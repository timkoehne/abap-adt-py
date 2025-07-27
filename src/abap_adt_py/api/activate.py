from ..http_request import HttpRequestParameters, request
from ..response_parsing import find_xml_element_attributes, find_xml_elements_attributes


def activate(
    http_request_parameters: HttpRequestParameters, object_name: str, object_uri: str
) -> bool:

    body = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
        <adtcore:objectReference adtcore:uri="{object_uri}" adtcore:name="{object_name}"/>
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
    properties = find_xml_element_attributes(response.text, "chkl:properties")
    if (
        properties["activationExecuted"] == "true"
        or properties["generationExecuted"] == "true"
    ):
        return True
    else:
        msg_elements = find_xml_elements_attributes(response.text, "msg")
        raise Exception(f"{response.status_code} - Activation failed.\n{msg_elements}")
