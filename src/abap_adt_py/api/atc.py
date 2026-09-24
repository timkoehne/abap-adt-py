import re
import xml.etree.ElementTree as et
from html.parser import HTMLParser
from xml.sax.saxutils import quoteattr

from ..compat_typing import Dict, List, Optional, TypedDict, Union
from ..http_request import HttpRequestParameters, request
from .xml_namespaces import XML_NAMESPACES


class AtcVariant(TypedDict):
    name: str
    description: str


class AtcFinding(TypedDict):
    object_name: str
    object_type: str
    package: str
    # 1 = error, 2 = warning, 3 = information
    priority: int
    check_id: str
    check_title: str
    message_id: str
    message: str
    # source the finding points to, without the position
    uri: str
    line: Optional[int]
    column: Optional[int]
    documentation_uri: str
    # additional information, e.g. REF_OBJ_NAME for the API a finding is about
    tags: Dict[str, str]


class AtcInfo(TypedDict):
    # e.g. FINDING_STATS or TOOL_FAILURE if a check could not be executed
    type: str
    description: str


class AtcResult(TypedDict):
    check_variant: str
    findings: List[AtcFinding]
    infos: List[AtcInfo]


def _ns(prefix: str, name: str) -> str:
    return f"{{{XML_NAMESPACES[prefix]}}}{name}"


def _raise(response, action: str):
    raise Exception(f"{response.status_code} - Failed to {action}\n{response.text}")


def default_check_variant(http_request_parameters: HttpRequestParameters) -> str:
    """The check variant the system uses when none is given."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/atc/customizing",
        method="GET",
        body="",
        params={},
        accept="application/xml",
    )
    if response.status_code != 200:
        _raise(response, "read the ATC customizing")

    root = et.fromstring(response.text)
    for prop in root.iterfind("properties/property"):
        if prop.get("name") == "systemCheckVariant":
            return prop.get("value", "")
    return ""


def list_check_variants(
    http_request_parameters: HttpRequestParameters,
    pattern: str = "*",
    max_results: int = 100,
) -> List[AtcVariant]:
    """List ATC check variants whose name matches pattern (* as wildcard)."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/atc/variants",
        method="GET",
        body="",
        params={"name": pattern, "maxItemCount": max_results},
        accept="application/xml",
    )
    if response.status_code != 200:
        _raise(response, "list ATC check variants")

    root = et.fromstring(response.text)
    return [
        {
            "name": item.findtext("nameditem:name", "", XML_NAMESPACES),
            "description": item.findtext("nameditem:description", "", XML_NAMESPACES),
        }
        for item in root.iterfind("nameditem:namedItem", XML_NAMESPACES)
    ]


def _parse_run_infos(xml_text: str) -> List[AtcInfo]:
    root = et.fromstring(xml_text)
    return [
        {
            "type": info.findtext("atcinfo:type", "", XML_NAMESPACES),
            "description": info.findtext("atcinfo:description", "", XML_NAMESPACES),
        }
        for info in root.iterfind(".//atcinfo:info", XML_NAMESPACES)
    ]


