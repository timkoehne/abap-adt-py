import pytest

from abap_adt_py import exceptions
from abap_adt_py.api import atc, classrun, create, datapreview, login, transport
from abap_adt_py.exceptions import (
    AdtError,
    AuthenticationError,
    ClassRunError,
    InvalidLockHandleError,
    LockError,
    NotFoundError,
    ObjectLockedError,
    QueryError,
    SessionError,
    TransportError,
    error_from_response,
)
from helpers import PARAMS, FakeResponse, fixture


def test_every_error_is_an_adt_error_and_an_exception():
    for cls in (
        AuthenticationError,
        SessionError,
        NotFoundError,
        ObjectLockedError,
        InvalidLockHandleError,
        exceptions.ActivationError,
        TransportError,
        QueryError,
        ClassRunError,
    ):
        assert issubclass(cls, AdtError)
        assert issubclass(cls, Exception)
    assert issubclass(ObjectLockedError, LockError)
    assert issubclass(InvalidLockHandleError, LockError)


def test_error_carries_the_sap_details():
    error = error_from_response(
        FakeResponse(404, fixture("error_not_found.xml")), "Failed to lock Z_X"
    )
    assert isinstance(error, NotFoundError)
    assert str(error) == "404 - Failed to lock Z_X: Z_ADTPY_MISSING does not exist"
    assert error.status_code == 404
    assert error.sap_type == "ExceptionResourceNotFound"
    assert error.sap_message == "Z_ADTPY_MISSING does not exist"
    assert error.response_text == fixture("error_not_found.xml")


def test_placeholder_message_falls_back_to_reason():
    # SAP sometimes sends "I::000" instead of a message
    response = FakeResponse(404, fixture("error_not_found_placeholder.xml"), reason="Not Found")
    error = error_from_response(response, "Failed to get source of Z_X")
    assert str(error) == "404 - Failed to get source of Z_X: Not Found"


@pytest.mark.parametrize(
    "response, cls",
    [
        (FakeResponse(401, fixture("error_login.html")), AuthenticationError),
        (
            FakeResponse(403, "CSRF token validation failed", {"x-csrf-token": "Required"}),
            SessionError,
        ),
        (FakeResponse(404, fixture("error_not_found.xml")), NotFoundError),
        (FakeResponse(423, fixture("error_invalid_lock_handle.xml")), InvalidLockHandleError),
        (FakeResponse(500, fixture("error_already_exists.xml")), AdtError),
    ],
    ids=["401", "403-csrf", "404", "423", "500"],
)
def test_status_mapping(response, cls):
    assert type(error_from_response(response, "action")) is cls


def test_specific_status_wins_over_default_class():
    response = FakeResponse(404, fixture("error_not_found.xml"))
    assert type(error_from_response(response, "action", QueryError)) is NotFoundError
    response = FakeResponse(400, fixture("datapreview_error.xml"))
    assert type(error_from_response(response, "action", QueryError)) is QueryError


def test_message_from_html_error_page():
    error = error_from_response(FakeResponse(401, fixture("error_login.html")), "Login failed")
    assert str(error) == "401 - Login failed: Logon failed"


def test_message_from_plain_text():
    error = error_from_response(FakeResponse(500, "something broke\n"), "action")
    assert error.sap_message == "something broke"


def test_login_failure(fake_sap):
    fake_sap(login, FakeResponse(401, fixture("error_login.html")))
    with pytest.raises(AuthenticationError, match="401 - Login failed: Logon failed"):
        login.login(PARAMS)


def test_create_existing_object(fake_sap):
    fake_sap(create, FakeResponse(500, fixture("error_already_exists.xml")))
    with pytest.raises(AdtError) as error:
        create.create(PARAMS, "PROG/P", "Z_ADTPY_ERR", "$TMP", "x", "DEVELOPER")
    assert error.value.sap_type == "ExceptionResourceCreationFailure"
    assert "already exists" in error.value.sap_message


def test_query_error(fake_sap):
    fake_sap(datapreview, FakeResponse(400, fixture("datapreview_error.xml")))
    with pytest.raises(QueryError):
        datapreview.run_query(PARAMS, "SELECT * FROM does_not_exist")


def test_class_run_error(fake_sap):
    fake_sap(classrun, FakeResponse(500, fixture("classrun_runtime_error.html")))
    with pytest.raises(ClassRunError) as error:
        classrun.run_class(PARAMS, "ZCL_DEMO")
    assert error.value.sap_message.startswith("Division by 0")


def test_unknown_atc_variant(fake_sap):
    empty = fixture("atc_variants.xml").replace("nameditem:namedItem>", "ignored>")
    fake_sap(atc, FakeResponse(200, empty))
    with pytest.raises(NotFoundError):
        atc.run_atc(PARAMS, "/sap/bc/adt/oo/classes/zcl_x", "ZDOES_NOT_EXIST")


def test_transport_errors(fake_sap):
    fake_sap(transport, FakeResponse(400, "Request/task cannot be deleted because it contains locked objects"))
    with pytest.raises(TransportError, match="locked objects"):
        transport.delete_transport(PARAMS, "A4HK900001")
