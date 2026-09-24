"""Code navigation: go to definition, where-used list and code completion.

Positions follow SAP's convention: lines start at 1, columns at 0.
"""

import re
import xml.etree.ElementTree as et
from xml.sax.saxutils import escape

from ..compat_typing import Dict, List, Optional, TypedDict
from ..http_request import HttpRequestParameters, request
from ..exceptions import error_from_response
from .xml_namespaces import XML_NAMESPACES


class SourceLocation(TypedDict):
    uri: str
    line: Optional[int]
    column: Optional[int]


class Usage(TypedDict):
    # the object containing the usage, e.g. the program calling a method
    object_name: str
    object_type: str
    package: str
    object_uri: str
    # part of the object the usage is in, e.g. the method of a class, or ""
    element: str
    # full location as reported by SAP, "" if SAP has no source position
    location: str
    # position of the usage. Inside class methods SAP reports it relative to the method
    line: Optional[int]
    column: Optional[int]
    # the source line containing the usage
    code: str
    # e.g. "Usage Kind: direct usage, read access"
    usage: str


class CompletionProposal(TypedDict):
    identifier: str
    # SAP's category code, e.g. 1 for data objects, 3 for methods, 52 for keywords
    kind: int
    # number of characters before the cursor the proposal replaces
    prefix_length: int


def _ns(prefix: str, name: str) -> str:
    return f"{{{XML_NAMESPACES[prefix]}}}{name}"


def _parse_location(uri: str) -> SourceLocation:
    position = re.search(r"start=(\d+),(\d+)", uri)
    return {
        "uri": uri.split("#")[0],
        "line": int(position.group(1)) if position else None,
        "column": int(position.group(2)) if position else None,
    }


def find_definition(
    http_request_parameters: HttpRequestParameters,
    source_uri: str,
    source: str,
    line: int,
    column: int,
) -> Optional[SourceLocation]:
    """Find where the identifier at line/column of source is defined.

    source is the current code of source_uri (e.g. .../source/main) and may be unsaved.
    Returns None if there is nothing to navigate to at that position.
    """

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/navigation/target",
        method="POST",
        body=source,
        params={
            "uri": f"{source_uri}#start={line},{column};end={line},{column}",
            "filter": "definition",
        },
        content_type="text/plain; charset=utf-8",
        accept="application/xml",
    )

    if response.status_code == 400 and "NavigationFailure" in response.text:
        return None
    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to find definition at {source_uri} {line},{column}"
        )
    if not response.text.strip():
        return None

    target = et.fromstring(response.text).get(_ns("adtcore", "uri"), "")
    return _parse_location(target) if target else None


def _usage_references(
    http_request_parameters: HttpRequestParameters, uri: str
) -> et.Element:
    body = """<?xml version="1.0" encoding="UTF-8"?>
    <usagereferences:usageReferenceRequest xmlns:usagereferences="http://www.sap.com/adt/ris/usageReferences">
        <usagereferences:affectedObjects/>
    </usagereferences:usageReferenceRequest>"""
    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/informationsystem/usageReferences",
        method="POST",
        body=body,
        params={"uri": uri},
        content_type="application/*",
        accept="application/*",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to get where-used list of {uri}")
    return et.fromstring(response.text)


