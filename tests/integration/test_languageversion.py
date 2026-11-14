import pytest

from abap_adt_py.exceptions import ActivationError, AdtError
from helpers import write_source

CLASS = """CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS run RETURNING VALUE(rv) TYPE i.
ENDCLASS.

CLASS {name} IMPLEMENTATION.
  METHOD run.
{body}
  ENDMETHOD.
ENDCLASS."""


def test_class_created_in_cloud_development(client, uid, cleanup):
    name = f"ZCL_ADTPY_{uid}_LV"
    uri = f"/sap/bc/adt/oo/classes/{name.lower()}"
    cleanup(uri)
    client.create("CLAS/OC", name, "$TMP", "adt-py language version", language_version="cloudDevelopment")
    write_source(client, uri, CLASS.format(name=name.lower(), body="    rv = 1."))
    client.activate(name, uri)

    version = client.get_language_version(uri)
    assert version["version"] == "cloudDevelopment"
    assert set(version["allowed"]) == {"standard", "cloudDevelopment", "keyUser"}
    stored = client.run_query(f"SELECT uccheck FROM progdir WHERE name = '{name:=<30}CP' AND state = 'A'")
    assert stored["rows"] == [{"UCCHECK": "5"}]

    # code that is not valid in the version: the activation fails, the active version stays
    client.set_language_version(uri, "standard")
    write_source(client, uri, CLASS.format(name=name.lower(), body="    SELECT COUNT(*) FROM tcurx INTO @rv."))
    client.activate(name, uri)
    with pytest.raises(ActivationError) as error:
        client.set_language_version(uri, "5")
    assert "TCURX" in str(error.value)
    stored = client.run_query(f"SELECT uccheck FROM progdir WHERE name = '{name:=<30}CP' AND state = 'A'")
    assert stored["rows"] == [{"UCCHECK": "X"}]


@pytest.mark.parametrize(
    "object_type, suffix, path",
    [
        ("INTF/OI", "I", "/sap/bc/adt/oo/interfaces"),
        ("FUGR/F", "G", "/sap/bc/adt/functions/groups"),
        ("TABL/DT", "T", "/sap/bc/adt/ddic/tables"),
        ("TABL/DS", "S", "/sap/bc/adt/ddic/structures"),
        ("DDLS/DF", "V", "/sap/bc/adt/ddic/ddl/sources"),
        ("SRVD/SRV", "D", "/sap/bc/adt/ddic/srvd/sources"),
    ],
)
def test_kinds_created_in_cloud_development(client, uid, cleanup, object_type, suffix, path):
    # table names have at most 16 characters
    name = f"ZIF_ADTPY_{uid}_LV" if object_type == "INTF/OI" else f"ZADT{uid}LV{suffix}"
    uri = f"{path}/{name.lower()}"
    cleanup(uri)
    client.create(object_type, name, "$TMP", "adt-py language version", language_version="cloudDevelopment")
    assert client.get_language_version(uri)["version"] == "cloudDevelopment"


def test_a_report_cannot_be_cloud_development(client, uid):
    name = f"ZADTPY_{uid}_LVR"
    with pytest.raises(AdtError, match="not allowed in this software component"):
        client.create("PROG/P", name, "$TMP", "adt-py language version", language_version="cloudDevelopment")
    # it is deleted again
    assert client.search_object(name, 5) == []


def test_dictionary_objects_switch(client, uid, cleanup):
    domain, data_element = f"ZADTPY_{uid}_LVDO", f"ZADTPY_{uid}_LVDE"
    cleanup(f"/sap/bc/adt/ddic/domains/{domain.lower()}")
    client.create_domain(domain, "$TMP", "adt-py domain", "CHAR", 4)
    cleanup(f"/sap/bc/adt/ddic/dataelements/{data_element.lower()}")
    client.create_data_element(data_element, "$TMP", "adt-py data element", domain=domain)

    for uri in (
        f"/sap/bc/adt/ddic/domains/{domain.lower()}",
        f"/sap/bc/adt/ddic/dataelements/{data_element.lower()}",
    ):
        assert client.get_language_version(uri)["version"] == "standard"
        client.set_language_version(uri, "cloudDevelopment")
        assert client.get_language_version(uri)["version"] == "cloudDevelopment"


def test_message_class_has_no_version(client, uid, cleanup):
    name = f"ZADTPY_{uid}_LVM"
    uri = f"/sap/bc/adt/messageclass/{name.lower()}"
    cleanup(uri)
    client.create_message_class(name, "$TMP", "adt-py messages")
    assert client.get_language_version(uri) == {
        "name": name, "type": "MSAG/N", "uri": uri, "version": "", "allowed": []
    }
    with pytest.raises(ValueError, match="no ABAP language version"):
        client.set_language_version(uri, "cloudDevelopment")
