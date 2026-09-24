import pytest

from helpers import write_source

CLASS_SOURCE = """CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    INTERFACES if_oo_adt_classrun.
  PROTECTED SECTION.
  PRIVATE SECTION.
ENDCLASS.

CLASS {name} IMPLEMENTATION.
  METHOD if_oo_adt_classrun~main.
{body}
  ENDMETHOD.
ENDCLASS."""


@pytest.fixture
def runnable_class(client, uid, cleanup):
    """Create and activate a class whose main method runs the given ABAP statements."""

    def create(suffix, body):
        name = f"ZCL_ADTPY_{uid}_{suffix}"
        uri = f"/sap/bc/adt/oo/classes/{name.lower()}"
        client.create("CLAS/OC", name, "$TMP", "adt-py class run test")
        cleanup(uri)
        write_source(client, uri, CLASS_SOURCE.format(name=name.lower(), body=body))
        assert client.activate(name, uri)
        return name

    return create


def test_run_class(client, runnable_class):
    name = runnable_class("RUN", "    out->write( |Hello from { sy-uname }| ).\n    out->write( 42 ).")
    output = client.run_class(name)
    # numbers are padded with trailing blanks in the console output
    lines = [line.rstrip() for line in output.splitlines()]
    assert lines[:2] == [f"Hello from {client.username}", "42"]


def test_run_class_runtime_error(client, runnable_class):
    name = runnable_class("ERR", "    DATA(zero) = 0.\n    out->write( 1 / zero ).")
    with pytest.raises(Exception, match="500 - Running .* failed: Division by 0"):
        client.run_class(name)


def test_run_missing_class_returns_explanation(client):
    # SAP reports this as normal output, not as an error
    output = client.run_class("ZCL_ADTPY_DOES_NOT_EXIST")
    assert "ZCL_ADTPY_DOES_NOT_EXIST" in output
