import pytest

from helpers import delete_object, write_source

CLASS_SOURCE = """CLASS {cls} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS add IMPORTING a TYPE i b TYPE i RETURNING VALUE(result) TYPE i.
  PROTECTED SECTION.
  PRIVATE SECTION.
ENDCLASS.

CLASS {cls} IMPLEMENTATION.
  METHOD add.
    result = a + b.
  ENDMETHOD.
ENDCLASS."""

PROGRAM_SOURCE = """REPORT {prog}.
DATA(calc) = NEW {cls}( ).
DATA(sum) = calc->add( a = 1 b = 2 ).
WRITE sum.
cl_abap_typedescr=>describe_by_name( 'I' )."""


@pytest.fixture(scope="module")
def objects(client, uid):
    """A class with a method ADD and a program calling it, shared by the tests (they only read)."""
    cls, prog = f"ZCL_ADTPY_{uid}_NAV", f"Z_ADTPY_{uid}_NAV"
    class_uri = f"/sap/bc/adt/oo/classes/{cls.lower()}"
    program_uri = f"/sap/bc/adt/programs/programs/{prog.lower()}"
    source = PROGRAM_SOURCE.format(prog=prog.lower(), cls=cls.lower())

    created = []
    try:
        client.create("CLAS/OC", cls, "$TMP", "adt-py navigation test")
        created.append(class_uri)
        write_source(client, class_uri, CLASS_SOURCE.format(cls=cls.lower()))
        assert client.activate(cls, class_uri)

        client.create("PROG/P", prog, "$TMP", "adt-py navigation test")
        created.append(program_uri)
        write_source(client, program_uri, source)
        assert client.activate(prog, program_uri)

        yield {
            "class": cls,
            "class_uri": class_uri,
            "program": prog,
            "program_uri": program_uri,
            "source": source,
            # column of "add" in "DATA(sum) = calc->add( ..."
            "add_column": source.splitlines()[2].index("add"),
        }
    finally:
        for uri in reversed(created):
            delete_object(client, uri)


def test_find_definition_of_method(client, objects):
    source_uri = objects["program_uri"] + "/source/main"
    target = client.find_definition(
        source_uri, objects["source"], 3, objects["add_column"]
    )
    assert target == {
        "uri": objects["class_uri"] + "/source/main",
        "line": 3,
        "column": 12,
    }


def test_find_definition_of_sap_class(client, objects):
    source_uri = objects["program_uri"] + "/source/main"
    target = client.find_definition(source_uri, objects["source"], 5, 5)
    assert target["uri"] == "/sap/bc/adt/oo/classes/cl_abap_typedescr/source/main"


def test_find_definition_of_local_variable(client, objects):
    source_uri = objects["program_uri"] + "/source/main"
    target = client.find_definition(source_uri, objects["source"], 4, 7)
    assert target == {"uri": source_uri, "line": 3, "column": 5}


def test_find_definition_on_keyword(client, objects):
    source_uri = objects["program_uri"] + "/source/main"
    assert client.find_definition(source_uri, objects["source"], 4, 0) is None


def test_where_used_method(client, objects):
    usages = client.where_used(objects["class_uri"] + "/source/main", 3, 12)
    assert [(u["object_name"], u["line"], u["column"]) for u in usages] == [
        (objects["program"], 3, objects["add_column"])
    ]
    assert "calc->add" in usages[0]["code"]


def test_where_used_class(client, objects):
    usages = client.where_used(objects["class_uri"])
    in_program = [u for u in usages if u["object_name"] == objects["program"]]
    assert sorted(u["line"] for u in in_program) == [2, 3]
    assert all(
        u["object_type"] == "PROG/P" and u["package"] == "$TMP" for u in in_program
    )


def test_code_completion(client, objects):
    source = objects["source"] + "\nDATA(x) = calc->a"
    proposals = client.code_completion(
        objects["program_uri"] + "/source/main", source, 6, len("DATA(x) = calc->a")
    )
    assert {"identifier": "ADD", "kind": 3, "prefix_length": 1} in proposals
