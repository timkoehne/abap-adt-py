import xml.etree.ElementTree as et
from ..compat_typing import TypedDict, List
from ..http_request import HttpRequestParameters, request
from .xml_namespaces import XML_NAMESPACES


class LinkInfo(TypedDict):
    rel: str
    href: str


class ComponentInfo(TypedDict, total=False):
    name: str
    type: str
    links: List[LinkInfo]
    level: str
    clif_name: str
    visibility: str


class ClassStructureResult(TypedDict):
    name: str
    xml_base: str
    visibility: str
    final: bool
    type: str
    links: List[LinkInfo]
    components: List[ComponentInfo]


def _parse_class_structure_response(xml_content: str) -> ClassStructureResult:
    root = et.fromstring(xml_content)

    all_attrs = root.attrib

    class_info: ClassStructureResult = {
        "name": "",
        "xml_base": "",
        "visibility": "",
        "final": False,
        "type": "",
        "links": [],
        "components": [],
    }

    attr_mapping = {
        "{http://www.sap.com/adt/core}name": "name",
        "{http://www.w3.org/XML/1998/namespace}base": "xml_base",
        "visibility": "visibility",
        "{http://www.sap.com/adt/core}type": "type",
    }
    for xml_attr, struct_key in attr_mapping.items():
        if xml_attr in all_attrs:
            if struct_key == "final":
                class_info[struct_key] = all_attrs[xml_attr] == "true"
            else:
                class_info[struct_key] = all_attrs[xml_attr]

    if "final" in all_attrs:
        class_info["final"] = all_attrs["final"] == "true"

    for link in root.findall("atom:link", XML_NAMESPACES):
        class_info["links"].append(
            {"rel": link.get("rel", ""), "href": link.get("href", "")}
        )

    for element in root.findall(".//abapsource:objectStructureElement", XML_NAMESPACES):
        all_element_attrs = element.attrib

        element_info: ComponentInfo = {
            "name": "",
            "type": "",
            "links": [],
        }
        for attr_name, attr_value in all_element_attrs.items():
            if attr_value in ["true", "false"]:
                element_info[attr_name] = attr_value == "true"
            else:
                if attr_name in attr_mapping:
                    attr_name = attr_mapping[attr_name]
                element_info[attr_name] = attr_value

        for link in element.findall("atom:link", XML_NAMESPACES):
            element_info["links"].append(
                {"rel": link.get("rel", ""), "href": link.get("href", "")}
            )
        class_info["components"].append(element_info)

    return class_info


def object_structure(http_request_parameters: HttpRequestParameters, object_uri: str):
    response = request(
        http_request_parameters,
        uri=f"{object_uri}/objectstructure",
        params={"version": "active", "withShortDescriptions": True},
        body="",
        method="GET",
        content_type="application/*",
    )
    if 200 <= response.status_code < 300:
        content = _parse_class_structure_response(response.text)
        return content
    else:
        raise Exception(
            f"{response.status_code} - Failed get object structure for {object_uri}\n{response.text}"
        )
