from datetime import datetime, timedelta, timezone

import pytest

from abap_adt_py.api import dumps
from abap_adt_py.exceptions import NotFoundError
from helpers import PARAMS, FakeResponse, fixture

DUMP_ID = (
    "/sap/bc/adt/runtime/dump/20260924182816vhcala4hci_A4H_00"
    "%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20DEVELOPER%20%20%20001%20%20%20%20%20%20%20%201"
)


def test_list_dumps(fake_sap):
    calls = fake_sap(dumps, FakeResponse(200, fixture("dumps_feed.xml")))
    result = dumps.list_dumps(PARAMS, max_results=2)

    assert calls[0]["uri"] == "/sap/bc/adt/runtime/dumps"
    assert calls[0]["params"] == {"$top": 2}
    assert len(result) == 2
    assert result[0] == {
        "id": DUMP_ID,
        "runtime_error": "COMPUTE_INT_ZERODIVIDE",
        "program": "ZCL_ADTPY_83D6E6_ERR==========CP",
        "user": "DEVELOPER",
        "datetime": datetime(2026, 9, 24, 18, 28, 16, tzinfo=timezone.utc),
        "short_text": "Division by 0 (type I or INT8)",
    }


def test_list_dumps_filters(fake_sap):
    calls = fake_sap(dumps, FakeResponse(200, fixture("dumps_feed.xml")))
    since = datetime(2026, 9, 24, 20, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    dumps.list_dumps(PARAMS, user="developer", runtime_error="compute_int_zerodivide", since=since)

    # the feed compares times in UTC and needs every condition inside and( ... )
    assert calls[0]["params"]["$query"] == (
        "and( equals( user, DEVELOPER ), "
        "equals( runtimeError, COMPUTE_INT_ZERODIVIDE ), "
        "greater( datetime, 20260924180000 ) )"
    )


def test_list_dumps_single_filter_is_wrapped(fake_sap):
    calls = fake_sap(dumps, FakeResponse(200, fixture("dumps_feed.xml")))
    dumps.list_dumps(PARAMS, user="DEVELOPER")
    assert calls[0]["params"]["$query"] == "and( equals( user, DEVELOPER ) )"


def test_list_dumps_failure_raises(fake_sap):
    fake_sap(dumps, FakeResponse(400, "Data is invalid and could not be converted"))
    with pytest.raises(Exception, match="400 - Failed to list runtime errors"):
        dumps.list_dumps(PARAMS)


def test_get_dump(fake_sap):
    calls = fake_sap(
        dumps,
        FakeResponse(200, fixture("dump.xml")),
        FakeResponse(200, fixture("dump_formatted.txt")),
    )
    dump = dumps.get_dump(PARAMS, DUMP_ID)

    assert [c["uri"] for c in calls] == [DUMP_ID, DUMP_ID + "/formatted"]
    assert dump["runtime_error"] == "COMPUTE_INT_ZERODIVIDE"
    assert dump["exception"] == "CX_SY_ZERODIVIDE"
    assert dump["program"] == "ZCL_ADTPY_83D6E6_ERR==========CP"
    assert dump["user"] == "DEVELOPER"
    assert dump["datetime"] == datetime(2026, 9, 24, 18, 28, 16, tzinfo=timezone.utc)
    assert dump["short_text"] == "Division by 0 (type I or INT8)"


def test_get_dump_chapters(fake_sap):
    fake_sap(
        dumps,
        FakeResponse(200, fixture("dump.xml")),
        FakeResponse(200, fixture("dump_formatted.txt")),
    )
    chapters = dumps.get_dump(PARAMS, DUMP_ID)["chapters"]

    # in the order of the dump, not of SAP's chapter list
    assert list(chapters)[:5] == [
        "Short Text",
        "What happened?",
        "What can you do?",
        "Error analysis",
        "How to correct the error",
    ]
    assert chapters["What happened?"].startswith("Error in the ABAP application program.")
    where = chapters["Information on where terminated"]
    assert "termination point is in line 3" in where
    # the box borders are removed
    assert not any(line.startswith("|") or line.endswith("|") for line in where.splitlines())
    # chapters beyond the end of the (shortened) text are skipped
    assert "ABAP Control Blocks (CONT)" not in chapters


def test_get_dump_text_has_no_padding(fake_sap):
    padded = "\n".join(line + " " * 40 for line in fixture("dump_formatted.txt").split("\n"))
    fake_sap(dumps, FakeResponse(200, fixture("dump.xml")), FakeResponse(200, padded))
    text = dumps.get_dump(PARAMS, DUMP_ID)["text"]
    assert not any(line != line.rstrip() for line in text.splitlines())


def test_get_missing_dump(fake_sap):
    fake_sap(dumps, FakeResponse(404, fixture("error_not_found.xml")))
    with pytest.raises(NotFoundError):
        dumps.get_dump(PARAMS, DUMP_ID)