def _parse_findings(xml_text: str) -> List[AtcFinding]:
    root = et.fromstring(xml_text)
    findings: List[AtcFinding] = []
    for obj in root.iterfind(".//atcobject:object", XML_NAMESPACES):
        for finding in obj.iterfind(".//atcfinding:finding", XML_NAMESPACES):
            location = finding.get(_ns("atcfinding", "location"), "")
            position = re.search(r"#start=(\d+),(\d+)", location)
            documentation = finding.find("atom:link", XML_NAMESPACES)
            findings.append(
                {
                    "object_name": obj.get(_ns("adtcore", "name"), ""),
                    "object_type": obj.get(_ns("adtcore", "type"), ""),
                    "package": obj.get(_ns("adtcore", "packageName"), ""),
                    "priority": int(finding.get(_ns("atcfinding", "priority"), "0")),
                    "check_id": finding.get(_ns("atcfinding", "checkId"), ""),
                    "check_title": finding.get(_ns("atcfinding", "checkTitle"), ""),
                    "message_id": finding.get(_ns("atcfinding", "messageId"), ""),
                    "message": finding.get(
                        _ns("atcfinding", "messageTitle"), ""
                    ).strip(),
                    "uri": location.split("#")[0],
                    "line": int(position.group(1)) if position else None,
                    "column": int(position.group(2)) if position else None,
                    "documentation_uri": (
                        documentation.get("href", "")
                        if documentation is not None
                        else ""
                    ),
                    "tags": {
                        tag.get(_ns("atcfinding", "name"), ""): tag.get(
                            _ns("atcfinding", "value"), ""
                        )
                        for tag in finding.iterfind(
                            "atcfinding:tags/atcfinding:tag", XML_NAMESPACES
                        )
                    },
                }
            )
    return findings


def run_atc(
    http_request_parameters: HttpRequestParameters,
    object_uris: Union[str, List[str]],
    check_variant: Optional[str] = None,
    max_findings: int = 100,
) -> AtcResult:
    """Run the ABAP Test Cockpit on objects or packages and return the findings.

    Without check_variant the system's default variant is used. Findings are only
    reported for customer objects, SAP objects are not checked.
    """

    if isinstance(object_uris, str):
        object_uris = [object_uris]

    if check_variant:
        # SAP runs an unknown variant without any checks instead of reporting an error
        variants = list_check_variants(http_request_parameters, check_variant, 1)
        if not any(v["name"] == check_variant.upper() for v in variants):
            raise Exception(f"ATC check variant {check_variant} does not exist")
        check_variant = check_variant.upper()
    else:
        check_variant = default_check_variant(http_request_parameters)

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/atc/worklists",
        method="POST",
        body="",
        params={"checkVariant": check_variant},
        accept="text/plain",
    )
    if response.status_code != 200:
        _raise(response, f"create an ATC worklist for {check_variant}")
    worklist_id = response.text.strip()

    references = "".join(
        f"<adtcore:objectReference adtcore:uri={quoteattr(uri)}/>"
        for uri in object_uris
    )
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <atc:run maximumVerdicts="{int(max_findings)}" xmlns:atc="http://www.sap.com/adt/atc">
        <objectSets xmlns:adtcore="http://www.sap.com/adt/core">
            <objectSet kind="inclusive">
                <adtcore:objectReferences>{references}</adtcore:objectReferences>
            </objectSet>
        </objectSets>
    </atc:run>"""
    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/atc/runs",
        method="POST",
        body=body,
        params={"worklistId": worklist_id},
        accept="application/xml",
    )
    if response.status_code != 200:
        _raise(response, "run ATC")
    infos = _parse_run_infos(response.text)

    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/atc/worklists/{worklist_id}",
        method="GET",
        body="",
        params={"includeExemptedFindings": "false"},
        accept="application/atc.worklist.v1+xml",
    )
    if response.status_code != 200:
        _raise(response, "read the ATC findings")

    return {
        "check_variant": check_variant,
        "findings": _parse_findings(response.text),
        "infos": infos,
    }


class _TextExtractor(HTMLParser):
    BLOCKS = {"p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS:
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")

    def handle_endtag(self, tag):
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        # drop blank lines within blocks and collapse runs of them
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def atc_documentation(
    http_request_parameters: HttpRequestParameters,
    documentation_uri: str,
    as_html: bool = False,
) -> str:
    """Explanation of an ATC finding's check, as plain text or as the original HTML."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri=documentation_uri,
        method="GET",
        body="",
        params={},
        accept="application/vnd.sap.adt.docu.v1+html",
    )
    if response.status_code != 200:
        _raise(response, f"read the documentation {documentation_uri}")

    if as_html:
        return response.text
    extractor = _TextExtractor()
    extractor.feed(response.text)
    return extractor.text()
