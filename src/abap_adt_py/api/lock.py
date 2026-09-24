from ..http_request import HttpRequestParameters, request
from ..exceptions import ObjectLockedError, error_from_response
from ..response_parsing import find_xml_element_text


def lock(http_request_parameters: HttpRequestParameters, object_uri: str) -> str:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        body="",
        params={"_action": "LOCK", "accessMode": "MODIFY"},
        method="POST",
        # packages reject the lock with 406 unless the result type is requested explicitly
        accept="application/*,application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.lock.result",
    )
    if response.status_code == 200:
        lock_handle = find_xml_element_text(response.text, ".//LOCK_HANDLE")
        return lock_handle
    else:
        # 403 means another user or session holds the lock
        raise error_from_response(
            response,
            f"Failed to lock {object_uri}",
            ObjectLockedError if response.status_code == 403 else None,
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
        raise error_from_response(response, f"Failed to unlock {object_uri}")
