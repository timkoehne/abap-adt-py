import xml.etree.ElementTree as et
from xml.sax.saxutils import quoteattr

from ..compat_typing import List, TypedDict
from ..api.xml_namespaces import XML_NAMESPACES
from ..http_request import HttpRequestParameters, request
from ..exceptions import error_from_response


class UnittestFlags:
    def __init__(
        self,
        harmless: bool = True,
        dangerous: bool = False,
        critical: bool = False,
        short: bool = True,
        medium: bool = False,
        long: bool = False,
    ):
        self.harmless = harmless
        self.dangerous = dangerous
        self.critical = critical
        self.short = short
        self.medium = medium
        self.long = long


class UnitTestStackEntry(TypedDict):
    uri: str
    type: str
    name: str
    description: str


class UnitTestAlert(TypedDict):
    title: str
    kind: str
    severity: str
    details: List[str]
    stack: List[UnitTestStackEntry]
    # the test class and method the alert belongs to, empty if raised above them
    test_class: str
    test_method: str


def _adtcore(element: et.Element, name: str) -> str:
    return element.get(f"{{{XML_NAMESPACES['adtcore']}}}{name}", "")


def _parse_alerts(xml_text: str) -> List[UnitTestAlert]:
    root = et.fromstring(xml_text)
    parents = {child: parent for parent in root.iter() for child in parent}

    def enclosing(element: et.Element, tag: str) -> str:
        while element in parents:
            element = parents[element]
            if element.tag == tag:
                return _adtcore(element, "name")
        return ""

    alerts: List[UnitTestAlert] = []
    for alert in root.iter("alert"):
        title = alert.find("title")
        details = [
            "\n".join(x.attrib["text"] for x in detail.iter() if "text" in x.attrib)
            for detail in alert.findall("details/detail")
        ]
        stack: List[UnitTestStackEntry] = [
            {
                "uri": _adtcore(entry, "uri"),
                "type": _adtcore(entry, "type"),
                "name": _adtcore(entry, "name"),
                "description": _adtcore(entry, "description"),
            }
            for entry in alert.findall("stack/stackEntry")
        ]
        alerts.append(
            {
                "title": (title.text or "") if title is not None else "",
                "kind": alert.get("kind", ""),
                "severity": alert.get("severity", ""),
                "details": details,
                "stack": stack,
                "test_class": enclosing(alert, "testClass"),
                "test_method": enclosing(alert, "testMethod"),
            }
        )
    return alerts


def run_unit_test(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    unit_test_flags: UnittestFlags = UnittestFlags(),
) -> List[UnitTestAlert]:
    body = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <aunit:runConfiguration xmlns:aunit="http://www.sap.com/adt/aunit">
        <external>
            <coverage active="false"/>
        </external>
        <options>
            <uriType value="semantic"/>
            <testDeterminationStrategy sameProgram="true" assignedTests="false"/>
            <testRiskLevels harmless="{str(unit_test_flags.harmless).lower()}" dangerous="{str(unit_test_flags.dangerous).lower()}" critical="{str(unit_test_flags.critical).lower()}"/>
            <testDurations short="{str(unit_test_flags.short).lower()}" medium="{str(unit_test_flags.medium).lower()}" long="{str(unit_test_flags.long).lower()}"/>
            <withNavigationUri enabled="true"/>    
        </options>
        <adtcore:objectSets xmlns:adtcore="http://www.sap.com/adt/core">
            <objectSet kind="inclusive">
            <adtcore:objectReferences>
                <adtcore:objectReference adtcore:uri={quoteattr(object_uri)}/>
            </adtcore:objectReferences>
            </objectSet>
        </adtcore:objectSets>
        </aunit:runConfiguration>
        """

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/abapunit/testruns",
        method="POST",
        body=body,
        params={},
        content_type="application/xml",
    )
    if response.status_code == 200:
        alerts = _parse_alerts(response.text)
        return alerts

    else:
        raise error_from_response(response, f"Failed to run unit test for {object_uri}")
