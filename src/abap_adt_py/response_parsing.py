from xml.etree import ElementTree as et
from .compat_typing import Optional, Dict, List
from .api.xml_namespaces import XML_NAMESPACES


def _strip_namespace(name: str) -> str:
    if name.startswith("{"):
        return name.split("}", 1)[1]
    if ":" in name:
        return name.split(":", 1)[1]
    return name


def _et_to_attributes_dict(element: Optional[et.Element]) -> Dict[str, str]:
    cleaned = (
        {_strip_namespace(key): value for key, value in element.attrib.items()}
        if element is not None
        else {}
    )
    return cleaned


def find_xml_elements_attributes(xml_text: str, tag_name: str) -> List[Dict[str, str]]:
    root = et.fromstring(xml_text)
    elements = root.findall(tag_name, XML_NAMESPACES)
    processed_elements = []
    for element in elements:
        cleaned = _et_to_attributes_dict(element)
        processed_elements.append(cleaned)
    return processed_elements


def find_xml_element_attributes(xml_text: str, tag_name: str) -> Dict[str, str]:
    root = et.fromstring(xml_text)
    element = root.find(tag_name, XML_NAMESPACES)
    element = _et_to_attributes_dict(element)
    return element


def find_xml_element_text(xml_text: str, tag_name: str):
    root = et.fromstring(xml_text)
    el = root.find(tag_name, XML_NAMESPACES)
    return "".join(el.itertext()).strip() if el is not None else ""
