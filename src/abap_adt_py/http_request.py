import requests
from .compat_typing import Callable, Literal, NotRequired, Optional, TypedDict


class HttpRequestParameters(TypedDict):
    host: str
    csrf_token: str
    statefulness: Literal["stateless", "stateful"]
    request_number: int
    session: requests.Session
    # logs in again and returns the new CSRF token, used when the session expired
    refresh_csrf_token: NotRequired[Callable[[], str]]


def csrf_token_rejected(response) -> bool:
    """True if SAP rejected the request's CSRF token, e.g. because the session expired."""
    headers = getattr(response, "headers", None) or {}
    return (
        response.status_code == 403
        and headers.get("x-csrf-token", "").lower() == "required"
    )


def with_transport(params: dict, transport: Optional[str]) -> dict:
    """Add the transport request (corrNr) to the query parameters if one is given."""
    if transport:
        params["corrNr"] = transport
    return params


def request(
    http_request_parameters: HttpRequestParameters,
    uri: str,
    method: Literal["GET", "POST", "PUT", "DELETE"],
    body: str,
    params: dict,
    content_type: str = "application/xml",
    accept: str = "*/*",
) -> requests.Response:

    config = {
        "params": params,
        "headers": {
            "Accept": accept,
            "Cache-Control": "no-cache",
            "x-csrf-token": http_request_parameters["csrf_token"],
            "X-sap-adt-sessiontype": http_request_parameters["statefulness"],
            "content-type": content_type,
        },
        "url": http_request_parameters["host"] + uri,
        "data": body,
    }

    session = http_request_parameters["session"]
    send = {
        "GET": session.get,
        "POST": session.post,
        "PUT": session.put,
        "DELETE": session.delete,
    }.get(method)
    if send is None:
        raise ValueError(f"Unsupported method: {method}")

    response = send(**config)

    refresh_csrf_token = http_request_parameters.get("refresh_csrf_token")
    if refresh_csrf_token and csrf_token_rejected(response):
        # the session expired: log in again and repeat the request once
        config["headers"]["x-csrf-token"] = refresh_csrf_token()
        response = send(**config)
    return response
