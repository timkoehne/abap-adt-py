import pytest

from abap_adt_py.api import activate, content, delete, lock, prettyprint, search
from abap_adt_py.exceptions import (
    ActivationError,
    InvalidLockHandleError,
    NotFoundError,
    ObjectLockedError,
    SessionError,
)
from helpers import PARAMS, FakeResponse, fixture

PROGRAM = "/sap/bc/adt/programs/programs/z_test"


def test_lock_returns_handle(fake_sap):
    calls = fake_sap(lock, FakeResponse(200, fixture("lock.xml")))
    assert lock.lock(PARAMS, PROGRAM) == "AD111DBD5E2316FBF7AA949C8B2AEC2B5C27CD4E"

    call = calls[0]
    assert call["params"] == {"_action": "LOCK", "accessMode": "MODIFY"}
    # packages answer 406 unless the lock result type is requested explicitly
    assert "dataname=com.sap.adt.lock.result" in call["accept"]


def test_lock_held_by_other_user(fake_sap):
    fake_sap(lock, FakeResponse(403, fixture("error_locked.xml")))
    with pytest.raises(ObjectLockedError) as error:
        lock.lock(PARAMS, PROGRAM)
    assert error.value.sap_message == "User DEVELOPER is currently editing Z_ADTPY_ERR"


def test_lock_with_expired_session(fake_sap):
    fake_sap(lock, FakeResponse(403, "CSRF token validation failed", {"x-csrf-token": "Required"}))
    with pytest.raises(SessionError):
        lock.lock(PARAMS, PROGRAM)


def test_lock_missing_object(fake_sap):
    fake_sap(lock, FakeResponse(404, fixture("error_not_found.xml")))
    with pytest.raises(NotFoundError, match="Z_ADTPY_MISSING does not exist"):
        lock.lock(PARAMS, PROGRAM)


def test_unlock(fake_sap):
    calls = fake_sap(lock, FakeResponse(200))
    assert lock.unlock(PARAMS, PROGRAM, "HANDLE")
    assert calls[0]["params"] == {"_action": "UNLOCK", "lockHandle": "HANDLE"}


def test_get_object_source(fake_sap):
    calls = fake_sap(content, FakeResponse(200, "REPORT z_test."))
    source = content.get_object_source(PARAMS, PROGRAM + "/source/main", "inactive")

    assert source == "REPORT z_test."
    assert calls[0]["params"] == {"version": "inactive"}


def test_set_object_source(fake_sap):
    calls = fake_sap(content, FakeResponse(200))
    assert content.set_object_source(
        PARAMS, PROGRAM + "/source/main", "REPORT z_test.", "HANDLE", "A4HK900001"
    )

    call = calls[0]
    assert call["method"] == "PUT"
    assert call["body"] == "REPORT z_test."
    assert call["params"] == {"lockHandle": "HANDLE", "corrNr": "A4HK900001"}
    assert call["content_type"].startswith("text/plain")


def test_set_object_source_without_lock(fake_sap):
    fake_sap(content, FakeResponse(423, fixture("error_invalid_lock_handle.xml")))
    with pytest.raises(InvalidLockHandleError, match="invalid lock handle"):
        content.set_object_source(PARAMS, PROGRAM, "x", "HANDLE")


def test_delete(fake_sap):
    calls = fake_sap(delete, FakeResponse(200))
    assert delete.delete(PARAMS, PROGRAM, "HANDLE")
    assert calls[0]["method"] == "DELETE"
    assert calls[0]["params"] == {"lockHandle": "HANDLE"}


def test_delete_with_transport(fake_sap):
    calls = fake_sap(delete, FakeResponse(200))
    delete.delete(PARAMS, PROGRAM, "HANDLE", "A4HK900001")
    assert calls[0]["params"] == {"lockHandle": "HANDLE", "corrNr": "A4HK900001"}


def test_activate_success(fake_sap):
    calls = fake_sap(activate, FakeResponse(200, fixture("activation_success.xml")))
    assert activate.activate(PARAMS, "Z_TEST", PROGRAM)
    assert 'adtcore:name="Z_TEST"' in calls[0]["body"]


def test_activate_escapes_values(fake_sap):
    calls = fake_sap(activate, FakeResponse(200, fixture("activation_success.xml")))
    activate.activate(PARAMS, "Z_A&B", PROGRAM)
    assert 'adtcore:name="Z_A&amp;B"' in calls[0]["body"]


def test_activate_error_reports_messages(fake_sap):
    fake_sap(activate, FakeResponse(200, fixture("activation_error.xml")))
    with pytest.raises(ActivationError) as error:
        activate.activate(PARAMS, "Z_TEST", PROGRAM)

    assert str(error.value) == (
        '200 - Activation of Z_TEST failed: Field "UNDEFINED_VAR" is unknown.'
    )
    assert error.value.messages[1] == {
        "type": "E",
        "text": 'Field "UNDEFINED_VAR" is unknown.',
        "uri": "/sap/bc/adt/programs/programs/z_adtpy_fixture/source/main#start=2,6;end=2,19",
        "object": "Program Z_ADTPY_FIXTURE",
    }


def test_activate_http_error(fake_sap):
    fake_sap(activate, FakeResponse(404, "not found"))
    with pytest.raises(NotFoundError, match="404 - Failed to activate Z_TEST"):
        activate.activate(PARAMS, "Z_TEST", PROGRAM)


def test_prettyprint(fake_sap):
    calls = fake_sap(prettyprint, FakeResponse(200, fixture("prettyprint.txt")))
    assert prettyprint.prettyprint(PARAMS, "report z_x. write 'a'.") == (
        "REPORT z_x. WRITE 'a'."
    )
    assert calls[0]["body"] == "report z_x. write 'a'."


def test_prettyprint_settings(fake_sap):
    calls = fake_sap(prettyprint, FakeResponse(200))
    assert prettyprint.set_pretty_printer_settings(
        PARAMS, {"indentation": True, "style": "keywordUpper"}
    )
    # the server answers 415 for any other content type
    assert calls[0]["content_type"] == "application/vnd.sap.adt.ppsettings.v5+xml"
    body = calls[0]["body"]
    assert 'indentation="true"' in body
    assert 'style="keywordUpper"' in body


def test_search(fake_sap):
    calls = fake_sap(search, FakeResponse(200, fixture("search.xml")))
    results = search.search_object(PARAMS, "CL_ABAP_TYPEDESCR", 3)

    assert results == [
        {
            "uri": "/sap/bc/adt/oo/classes/cl_abap_typedescr",
            "type": "CLAS/OC",
            "name": "CL_ABAP_TYPEDESCR",
            "packageName": "SABP_RTTI",
            "description": "Runtime Type Services",
        }
    ]
    assert calls[0]["params"]["maxResults"] == 3
