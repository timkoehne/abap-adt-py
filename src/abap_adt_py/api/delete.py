from ..http_request import HttpRequestParameters, request


def delete(http_request_parameters: HttpRequestParameters, object_uri: str, lock_handle: str) -> bool:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        body="",
        params={"lockHandle": lock_handle},
        method="DELETE",
    )
    if response.status_code == 200:
        return True
    else:
        raise Exception(
            f"{response.status_code} Failed to delete {object_uri}.\n{response.text}"
        )