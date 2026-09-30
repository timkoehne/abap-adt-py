import xml.etree.ElementTree as et
from xml.sax.saxutils import escape, quoteattr

from ..compat_typing import Optional, Sequence
from ..http_request import HttpRequestParameters, request, with_transport
from ..exceptions import AdtError, error_from_response
from .xml_namespaces import XML_NAMESPACES


def delete(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    lock_handle: str,
    transport: Optional[str] = None,
) -> bool:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        body="",
        params=with_transport({"lockHandle": lock_handle}, transport),
        method="DELETE",
    )
    if response.status_code == 200:
        return True
    else:
        raise error_from_response(response, f"Failed to delete {object_uri}")


def delete_objects(
    http_request_parameters: HttpRequestParameters,
    object_uris: Sequence[str],
    transport: Optional[str] = None,
) -> bool:
    """Delete several objects in one request, without locking them first.

    Objects that use each other, e.g. a CDS root view and its composition child,
    can only be deleted together. Raises AdtError if any object wasn't deleted.
    """
    if not object_uris:
        raise ValueError("no objects to delete")

    transport_number = (
        f"<del:transportNumber>{escape(transport)}</del:transportNumber>" if transport else ""
    )
    objects = "".join(
        f"<del:object adtcore:uri={quoteattr(uri)}>{transport_number}</del:object>"
        for uri in object_uris
    )
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <del:deletionRequest xmlns:del="http://www.sap.com/adt/deletion" xmlns:adtcore="http://www.sap.com/adt/core">{objects}</del:deletionRequest>"""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/deletion/delete",
        method="POST",
        body=body,
        params={},
        content_type="application/vnd.sap.adt.deletion.request.v1+xml",
        accept="application/vnd.sap.adt.deletion.response.v1+xml",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to delete {', '.join(object_uris)}")

    adtcore = "{" + XML_NAMESPACES["adtcore"] + "}"
    ns = "{http://www.sap.com/adt/deletion}"
    # the result also lists objects deleted along with the requested ones
    failed = [
        "{}: {}".format(
            obj.get(f"{adtcore}name") or obj.get(f"{adtcore}uri"),
            "; ".join(
                t.strip() for t in (m.findtext(f"{ns}text") or "" for m in obj.iter(f"{ns}message")) if t.strip()
            )
            or "not deleted",
        )
        for obj in et.fromstring(response.text).iter(f"{ns}object")
        if obj.get(f"{ns}isDeleted") != "true"
    ]
    if failed:
        raise AdtError(
            f"{response.status_code} - Failed to delete " + ", ".join(failed),
            status_code=response.status_code,
            sap_message=", ".join(failed),
            response_text=response.text,
        )
    return True
