import xml.etree.ElementTree as et
from xml.sax.saxutils import quoteattr

from ..exceptions import ActivationError, error_from_response
from ..http_request import HttpRequestParameters, request
from ..response_parsing import find_xml_element_attributes


def activate(
    http_request_parameters: HttpRequestParameters, object_name: str, object_uri: str
) -> bool:

    body = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
        <adtcore:objectReference adtcore:uri={quoteattr(object_uri)} adtcore:name={quoteattr(object_name)}/>
    </adtcore:objectReferences>
    """

    response = request(
        http_request_parameters,
        uri="/sap/bc/adt/activation",
        params={"method": "activate", "preauditRequested": "true"},
        body=body,
        method="POST",
        content_type="application/xml",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to activate {object_name}")

    properties = find_xml_element_attributes(response.text, "chkl:properties")
    if (
        properties.get("activationExecuted") == "true"
        or properties.get("generationExecuted") == "true"
    ):
        return True

    messages = [
        {
            "type": msg.get("type", ""),
            "text": msg.findtext("shortText/txt", "").strip(),
            "uri": msg.get("href", ""),
            "object": msg.get("objDescr", ""),
        }
        for msg in et.fromstring(response.text).iter("msg")
    ]
    errors = [m["text"] for m in messages if m["type"] == "E"] or [
        m["text"] for m in messages
    ]
    raise ActivationError(
        f"{response.status_code} - Activation of {object_name} failed: "
        + "; ".join(errors),
        messages=messages,
        status_code=response.status_code,
        sap_message="; ".join(errors),
        response_text=response.text,
    )
