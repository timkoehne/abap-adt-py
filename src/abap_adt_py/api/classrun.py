import re

from ..exceptions import ClassRunError, error_from_response
from ..http_request import HttpRequestParameters, request


NOT_RUNNABLE = "For console output, a class must implement IF_OO_ADT_CLASSRUN"
MISSING = re.compile(r"Object \S+ of type CLAS does not exist")


def run_class(http_request_parameters: HttpRequestParameters, class_name: str) -> str:
    """Run a class that implements IF_OO_ADT_CLASSRUN and return its console output.

    SAP answers a class that doesn't exist, isn't active or doesn't implement the
    interface with an explanation as a normal output; that raises ClassRunError.
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
        output = response.text.lstrip()
        reason = None
        if output.startswith(NOT_RUNNABLE):
            reason = "the class is not active or does not implement IF_OO_ADT_CLASSRUN."
        elif MISSING.match(output):
            reason = "the class does not exist."
        if reason:
            raise ClassRunError(
                f"Running {class_name} failed: {reason}",
                status_code=response.status_code,
                response_text=response.text,
            )
        return response.text
    else:
        raise error_from_response(
            response, f"Running {class_name} failed", ClassRunError
        )
