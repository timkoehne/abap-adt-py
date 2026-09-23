import requests
from .compat_typing import Literal, Optional, TypedDict


class HttpRequestParameters(TypedDict):
    host: str
    csrf_token: str
    statefulness: Literal["stateless", "stateful"]
    request_number: int
    session: requests.Session


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
    if method == "POST":
        response = session.post(**config)
    elif method == "GET":
        response = session.get(**config)
    elif method == "PUT":
        response = session.put(**config)
    elif method == "DELETE":
        response = session.delete(**config)
    else:
        raise ValueError(f"Unsupported method: {method}")
    return response
