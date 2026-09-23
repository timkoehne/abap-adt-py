import pytest

from abap_adt_py import http_request
from abap_adt_py.adt_client import AdtClient
from abap_adt_py.api import login
from helpers import PARAMS, FakeResponse


class FakeSession:
    def __init__(self):
        self.calls = []

    def _record(self, method):
        def call(**kwargs):
            self.calls.append((method, kwargs))
            return FakeResponse()

        return call

    def __getattr__(self, name):
        if name in ("get", "post", "put", "delete"):
            return self._record(name.upper())
        raise AttributeError(name)


def params_with(session):
    return {**PARAMS, "session": session, "csrf_token": "abc", "statefulness": "stateful"}


def test_request_sends_sap_headers():
    session = FakeSession()
    http_request.request(
        params_with(session), "/sap/bc/adt/x", "POST", "<a/>", {"q": "1"}
    )

    method, kwargs = session.calls[0]
    assert method == "POST"
    assert kwargs["url"] == "http://sap.example/sap/bc/adt/x"
    assert kwargs["params"] == {"q": "1"}
    assert kwargs["data"] == "<a/>"
    assert kwargs["headers"]["x-csrf-token"] == "abc"
    assert kwargs["headers"]["X-sap-adt-sessiontype"] == "stateful"
    assert kwargs["headers"]["content-type"] == "application/xml"
    assert kwargs["headers"]["Accept"] == "*/*"


def test_request_accept_can_be_overridden():
    session = FakeSession()
    http_request.request(
        params_with(session), "/x", "GET", "", {}, accept="text/plain"
    )
    assert session.calls[0][1]["headers"]["Accept"] == "text/plain"


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_request_dispatches_method(method):
    session = FakeSession()
    http_request.request(params_with(session), "/x", method, "", {})
    assert session.calls[0][0] == method


def test_request_rejects_unknown_method():
    with pytest.raises(ValueError):
        http_request.request(params_with(FakeSession()), "/x", "PATCH", "", {})


def test_with_transport():
    assert http_request.with_transport({"a": 1}, "A4HK900001") == {
        "a": 1,
        "corrNr": "A4HK900001",
    }
    assert http_request.with_transport({"a": 1}, None) == {"a": 1}
    assert http_request.with_transport({}, "") == {}


def test_client_sends_client_and_language_with_every_request():
    client = AdtClient("http://sap.example", "USER", "pw", "100", "DE")
    assert client.session.params == {"sap-client": "100", "sap-language": "DE"}


def test_client_counts_requests():
    client = AdtClient("http://sap.example", "USER", "pw", "100", "DE")
    first = client.build_request_parameters()
    second = client.build_request_parameters()
    assert second["request_number"] == first["request_number"] + 1
    assert first["session"] is client.session


def test_login_returns_csrf_token(fake_sap):
    calls = fake_sap(login, FakeResponse(200, headers={"x-csrf-token": "tok"}))
    assert login.login(PARAMS) == "tok"
    assert calls[0]["method"] == "GET"


def test_login_without_token_raises(fake_sap):
    fake_sap(login, FakeResponse(200))
    with pytest.raises(Exception, match="CSRF token"):
        login.login(PARAMS)


def test_login_failure_raises(fake_sap):
    fake_sap(login, FakeResponse(401, "Logon failed"))
    with pytest.raises(Exception, match="401"):
        login.login(PARAMS)
