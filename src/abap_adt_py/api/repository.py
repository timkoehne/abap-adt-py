import xml.etree.ElementTree as et

from ..compat_typing import Optional, TypedDict, List
from ..http_request import HttpRequestParameters, request
from ..exceptions import error_from_response
from .xml_namespaces import XML_NAMESPACES


class RepositoryNode(TypedDict):
    object_type: str
    object_name: str
    tech_name: str
    object_uri: str
    object_vit_uri: str
    expandable: bool
    node_id: str
    description: str


class ObjectCategory(TypedDict):
    category: str
    label: str


class ObjectTypeInfo(TypedDict):
    object_type: str
    category: str
    label: str
    node_id: str


class NodeStructure(TypedDict):
    nodes: List[RepositoryNode]
    categories: List[ObjectCategory]
    object_types: List[ObjectTypeInfo]


class PackageInfo(TypedDict):
    name: str
    description: str
    uri: str


def _text(element: et.Element, tag: str) -> str:
    return element.findtext(tag) or ""


def _parse_node_structure(xml_text: str) -> NodeStructure:
    result: NodeStructure = {"nodes": [], "categories": [], "object_types": []}
    # the server answers with an empty body for unknown parents or node keys
    if not xml_text.strip():
        return result
    root = et.fromstring(xml_text)
    data = root.find("asx:values/DATA", XML_NAMESPACES)
    if data is None:
        return result

    for node in data.findall("TREE_CONTENT/SEU_ADT_REPOSITORY_OBJ_NODE"):
        result["nodes"].append(
            {
                "object_type": _text(node, "OBJECT_TYPE"),
                "object_name": _text(node, "OBJECT_NAME"),
                "tech_name": _text(node, "TECH_NAME"),
                "object_uri": _text(node, "OBJECT_URI"),
                "object_vit_uri": _text(node, "OBJECT_VIT_URI"),
                "expandable": _text(node, "EXPANDABLE") == "X",
                "node_id": _text(node, "NODE_ID"),
                "description": _text(node, "DESCRIPTION"),
            }
        )

    for category in data.findall("CATEGORIES/SEU_ADT_OBJECT_CATEGORY_INFO"):
        result["categories"].append(
            {
                "category": _text(category, "CATEGORY"),
                "label": _text(category, "CATEGORY_LABEL"),
            }
        )

    for object_type in data.findall("OBJECT_TYPES/SEU_ADT_OBJECT_TYPE_INFO"):
        result["object_types"].append(
            {
                "object_type": _text(object_type, "OBJECT_TYPE"),
                "category": _text(object_type, "CATEGORY_TAG"),
                "label": _text(object_type, "OBJECT_TYPE_LABEL"),
                "node_id": _text(object_type, "NODE_ID"),
            }
        )

    return result


def node_contents(
    http_request_parameters: HttpRequestParameters,
    parent_type: str,
    parent_name: str,
    node_key: Optional[str] = None,
) -> NodeStructure:
    """Read one level of the repository tree below an object (e.g. a package).

    Without node_key the result contains group nodes (e.g. DEVC/OC "Classes")
    whose node_id can be passed as node_key to list the objects in that group.
    """

    body = ""
    if node_key:
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
        <asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">
            <asx:values><DATA><TV_NODEKEY>{node_key}</TV_NODEKEY></DATA></asx:values>
        </asx:abap>"""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/nodestructure",
        method="POST",
        body=body,
        params={
            "parent_type": parent_type,
            "parent_name": parent_name,
            "withShortDescriptions": "true",
        },
    )

    if response.status_code == 200:
        return _parse_node_structure(response.text)
    else:
        raise error_from_response(
            response, f"Failed to read node structure of {parent_type} {parent_name}"
        )


def package_contents(
    http_request_parameters: HttpRequestParameters,
    package: str,
    recursive: bool = False,
) -> List[RepositoryNode]:
    """List all objects of a package. Subpackages are included as DEVC/K nodes."""

    structure = node_contents(http_request_parameters, "DEVC/K", package)

    objects: List[RepositoryNode] = []
    seen = set()

    def add(node: RepositoryNode):
        key = (node["object_type"], node["object_name"])
        if node["object_name"] and key not in seen:
            seen.add(key)
            objects.append(node)

    for node in structure["nodes"]:
        is_group = not node["object_name"] and node["node_id"]
        # subpackages are already listed inline, so their group needs no expansion
        if is_group and node["object_type"] != "DEVC/K":
            group = node_contents(
                http_request_parameters, "DEVC/K", package, node["node_id"]
            )
            for child in group["nodes"]:
                add(child)
        else:
            add(node)

    if recursive:
        for subpackage in [o for o in objects if o["object_type"] == "DEVC/K"]:
            for node in package_contents(
                http_request_parameters, subpackage["object_name"], recursive=True
            ):
                add(node)

    return objects


def object_package_path(
    http_request_parameters: HttpRequestParameters, object_uri: str
) -> List[PackageInfo]:
    """Return the package hierarchy of an object, from the top-level package down."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/informationsystem/objectproperties/values",
        method="GET",
        body="",
        params={"uri": object_uri, "facet": "package"},
    )

    if response.status_code != 200:
        raise error_from_response(response, f"Failed to get package of {object_uri}")

    root = et.fromstring(response.text)
    packages: List[PackageInfo] = []
    for prop in root.findall("opr:property", XML_NAMESPACES):
        if prop.get("facet") != "PACKAGE":
            continue
        link = prop.find("atom:link", XML_NAMESPACES)
        packages.append(
            {
                "name": prop.get("name", ""),
                "description": prop.get("text", ""),
                "uri": link.get("href", "") if link is not None else "",
            }
        )
    return packages
