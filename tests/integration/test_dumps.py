from datetime import datetime, timedelta, timezone

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
    DATA(zero) = 0.
    out->write( 1 / zero ).
  ENDMETHOD.
ENDCLASS."""


def test_runtime_error_is_listed_and_readable(client, uid, cleanup):
    # a class that divides by zero produces a short dump when it runs
    name = f"ZCL_ADTPY_{uid}_DUMP"
    uri = f"/sap/bc/adt/oo/classes/{name.lower()}"
    client.create("CLAS/OC", name, "$TMP", "adt-py dump test")
    cleanup(uri)
    write_source(client, uri, CLASS_SOURCE.format(name=name.lower()))
    assert client.activate(name, uri)

    # the server clock may differ a little from ours
    started = datetime.now(timezone.utc) - timedelta(minutes=2)
    with pytest.raises(Exception, match="Division by 0"):
        client.run_class(name)

    found = client.list_dumps(
        user=client.username, runtime_error="COMPUTE_INT_ZERODIVIDE", since=started
    )
    [summary] = [d for d in found if d["program"].startswith(name)]
    assert summary["short_text"].startswith("Division by 0")
    assert summary["datetime"] >= started

    dump = client.get_dump(summary["id"])
    assert dump["exception"] == "CX_SY_ZERODIVIDE"
    assert "What happened?" in dump["chapters"]
    assert "IF_OO_ADT_CLASSRUN~MAIN" in dump["chapters"]["Information on where terminated"]


def test_list_dumps_limits_results(client):
    assert len(client.list_dumps(max_results=1)) <= 1
