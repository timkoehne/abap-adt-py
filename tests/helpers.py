import contextlib
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# http_request_parameters are only passed through to request(), which the unit tests replace
PARAMS = {
    "host": "http://sap.example",
    "csrf_token": "token",
    "statefulness": "stateless",
    "request_number": 0,
    "session": None,
}


def fixture(name: str) -> str:
    """Return a response captured from a real SAP system (see tests/fixtures)."""
    return (FIXTURES / name).read_text()


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "", headers=None, reason=""):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.reason = reason


# helpers for the integration tests


@contextlib.contextmanager
def locked(client, object_uri: str):
    handle = client.lock(object_uri)
    try:
        yield handle
    finally:
        try:
            client.unlock(object_uri, handle)
        except Exception:
            pass  # the object may be gone after a delete
        client.statefulness = "stateless"


def write_source(client, object_uri, source, transport=None, include="source/main"):
    with locked(client, object_uri) as handle:
        client.set_object_source(f"{object_uri}/{include}", source, handle, transport)


def delete_object(client, object_uri, transport=None):
    with locked(client, object_uri) as handle:
        client.delete(object_uri, handle, transport)
