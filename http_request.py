from typing import Literal, TypedDict
import requests


class HttpRequestParameters(TypedDict):
    host: str
    csrf_token: str
    statefulness: Literal["stateless", "stateful"]
    requst_number: int
    session: requests.Session

def _request(
    http_request_parameters: HttpRequestParameters,
    url: str,
    params: dict,
    method: Literal["GET", "POST", "PUT"] = "GET",
    body: str = "",
    content_type: str = "application/xml",
) -> requests.Response:
    config = {
        "params": params,
        "headers": {
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "x-csrf-token": http_request_parameters["csrf_token"],
            "X-sap-adt-sessiontype": http_request_parameters["statefulness"],
            "content-type": content_type,
        },
        "url": url,
        "data": body,
    }

    session = http_request_parameters["session"]
    if method == "POST":
        response = session.post(**config)
    elif method == "GET":
        response = session.get(**config)
    elif method == "PUT":
        response = session.put(**config)
    else:
        raise ValueError(f"Unsupported method: {method}")
    return response