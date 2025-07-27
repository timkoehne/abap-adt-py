from ..http_request import HttpRequestParameters, request
from ..response_parsing import find_xml_element_text


def lock(http_request_parameters: HttpRequestParameters, object_uri: str) -> str:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        body="",
        params={"_action": "LOCK", "accessMode": "MODIFY"},
        method="POST",
    )
    if response.status_code == 200:
        lock_handle = find_xml_element_text(response.text, ".//LOCK_HANDLE")
        return lock_handle
    else:
        raise Exception(
            f"{response.status_code} Failed to lock {object_uri}.\n{response.text}"
        )


def unlock(
    http_request_parameters: HttpRequestParameters, object_uri: str, lock_handle: str
) -> bool:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        body="",
        params={"_action": "UNLOCK", "lockHandle": lock_handle},
        method="POST",
        content_type="plain/text; charset=utf-8",
    )
    if response.status_code == 200:
        return True
    else:
        raise Exception(
            f"{response.status_code} Failed to unlock {object_uri}\n{response.text}"
        )
