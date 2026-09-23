from ..compat_typing import Optional
from ..http_request import HttpRequestParameters, request, with_transport


def delete(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    lock_handle: str,
    transport: Optional[str] = None,
) -> bool:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        body="",
        params=with_transport({"lockHandle": lock_handle}, transport),
        method="DELETE",
    )
    if response.status_code == 200:
        return True
    else:
        raise Exception(
            f"{response.status_code} Failed to delete {object_uri}.\n{response.text}"
        )