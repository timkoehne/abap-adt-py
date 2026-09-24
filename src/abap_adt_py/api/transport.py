import xml.etree.ElementTree as et
from xml.sax.saxutils import escape

from ..compat_typing import List, Optional, TypedDict
from ..http_request import HttpRequestParameters, request
from ..exceptions import TransportError, error_from_response
from .xml_namespaces import XML_NAMESPACES


class TransportRequestHeader(TypedDict):
    number: str
    type: str
    status: str
    owner: str
    description: str
    target: str


class TransportLock(TypedDict):
    pgmid: str
    object_type: str
    object_name: str
    request: TransportRequestHeader


class TransportInfo(TypedDict):
    # True if changes to the object have to be recorded in a transport request
    recording: bool
    # True if the object is already locked in a request, which then has to be used
    existing_request_only: bool
    package: str
    requests: List[TransportRequestHeader]
    locks: List[TransportLock]


class TransportObject(TypedDict):
    pgmid: str
    type: str
    name: str
    wbtype: str
    description: str


class TransportTask(TypedDict):
    number: str
    owner: str
    description: str
    type: str
    status: str
    objects: List[TransportObject]


class TransportRequest(TypedDict):
    number: str
    owner: str
    description: str
    type: str
    status: str
    target: str
    tasks: List[TransportTask]


def _asx_body(fields: dict) -> str:
    data = "".join(
        f"<{key}>{escape(value)}</{key}>" if value else f"<{key}/>"
        for key, value in fields.items()
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
        <asx:values><DATA>{data}</DATA></asx:values>
    </asx:abap>"""


def _parse_request_header(header: et.Element) -> TransportRequestHeader:
    return {
        "number": header.findtext("TRKORR") or "",
        "type": header.findtext("TRFUNCTION") or "",
        "status": header.findtext("TRSTATUS") or "",
        "owner": header.findtext("AS4USER") or "",
        "description": header.findtext("AS4TEXT") or "",
        "target": header.findtext("TARSYSTEM") or "",
    }


def _parse_transport_info(xml_text: str) -> TransportInfo:
    root = et.fromstring(xml_text)
    data = root.find("asx:values/DATA", XML_NAMESPACES)
    if data is None:
        raise TransportError(
            "Unexpected transport check response", response_text=xml_text
        )

    locks: List[TransportLock] = []
    for lock in data.findall("LOCKS/CTS_OBJECT_LOCK"):
        header = lock.find("LOCK_HOLDER/REQ_HEADER")
        if header is None:
            continue
        locks.append(
            {
                "pgmid": lock.findtext("OBJECT_KEY/PGMID") or "",
                "object_type": lock.findtext("OBJECT_KEY/OBJECT") or "",
                "object_name": lock.findtext("OBJECT_KEY/OBJ_NAME") or "",
                "request": _parse_request_header(header),
            }
        )

    return {
        "recording": data.findtext("RECORDING") == "X",
        "existing_request_only": data.findtext("EXISTING_REQ_ONLY") == "X",
        "package": data.findtext("TADIRDEVC") or data.findtext("DEVCLASS") or "",
        "requests": [
            _parse_request_header(header)
            for header in data.findall("REQUESTS/CTS_REQUEST/REQ_HEADER")
        ],
        "locks": locks,
    }


def transport_info(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    package: str = "",
    operation: str = "I",
) -> TransportInfo:

    body = _asx_body(
        {
            "PGMID": "",
            "OBJECT": "",
            "OBJECTNAME": "",
            "DEVCLASS": package,
            "SUPER_PACKAGE": "",
            "OPERATION": operation,
            "URI": object_uri,
        }
    )

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/cts/transportchecks",
        method="POST",
        body=body,
        params={},
        content_type="application/vnd.sap.as+xml; charset=UTF-8; dataname=com.sap.adt.transport.service.checkData",
        accept="application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.transport.service.checkData",
    )

    if response.status_code == 200:
        return _parse_transport_info(response.text)
    else:
        raise error_from_response(
            response, f"Failed to check transport for {object_uri}", TransportError
        )


def create_transport(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    description: str,
    package: str,
) -> str:

    body = _asx_body(
        {
            "OPERATION": "I",
            "DEVCLASS": package,
            "REQUEST_TEXT": description,
            "REF": object_uri,
        }
    )

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/cts/transports",
        method="POST",
        body=body,
        params={},
        content_type="application/vnd.sap.as+xml; charset=UTF-8; dataname=com.sap.adt.CreateCorrectionRequest",
        accept="text/plain",
    )

    if response.status_code == 200:
        # the response is the request's object record, e.g. /com.sap.cts/object_record/A4HK900146
        return response.text.strip().split("/")[-1]
    else:
        raise error_from_response(
            response, "Failed to create transport request", TransportError
        )


def _attr(element: et.Element, name: str) -> str:
    return element.get(f"{{{XML_NAMESPACES['tm']}}}{name}", "")


def list_transports(
    http_request_parameters: HttpRequestParameters, user: str
) -> List[TransportRequest]:
    """List the modifiable transport requests of a user, including their tasks and objects."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/cts/transportrequests",
        method="GET",
        body="",
        params={"user": user, "requestStatus": "D"},
        accept="application/vnd.sap.adt.transportorganizertree.v1+xml",
    )

    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to list transport requests of {user}", TransportError
        )

    root = et.fromstring(response.text)
    requests: List[TransportRequest] = []
    for req in root.iterfind(".//tm:request", XML_NAMESPACES):
        tasks: List[TransportTask] = []
        for task in req.findall("tm:task", XML_NAMESPACES):
            tasks.append(
                {
                    "number": _attr(task, "number"),
                    "owner": _attr(task, "owner"),
                    "description": _attr(task, "desc"),
                    "type": _attr(task, "type"),
                    "status": _attr(task, "status"),
                    "objects": [
                        {
                            "pgmid": _attr(obj, "pgmid"),
                            "type": _attr(obj, "type"),
                            "name": _attr(obj, "name"),
                            "wbtype": _attr(obj, "wbtype"),
                            "description": _attr(obj, "obj_desc"),
                        }
                        for obj in task.findall("tm:abap_object", XML_NAMESPACES)
                    ],
                }
            )
        requests.append(
            {
                "number": _attr(req, "number"),
                "owner": _attr(req, "owner"),
                "description": _attr(req, "desc"),
                "type": _attr(req, "type"),
                "status": _attr(req, "status"),
                "target": _attr(req, "target"),
                "tasks": tasks,
            }
        )
    return requests


