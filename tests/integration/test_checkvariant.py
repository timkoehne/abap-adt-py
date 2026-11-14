import pytest

from abap_adt_py.exceptions import ActivationError, NotFoundError
from helpers import write_source

CLASS = """CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS run RETURNING VALUE(rv) TYPE i.
ENDCLASS.

CLASS {name} IMPLEMENTATION.
  METHOD run.
    SELECT SINGLE mandt FROM t000 INTO @DATA(lv_client).
    rv = strlen( lv_client ).
  ENDMETHOD.
ENDCLASS."""


def test_atc_checks(client):
    checks = {check["name"]: check for check in client.list_atc_checks()}
    assert len(checks) > 100
    assert checks["CI_SYSUBRC"]["category"] == "CI_ROBUSTNESS"

    check = client.get_atc_check("ci_sysubrc")
    assert check["description"] == "Check of SY-SUBRC Handling"
    read_db = next(p for p in check["parameters"] if p["name"] == "ReadDB")
    assert read_db == {"name": "ReadDB", "description": "Reading DB Accesses", "kind": "value", "default": "false"}
    with pytest.raises(NotFoundError):
        client.get_atc_check("CI_NOT_A_CHECK_ADTPY")


def test_check_variant(client, uid, cleanup):
    name = f"ZADTPY_{uid}_CV"
    uri = f"/sap/bc/adt/atc/checkvariants/{name.lower()}"
    cleanup(uri)
    client.save_check_variant(
        name, "$TMP", "adt-py check variant",
        [{"name": "CI_SYSUBRC", "parameters": {"ReadDB": True}}, {"name": "ci_no_order_by"}],
    )

    variant = client.get_check_variant(name)
    assert (variant["description"], variant["package"], variant["version"]) == ("adt-py check variant", "$TMP", "active")
    assert [check["name"] for check in variant["checks"]] == ["CI_SYSUBRC", "CI_NO_ORDER_BY"]
    assert variant["checks"][0]["parameters"]["ReadDB"] == "true"
    assert variant["checks"][0]["parameters"]["WriteDB"] == "false"

    # the variant runs: the SELECT SINGLE without checking SY-SUBRC is a finding of CI_SYSUBRC
    class_name = f"ZCL_ADTPY_{uid}_CV"
    class_uri = f"/sap/bc/adt/oo/classes/{class_name.lower()}"
    cleanup(class_uri)
    client.create("CLAS/OC", class_name, "$TMP", "adt-py check variant")
    write_source(client, class_uri, CLASS.format(name=class_name.lower()))
    client.activate(class_name, class_uri)
    result = client.run_atc(class_uri, check_variant=name)
    assert result["check_variant"] == name
    titles = {finding["check_title"] for finding in result["findings"]}
    assert "Check of SY-SUBRC Handling" in titles
    assert titles <= {"Check of SY-SUBRC Handling", "Search problematic statements for result of SELECT/OPEN CURSOR without ORDER BY"}

    # overwriting replaces the checks
    client.save_check_variant(name, "$TMP", "adt-py check variant 2", [{"name": "CI_NO_ORDER_BY"}])
    variant = client.get_check_variant(name)
    assert [check["name"] for check in variant["checks"]] == ["CI_NO_ORDER_BY"]
    assert variant["description"] == "adt-py check variant 2"

    with pytest.raises(ValueError, match="has no parameter Nonsense"):
        client.save_check_variant(name, "$TMP", "x", [{"name": "CI_SYSUBRC", "parameters": {"Nonsense": 1}}])
    with pytest.raises(NotFoundError, match="not an ATC check"):
        client.save_check_variant(name, "$TMP", "x", [{"name": "CI_NOT_A_CHECK_ADTPY"}])

    client.delete_check_variant(name)
    with pytest.raises(NotFoundError):
        client.get_check_variant(name)


def test_check_refusing_its_parameters(client, uid, cleanup):
    name = f"ZADTPY_{uid}_CR"
    cleanup(f"/sap/bc/adt/atc/checkvariants/{name.lower()}")
    # the ABAP Doc check refuses its own defaults
    with pytest.raises(ActivationError, match="rejected the attributes"):
        client.save_check_variant(name, "$TMP", "adt-py refused", [{"name": "CI_ABAP_DOC_COMMENT"}])
    assert client.get_check_variant(name)["version"] == "inactive"
