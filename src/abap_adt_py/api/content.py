from ..compat_typing import Literal
from ..http_request import HttpRequestParameters, request


def get_object_source(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    version: Literal["active", "inactive"] = "active",
) -> str:

    params = {}
    if version:
        params["version"] = version

    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        method="GET",
        body="",
        params=params,
        content_type="application/xml",
    )

    if response.status_code == 200:
        return response.text
    else:
        raise Exception(
            f"{response.status_code} - Failed to get object source.\n{response.text}"
        )


def set_object_source(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    source_code: str,
    lock_handle: str,
) -> bool:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        method="PUT",
        body=source_code,
        params={"lockHandle": lock_handle},
        content_type="text/plain; charset=utf-8",
    )

    if response.status_code == 200:
        return True
    else:
        raise Exception(
            f"{response.status_code} - Failed to set source code for {object_uri}\n{response.text}"
        )
