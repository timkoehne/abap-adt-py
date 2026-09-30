import xml.etree.ElementTree as et
from xml.sax.saxutils import quoteattr

from ..compat_typing import List, Sequence, Tuple, TypedDict
from ..exceptions import ActivationError, error_from_response
from ..http_request import HttpRequestParameters, request
from ..response_parsing import find_xml_element_attributes
from .xml_namespaces import XML_NAMESPACES


class InactiveObject(TypedDict):
    name: str
    type: str
    uri: str
    # the user who changed it
    user: str
    # True if the object is deleted but the deletion isn't activated yet
    deleted: bool
    transport: str


def inactive_objects(http_request_parameters: HttpRequestParameters) -> List[InactiveObject]:
    """The inactive objects of all users."""
    response = request(
        http_request_parameters,
        uri="/sap/bc/adt/activation/inactiveobjects",
        method="GET",
        body="",
        params={},
        accept="application/vnd.sap.adt.inactivectsobjects.v1+xml, application/xml;q=0.8",
    )
    if response.status_code != 200:
        raise error_from_response(response, "Failed to list inactive objects")

    adtcore = "{" + XML_NAMESPACES["adtcore"] + "}"
    ioc = "{" + XML_NAMESPACES["ioc"] + "}"
    objects: List[InactiveObject] = []
    for entry in et.fromstring(response.text).iter(f"{ioc}entry"):
        obj = entry.find(f"{ioc}object")
        ref = obj.find(f"{ioc}ref") if obj is not None else None
        if ref is None:
            continue  # entries with only a transport
        transport = entry.find(f"{ioc}transport/{ioc}ref")
        objects.append(
            {
                "name": ref.get(f"{adtcore}name", ""),
                "type": ref.get(f"{adtcore}type", ""),
                "uri": ref.get(f"{adtcore}uri", ""),
                "user": obj.get(f"{ioc}user", ""),
                "deleted": obj.get(f"{ioc}deleted") == "true",
                "transport": transport.get(f"{adtcore}name", "") if transport is not None else "",
            }
        )
    return objects


def _path(uri: str) -> str:
    return uri.split("#")[0].split("?")[0].rstrip("/").lower()


def _same_object(requested_uri: str, inactive_uri: str) -> bool:
    # parts of an object, e.g. a class include, are listed with their own uri
    requested, inactive = _path(requested_uri), _path(inactive_uri)
    return (
        requested == inactive
        or inactive.startswith(requested + "/")
        or requested.startswith(inactive + "/")
    )


def activate_objects(
    http_request_parameters: HttpRequestParameters,
    objects: Sequence[Tuple[str, str]],
) -> bool:
    """Activate several objects in one request, as (name, uri) pairs.

    Objects that depend on each other, e.g. a CDS root view with a composition and its
    child with an association to parent, can only be activated together.
    Raises ActivationError if any of them is still inactive afterwards.
    """
    if not objects:
        raise ValueError("no objects to activate")

    references = "".join(
        f"<adtcore:objectReference adtcore:uri={quoteattr(uri)} adtcore:name={quoteattr(name)}/>"
        for name, uri in objects
    )
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">{references}</adtcore:objectReferences>"""
    names = ", ".join(name for name, _ in objects)

    response = request(
        http_request_parameters,
        uri="/sap/bc/adt/activation",
        params={"method": "activate", "preauditRequested": "true"},
        body=body,
        method="POST",
        content_type="application/xml",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to activate {names}")

    messages = []
    properties = {}
    if response.text.strip():
        properties = find_xml_element_attributes(response.text, "chkl:properties")
        messages = [
            {
                "type": msg.get("type", ""),
                "text": msg.findtext("shortText/txt", "").strip(),
                "uri": msg.get("href", ""),
                "object": msg.get("objDescr", ""),
            }
            for msg in et.fromstring(response.text).iter("msg")
        ]

    executed = (
        properties.get("activationExecuted") == "true"
        or properties.get("generationExecuted") == "true"
    )
    failed = [] if executed else [name for name, _ in objects]
    if executed:
        # SAP reports an executed activation also when dictionary objects (tables, CDS
        # views, ...) fail to activate, so check what is still inactive
        inactive = inactive_objects(http_request_parameters)
        failed = [
            name
            for name, uri in objects
            if any(_same_object(uri, obj["uri"]) for obj in inactive)
        ]
    if not failed:
        return True

    texts = [m["text"] for m in messages if m["type"] in ("E", "A")] or [
        m["text"] for m in messages
    ]
    # SAP often repeats a message for the source and for the object
    texts = list(dict.fromkeys(t for t in texts if t)) or [
        f"{', '.join(failed)} is still inactive"
    ]
    raise ActivationError(
        f"{response.status_code} - Activation of {', '.join(failed)} failed: "
        + "; ".join(texts),
        messages=messages,
        status_code=response.status_code,
        sap_message="; ".join(texts),
        response_text=response.text,
    )


def activate(
    http_request_parameters: HttpRequestParameters, object_name: str, object_uri: str
) -> bool:
    return activate_objects(http_request_parameters, [(object_name, object_uri)])
