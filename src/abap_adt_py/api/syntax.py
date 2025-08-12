import base64
import xml.etree.ElementTree as et
from ..compat_typing import TypedDict, Literal, NotRequired
from ..http_request import HttpRequestParameters, request
from .xml_namespaces import XML_NAMESPACES


class SyntaxCheckResult(TypedDict):
    uri: str
    line: NotRequired[int]
    offset: NotRequired[int]
    type: str
    short_text: str


def _parse_syntax_check_response(response_text: str) -> list[SyntaxCheckResult]:
    root = et.fromstring(response_text)
    messages = []
    for msg in root.findall(".//chkrun:checkMessage", XML_NAMESPACES):
        uri: str = msg.get(f'{{{XML_NAMESPACES["chkrun"]}}}uri', "")

        if "#start=" in uri:
            line, offset = uri[uri.index("#start=") + 7 :].split(",")
            line, offset = int(line), int(offset)
            uri = uri[: uri.index("#start=")]
        else:
            line, offset = None, None

        uri = uri.removesuffix("/source/main")

        type = msg.get(f'{{{XML_NAMESPACES["chkrun"]}}}type', "")
        short_text = msg.get(f'{{{XML_NAMESPACES["chkrun"]}}}shortText', "")

        message: SyntaxCheckResult = {
            "uri": uri,
            "type": type,
            "short_text": short_text,
        }

        if line and offset:
            message["line"] = line
            message["offset"] = offset

        messages.append(message)
    return messages


def syntax_check(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    include_uri: str,
    source_code: str,
    version: Literal["active", "inactive"] = "active",
) -> list[SyntaxCheckResult]:
    body = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <chkrun:checkObjectList xmlns:chkrun="http://www.sap.com/adt/checkrun" xmlns:adtcore="http://www.sap.com/adt/core">
    <chkrun:checkObject adtcore:uri="{object_uri}" chkrun:version="{version}">
        <chkrun:artifacts>
        <chkrun:artifact chkrun:contentType="text/plain; charset=utf-8" chkrun:uri="{include_uri}">
            <chkrun:content>{base64.b64encode(source_code.encode("utf-8")).decode("utf-8")}</chkrun:content>
        </chkrun:artifact>
        </chkrun:artifacts>
    </chkrun:checkObject>
    </chkrun:checkObjectList>
    """

    response = request(
        http_request_parameters,
        uri="/sap/bc/adt/checkruns?reporters=abapCheckRun",
        params={},
        body=body,
        method="POST",
        content_type="application/*",
    )
    if 200 <= response.status_code < 300:
        messages = _parse_syntax_check_response(response.text)
        return messages
    else:
        raise Exception(
            f"{response.status_code} - Failed to check syntax for {object_uri}\n{response.text}"
        )