def _usage_snippets(
    http_request_parameters: HttpRequestParameters, identifiers: List[str]
) -> Dict[str, List[et.Element]]:
    requested = "".join(
        f'<usagereferences:objectIdentifier optional="false">{escape(identifier)}</usagereferences:objectIdentifier>'
        for identifier in identifiers
    )
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <usagereferences:usageSnippetRequest xmlns:usagereferences="http://www.sap.com/adt/ris/usageReferences">
        <usagereferences:objectIdentifiers>{requested}</usagereferences:objectIdentifiers>
        <usagereferences:affectedObjects/>
    </usagereferences:usageSnippetRequest>"""
    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/informationsystem/usageSnippets",
        method="POST",
        body=body,
        params={},
        content_type="application/*",
        accept="application/*",
    )
    if response.status_code != 200:
        raise error_from_response(response, "Failed to get where-used code snippets")

    snippets: Dict[str, List[et.Element]] = {}
    root = et.fromstring(response.text)
    for obj in root.iterfind(".//usagereferences:codeSnippetObject", XML_NAMESPACES):
        snippets[obj.findtext("objectIdentifier", "")] = obj.findall(
            "usagereferences:codeSnippets/usagereferences:codeSnippet", XML_NAMESPACES
        )
    return snippets


def where_used(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    line: Optional[int] = None,
    column: Optional[int] = None,
) -> List[Usage]:
    """List the usages of an object, one entry per usage.

    With line and column, object_uri must be a source (e.g. .../source/main) and the
    usages of the element at that position are listed, e.g. of a single method.
    """

    uri = object_uri if line is None else f"{object_uri}#start={line},{column or 0}"
    root = _usage_references(http_request_parameters, uri)

    nodes = {}
    for node in root.iterfind(".//usagereferences:referencedObject", XML_NAMESPACES):
        nodes[node.get("uri", "")] = node

    def describe(node: et.Element) -> Dict[str, str]:
        """Name, type and package of the repository object a node belongs to."""
        element = ""
        current: Optional[et.Element] = node
        while current is not None:
            adt_object = current.find("usagereferences:adtObject", XML_NAMESPACES)
            if adt_object is not None and adt_object.get(_ns("adtcore", "type")):
                package = adt_object.find("adtcore:packageRef", XML_NAMESPACES)
                return {
                    "object_name": adt_object.get(_ns("adtcore", "name"), ""),
                    "object_type": adt_object.get(_ns("adtcore", "type"), ""),
                    "package": (
                        package.get(_ns("adtcore", "name"), "")
                        if package is not None
                        else ""
                    ),
                    "object_uri": current.get("uri", ""),
                    "element": element,
                }
            if adt_object is not None and not element:
                element = adt_object.get(_ns("adtcore", "name"), "")
            current = nodes.get(current.get("parentUri", ""))
        return {
            "object_name": "",
            "object_type": "",
            "package": "",
            "object_uri": node.get("uri", ""),
            "element": element,
        }

    # nodes with usage information are the usages, the others (packages) only group them
    used_in = [node for node in nodes.values() if node.get("usageInformation")]
    identifiers = [node.findtext("objectIdentifier", "") for node in used_in]
    snippets = (
        _usage_snippets(http_request_parameters, [i for i in identifiers if i])
        if any(identifiers)
        else {}
    )

    usages: List[Usage] = []
    for node, identifier in zip(used_in, identifiers):
        info = describe(node)
        found = snippets.get(identifier, [])
        if not found:
            usages.append(
                {
                    **info,
                    "location": "",
                    "line": None,
                    "column": None,
                    "code": "",
                    "usage": "",
                }
            )
        for snippet in found:
            location = snippet.get("uri", "")
            position = _parse_location(location)
            usages.append(
                {
                    **info,
                    "location": location,
                    "line": position["line"],
                    "column": position["column"],
                    "code": snippet.findtext("content", "").strip(),
                    "usage": snippet.findtext("description", "").split("\n")[0].strip(),
                }
            )
    return usages


def code_completion(
    http_request_parameters: HttpRequestParameters,
    source_uri: str,
    source: str,
    line: int,
    column: int,
) -> List[CompletionProposal]:
    """Code completion proposals for the cursor at line/column of source (may be unsaved)."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/abapsource/codecompletion/proposal",
        method="POST",
        body=source,
        params={
            "uri": f"{source_uri}#start={line},{column}",
            "signalCompleteness": "true",
        },
        content_type="text/plain; charset=utf-8",
        accept="application/*",
    )
    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to get code completion at {source_uri} {line},{column}"
        )

    root = et.fromstring(response.text)
    return [
        {
            "identifier": proposal.findtext("IDENTIFIER", ""),
            "kind": int(proposal.findtext("KIND", "0")),
            "prefix_length": int(proposal.findtext("PREFIXLENGTH", "0")),
        }
        for proposal in root.iterfind(".//SCC_COMPLETION")
    ]
