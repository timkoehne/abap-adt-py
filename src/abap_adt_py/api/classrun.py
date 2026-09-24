from ..exceptions import ClassRunError, error_from_response
from ..http_request import HttpRequestParameters, request


def run_class(http_request_parameters: HttpRequestParameters, class_name: str) -> str:
    """Run a class that implements IF_OO_ADT_CLASSRUN and return its console output.

    If the class doesn't exist or doesn't implement the interface, SAP returns
    an explanation as the output instead of an error.
    """

    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/oo/classrun/{class_name.upper()}",
        method="POST",
        body="",
        params={},
        accept="text/plain",
    )

    if response.status_code == 200:
        return response.text
    else:
        raise error_from_response(
            response, f"Running {class_name} failed", ClassRunError
        )
