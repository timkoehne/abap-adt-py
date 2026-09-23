import pytest

from abap_adt_py.api import transport
from helpers import PARAMS, FakeResponse, fixture

REQUEST, TASK = "A4HK900160", "A4HK900161"
PROGRAM = "/sap/bc/adt/programs/programs/z_adtpy_fixture_tr"


def request_detail(request_status: str, task_status: str) -> FakeResponse:
    """The captured request with its task, both modifiable, set to the given statuses."""
    text = fixture("transport_request.xml")
    text = text.replace(
        f'tm:number="{REQUEST}" tm:parent="" tm:owner="DEVELOPER" tm:desc="adt-py fixture capture" tm:type="K" tm:status="D"',
        f'tm:number="{REQUEST}" tm:parent="" tm:owner="DEVELOPER" tm:desc="adt-py fixture capture" tm:type="K" tm:status="{request_status}"',
    )
    marker = f'tm:number="{TASK}"'
    head, tail = text.split(marker, 1)
    tail = tail.replace('tm:status="D"', f'tm:status="{task_status}"', 1)
    return FakeResponse(200, head + marker + tail)


def test_request_detail_helper_changes_statuses():
    assert f'tm:number="{REQUEST}"' in fixture("transport_request.xml")
    text = request_detail("R", "R").text
    assert 'tm:status="D"' not in text.split("<tm:abap_object")[0]


def test_transport_info_local_object(fake_sap):
    calls = fake_sap(transport, FakeResponse(200, fixture("transportcheck_local.xml")))
    info = transport.transport_info(PARAMS, PROGRAM, "$TMP")

    assert info == {
        "recording": False,
        "existing_request_only": False,
        "package": "$TMP",
        "requests": [],
        "locks": [],
    }
    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/cts/transportchecks"
    assert f"<URI>{PROGRAM}</URI>" in call["body"]
    assert "<DEVCLASS>$TMP</DEVCLASS>" in call["body"]
    assert "<OPERATION>I</OPERATION>" in call["body"]
    assert "transport.service.checkData" in call["content_type"]


def test_transport_info_new_object_lists_requests(fake_sap):
    fake_sap(transport, FakeResponse(200, fixture("transportcheck_new.xml")))
    info = transport.transport_info(PARAMS, PROGRAM, "ZADTPY_FIXTURE")

    assert info["recording"] is True
    assert info["existing_request_only"] is False
    assert info["requests"] == [
        {
            "number": REQUEST,
            "type": "K",
            "status": "D",
            "owner": "DEVELOPER",
            "description": "adt-py fixture capture",
            "target": "",
        }
    ]


def test_transport_info_locked_object(fake_sap):
    calls = fake_sap(transport, FakeResponse(200, fixture("transportcheck_locked.xml")))
    info = transport.transport_info(PARAMS, PROGRAM, "ZADTPY_FIXTURE", "U")

    assert "<OPERATION>U</OPERATION>" in calls[0]["body"]
    assert info["existing_request_only"] is True
    [lock] = info["locks"]
    assert lock["object_name"] == "Z_ADTPY_FIXTURE_TR"
    assert lock["request"]["number"] == REQUEST


def test_transport_info_escapes_values(fake_sap):
    calls = fake_sap(transport, FakeResponse(200, fixture("transportcheck_local.xml")))
    transport.transport_info(PARAMS, "/sap/bc/adt/x?a=1&b=2", "Z<PKG>")
    assert "<URI>/sap/bc/adt/x?a=1&amp;b=2</URI>" in calls[0]["body"]
    assert "<DEVCLASS>Z&lt;PKG&gt;</DEVCLASS>" in calls[0]["body"]


def test_create_transport_returns_number(fake_sap):
    calls = fake_sap(transport, FakeResponse(200, fixture("transport_create.txt")))
    number = transport.create_transport(
        PARAMS, "/sap/bc/adt/packages/zadtpy_fixture", "Fixture", "ZADTPY_FIXTURE"
    )

    assert number == REQUEST
    body = calls[0]["body"]
    assert "<REQUEST_TEXT>Fixture</REQUEST_TEXT>" in body
    assert "<DEVCLASS>ZADTPY_FIXTURE</DEVCLASS>" in body
    assert "<REF>/sap/bc/adt/packages/zadtpy_fixture</REF>" in body


def test_create_transport_failure_raises(fake_sap):
    fake_sap(transport, FakeResponse(400, "error"))
    with pytest.raises(Exception, match="400"):
        transport.create_transport(PARAMS, PROGRAM, "x", "ZPKG")


def test_list_transports(fake_sap):
    calls = fake_sap(transport, FakeResponse(200, fixture("transport_tree.xml")))
    [request] = transport.list_transports(PARAMS, "DEVELOPER")

    assert calls[0]["params"] == {"user": "DEVELOPER", "requestStatus": "D"}
    assert request["number"] == REQUEST
    assert request["description"] == "adt-py fixture capture"
    assert request["status"] == "D"
    [task] = request["tasks"]
    assert task["number"] == TASK
    assert [(o["wbtype"], o["name"]) for o in task["objects"]] == [
        ("DEVC/K", "ZADTPY_FIXTURE"),
        ("PROG/P", "Z_ADTPY_FIXTURE_TR"),
    ]


def test_release_transport_releases_tasks_first(fake_sap):
    calls = fake_sap(
        transport,
        request_detail("D", "D"),
        FakeResponse(200, fixture("transport_release_task.xml")),
        FakeResponse(200, fixture("transport_release_task.xml")),
    )
    # the request's own report is taken from the task fixture: status "released"
    assert transport.release_transport(PARAMS, REQUEST)

    assert [(c["method"], c["uri"]) for c in calls] == [
        ("GET", f"/sap/bc/adt/cts/transportrequests/{REQUEST}"),
        ("POST", f"/sap/bc/adt/cts/transportrequests/{TASK}/newreleasejobs"),
        ("POST", f"/sap/bc/adt/cts/transportrequests/{REQUEST}/newreleasejobs"),
    ]


def test_release_transport_accepts_released_status_despite_error(fake_sap):
    # captured: SAP reports "Error in pre-export methods" although the request is released
    calls = fake_sap(
        transport,
        request_detail("D", "R"),
        FakeResponse(200, fixture("transport_release_request.xml")),
        request_detail("R", "R"),
    )
    assert transport.release_transport(PARAMS, REQUEST)
    assert len(calls) == 3


def test_release_transport_failure_reports_messages(fake_sap):
    fake_sap(
        transport,
        request_detail("D", "R"),
        FakeResponse(200, fixture("transport_release_failed.xml")),
        request_detail("D", "R"),
    )
    with pytest.raises(Exception, match=f"Referencing task {TASK} not yet released"):
        transport.release_transport(PARAMS, REQUEST)


def test_release_unknown_transport_raises(fake_sap):
    fake_sap(transport, FakeResponse(404, "not found"))
    with pytest.raises(Exception, match="404"):
        transport.release_transport(PARAMS, "ZZZK999999")


def test_delete_transport(fake_sap):
    calls = fake_sap(transport, FakeResponse(200))
    assert transport.delete_transport(PARAMS, REQUEST)
    assert calls[0]["method"] == "DELETE"
    assert calls[0]["uri"] == f"/sap/bc/adt/cts/transportrequests/{REQUEST}"


def test_delete_transport_failure_raises(fake_sap):
    fake_sap(transport, FakeResponse(400, "contains locked objects"))
    with pytest.raises(Exception, match="locked objects"):
        transport.delete_transport(PARAMS, REQUEST)
