import html
import re

from ..http_request import HttpRequestParameters, request


def _error_message(page: str) -> str:
    # runtime errors come back as an HTML error page with the message in <span id="msgText">
    message = re.search(r'<span id="msgText">(.*?)</span>', page, re.S)
    if message is None:
        return page
    return re.sub(r"\s+", " ", html.unescape(message.group(1))).strip()


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
        raise Exception(
            f"{response.status_code} - Running {class_name} failed: {_error_message(response.text)}"
        )