def _read_request(
    http_request_parameters: HttpRequestParameters, transport: str
) -> et.Element:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/cts/transportrequests/{transport}",
        method="GET",
        body="",
        params={},
        accept="application/vnd.sap.adt.transportorganizer.v1+xml",
    )
    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to read {transport}", TransportError
        )
    return et.fromstring(response.text)


def _status(root: et.Element, transport: str) -> str:
    for element in root.iter():
        if (
            element.tag
            in (f"{{{XML_NAMESPACES['tm']}}}request", f"{{{XML_NAMESPACES['tm']}}}task")
            and _attr(element, "number") == transport
        ):
            return _attr(element, "status")
    return ""


def _release(http_request_parameters: HttpRequestParameters, transport: str):
    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/cts/transportrequests/{transport}/newreleasejobs",
        method="POST",
        body="",
        params={},
        accept="application/vnd.sap.adt.transportorganizer.v1+xml",
    )

    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to release {transport}", TransportError
        )

    chkrun = XML_NAMESPACES["chkrun"]
    report = et.fromstring(response.text).find(".//chkrun:checkReport", XML_NAMESPACES)
    if report is None or report.get(f"{{{chkrun}}}status") != "released":
        # the release can succeed even if a later step such as the export reports an error
        root = _read_request(http_request_parameters, transport)
        if _status(root, transport) == "R":
            return
        messages = (
            [
                message.get(f"{{{chkrun}}}shortText", "")
                for message in report.iterfind(".//chkrun:checkMessage", XML_NAMESPACES)
            ]
            if report is not None
            else [response.text]
        )
        raise TransportError(
            f"Release of {transport} failed: " + "; ".join(messages),
            status_code=response.status_code,
            sap_message="; ".join(messages),
            response_text=response.text,
        )


def release_transport(
    http_request_parameters: HttpRequestParameters, transport: str
) -> bool:

    root = _read_request(http_request_parameters, transport)
    tasks = [
        _attr(task, "number")
        for task in root.iterfind(".//tm:task", XML_NAMESPACES)
        if _attr(task, "status") == "D" and _attr(task, "number") != transport
    ]
    for task in tasks:
        _release(http_request_parameters, task)
    _release(http_request_parameters, transport)
    return True


def delete_transport(
    http_request_parameters: HttpRequestParameters, transport: str
) -> bool:
    """Delete a modifiable transport request or task."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/cts/transportrequests/{transport}",
        method="DELETE",
        body="",
        params={},
    )

    if 200 <= response.status_code < 300:
        return True
    else:
        raise error_from_response(
            response, f"Failed to delete {transport}", TransportError
        )
