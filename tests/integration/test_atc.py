import pytest

from helpers import write_source

CLASS_SOURCE = """CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS run.
  PROTECTED SECTION.
  PRIVATE SECTION.
ENDCLASS.

CLASS {name} IMPLEMENTATION.
  METHOD run.
    SELECT * FROM tadir INTO TABLE @DATA(entries) UP TO 1 ROWS.
  ENDMETHOD.
ENDCLASS."""


@pytest.fixture
def atc_objects(client, uid, cleanup):
    """A package with a class that reads TADIR directly, which ATC reports on."""
    package = f"$ZADTPY_{uid}_ATC"
    name = f"ZCL_ADTPY_{uid}_ATC"
    uri = f"/sap/bc/adt/oo/classes/{name.lower()}"

    client.create_package(package, "adt-py atc test", parent="$TMP")
    cleanup(f"/sap/bc/adt/packages/{package.lower()}")
    client.create("CLAS/OC", name, package, "adt-py atc test")
    cleanup(uri)
    write_source(client, uri, CLASS_SOURCE.format(name=name.lower()))
    assert client.activate(name, uri)
    return {"package": package, "class": name, "uri": uri}


def test_default_check_variant_exists(client):
    default = client.default_check_variant()
    assert default
    assert default in [v["name"] for v in client.list_check_variants(default)]


def test_list_check_variants(client):
    variants = client.list_check_variants("*", max_results=5)
    assert len(variants) == 5
    assert all(v["name"] for v in variants)


def test_run_atc_on_class(client, atc_objects):
    result = client.run_atc(atc_objects["uri"])

    assert result["check_variant"] == client.default_check_variant()
    findings = [f for f in result["findings"] if f["object_name"] == atc_objects["class"]]
    assert findings
    tadir = [f for f in findings if f["tags"].get("REF_OBJ_NAME") == "TADIR"]
    assert tadir, "expected a finding about the direct TADIR access"
    assert tadir[0]["uri"] == atc_objects["uri"] + "/source/main"
    assert tadir[0]["line"] == 10
    assert tadir[0]["priority"] in (1, 2, 3)

    text = client.atc_documentation(findings[0]["documentation_uri"])
    assert text and "<p>" not in text


def test_run_atc_on_package(client, atc_objects):
    package_uri = f"/sap/bc/adt/packages/{atc_objects['package'].lower()}"
    result = client.run_atc(package_uri)
    assert atc_objects["class"] in {f["object_name"] for f in result["findings"]}


def test_run_atc_unknown_variant(client, atc_objects):
    with pytest.raises(Exception, match="does not exist"):
        client.run_atc(atc_objects["uri"], "ZADTPY_NO_SUCH_VARIANT")
