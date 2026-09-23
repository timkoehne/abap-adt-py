from abap_adt_py.adt_client import AdtClient
from helpers import write_source

CLASS_SOURCE = """CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS add IMPORTING a TYPE i b TYPE i RETURNING VALUE(result) TYPE i.
  PROTECTED SECTION.
  PRIVATE SECTION.
ENDCLASS.

CLASS {name} IMPLEMENTATION.
  METHOD add.
    result = a + b.
  ENDMETHOD.
ENDCLASS."""

TEST_CLASS_SOURCE = """CLASS ltc_add DEFINITION FINAL FOR TESTING DURATION SHORT RISK LEVEL HARMLESS.
  PRIVATE SECTION.
    METHODS passes FOR TESTING.
    METHODS fails FOR TESTING.
ENDCLASS.

CLASS ltc_add IMPLEMENTATION.
  METHOD passes.
    cl_abap_unit_assert=>assert_equals( exp = 3 act = NEW {name}( )->add( a = 1 b = 2 ) ).
  ENDMETHOD.
  METHOD fails.
    cl_abap_unit_assert=>assert_equals( exp = 5 act = NEW {name}( )->add( a = 1 b = 2 ) msg = 'expected failure' ).
  ENDMETHOD.
ENDCLASS."""


def test_search(client):
    [result] = client.search_object("CL_ABAP_TYPEDESCR", 1)
    assert result["name"] == "CL_ABAP_TYPEDESCR"
    assert result["type"] == "CLAS/OC"
    assert result["uri"] == "/sap/bc/adt/oo/classes/cl_abap_typedescr"


def test_program_lifecycle(client, uid, cleanup):
    name = f"Z_ADTPY_{uid}"
    uri = f"/sap/bc/adt/programs/programs/{name.lower()}"

    assert client.create("PROG/P", name, "$TMP", "adt-py test program")
    cleanup(uri)

    broken = f"REPORT {name.lower()}.\nWRITE undefined_variable."
    [error] = [
        m
        for m in client.syntax_check(uri, f"{uri}/source/main", broken)
        if m["type"] == "E"
    ]
    assert "UNDEFINED_VARIABLE" in error["short_text"]
    assert error["line"] == 2

    client.prettyprint_settings({"indentation": True, "style": "keywordUpper"})
    source = client.prettyprint(f"report {name.lower()}.\nwrite 'hello'.")
    assert source.startswith("REPORT")

    write_source(client, uri, source)
    assert client.get_object_source(f"{uri}/source/main", "inactive") == source
    assert client.activate(name, uri)
    assert client.get_object_source(f"{uri}/source/main") == source


def test_class_with_unit_tests(client, uid, cleanup):
    name = f"ZCL_ADTPY_{uid}"
    uri = f"/sap/bc/adt/oo/classes/{name.lower()}"

    assert client.create("CLAS/OC", name, "$TMP", "adt-py test class")
    cleanup(uri)

    handle = client.lock(uri)
    try:
        client.set_object_source(
            f"{uri}/source/main", CLASS_SOURCE.format(name=name.lower()), handle
        )
        client.create_test_class_include(name, handle)
        client.set_object_source(
            f"{uri}/includes/testclasses",
            TEST_CLASS_SOURCE.format(name=name.lower()),
            handle,
        )
    finally:
        client.unlock(uri, handle)
    assert client.activate(name, uri)

    structure = client.object_structure(uri)
    assert structure["name"] == name
    assert "ADD" in [component["name"] for component in structure["components"]]

    [alert] = client.run_unit_test(uri)
    assert alert["kind"] == "failedAssertion"
    assert "expected failure" in alert["title"]


def test_description_with_special_characters(client, uid, cleanup):
    name = f"Z_ADTPY_{uid}_ESC"
    description = 'Tom & Jerry "quoted" <x>'
    uri = f"/sap/bc/adt/programs/programs/{name.lower()}"

    assert client.create("PROG/P", name, "$TMP", description)
    cleanup(uri)

    [result] = client.search_object(name, 1)
    assert result["description"] == description


def test_language_is_applied(config):
    descriptions = {}
    for language in ("EN", "DE"):
        client = AdtClient(**{**config, "language": language})
        client.login()
        path = client.object_package_path("/sap/bc/adt/oo/classes/cl_abap_typedescr")
        assert path[0]["name"] == "BASIS"
        descriptions[language] = path[0]["description"]
    assert descriptions["EN"] != descriptions["DE"]
