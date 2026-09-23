import pytest


@pytest.fixture
def fake_sap(monkeypatch):
    """Replace request() in an api module with canned responses.

    Usage: calls = fake_sap(module, FakeResponse(...), ...)
    Every request is recorded in calls; running out of responses fails the test.
    """

    def install(module, *responses):
        calls = []
        queue = list(responses)

        def fake_request(
            http_request_parameters,
            uri,
            method,
            body,
            params,
            content_type="application/xml",
            accept="*/*",
        ):
            calls.append(
                {
                    "uri": uri,
                    "method": method,
                    "body": body,
                    "params": params,
                    "content_type": content_type,
                    "accept": accept,
                }
            )
            assert queue, f"unexpected request: {method} {uri}"
            return queue.pop(0)

        monkeypatch.setattr(module, "request", fake_request)
        return calls

    return install
