from abap_adt_py import http_request
from abap_adt_py.adt_client import AdtClient
from abap_adt_py.api import login
from helpers import PARAMS, FakeResponse

EXPIRED = FakeResponse(403, "CSRF token validation failed", {"x-csrf-token": "Required"})


class ScriptedSession:
    """Answers requests with the given responses and records the CSRF token sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.tokens = []

    def post(self, **config):
        self.tokens.append(config["headers"]["x-csrf-token"])
        return self.responses.pop(0)

    get = put = delete = post


def send(session, refresh=None):
    params = {**PARAMS, "session": session, "csrf_token": "old"}
    if refresh:
        params["refresh_csrf_token"] = refresh
    return http_request.request(params, "/sap/bc/adt/x", "POST", "", {})


def test_expired_session_is_refreshed_and_retried_once():
    session = ScriptedSession(EXPIRED, FakeResponse(200, "ok"))
    refreshed = []
    response = send(session, lambda: refreshed.append(1) or "new")

    assert response.text == "ok"
    assert session.tokens == ["old", "new"]
    assert refreshed == [1]


def test_retry_happens_only_once():
    session = ScriptedSession(EXPIRED, EXPIRED)
    response = send(session, lambda: "new")
    assert http_request.csrf_token_rejected(response)
    assert session.tokens == ["old", "new"]


def test_no_retry_without_refresh_callback():
    session = ScriptedSession(EXPIRED)
    assert send(session).status_code == 403
    assert session.tokens == ["old"]


def test_other_403_is_not_retried():
    locked = FakeResponse(403, "User DEVELOPER is currently editing Z_TEST")
    session = ScriptedSession(locked)
    assert send(session, lambda: "new") is locked
    assert session.tokens == ["old"]


def test_login_always_fetches_a_new_token(monkeypatch):
    sent = []

    def fake_request(http_request_parameters, **kwargs):
        sent.append(http_request_parameters)
        return FakeResponse(200, headers={"x-csrf-token": "fresh"})

    monkeypatch.setattr(login, "request", fake_request)
    params = {**PARAMS, "csrf_token": "stale", "refresh_csrf_token": lambda: "x"}

    assert login.login(params) == "fresh"
    assert sent[0]["csrf_token"] == "fetch"
    # logging in must not try to log in again
    assert not sent[0]["refresh_csrf_token"]


def client(**kwargs):
    return AdtClient("http://sap.example", "USER", "pw", "001", "EN", **kwargs)


def test_client_reconnects_while_nothing_is_locked():
    c = client()
    assert c.build_request_parameters()["refresh_csrf_token"] == c._refresh_csrf_token


def test_client_does_not_reconnect_while_holding_a_lock():
    c = client()
    c.statefulness = "stateful"
    assert "refresh_csrf_token" not in c.build_request_parameters()


def test_reconnect_can_be_switched_off():
    assert "refresh_csrf_token" not in client(reconnect=False).build_request_parameters()


def test_lock_request_can_still_reconnect(monkeypatch):
    import abap_adt_py.adt_client as adt_client

    seen = []
    monkeypatch.setattr(adt_client, "lock", lambda params, uri: seen.append(params) or "HANDLE")
    c = client()
    assert c.lock("/sap/bc/adt/programs/programs/z_x") == "HANDLE"

    assert seen[0]["statefulness"] == "stateful"
    assert "refresh_csrf_token" in seen[0]
    assert c.statefulness == "stateful"
