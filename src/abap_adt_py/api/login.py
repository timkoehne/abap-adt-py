from ..exceptions import AuthenticationError, error_from_response
from ..http_request import HttpRequestParameters, request


def login(http_request_parameters: HttpRequestParameters) -> str:

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/compatibility/graph",
        method="GET",
        body="",
        params={},
    )

    if response.status_code == 200:
        csrf_token = response.headers.get("x-csrf-token")
        if csrf_token is None:
            raise AuthenticationError(
                "Login failed: CSRF token not found in response headers.",
                status_code=response.status_code,
                response_text=response.text,
            )
        return csrf_token
    else:
        raise error_from_response(response, "Login failed", AuthenticationError)
