import xml.etree.ElementTree as et

from ..compat_typing import List, TypedDict
from ..api.xml_namespaces import XML_NAMESPACES
from ..http_request import HttpRequestParameters, request


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


class UnitTestAlert(TypedDict):
    title: str
    kind: str
    severity: str
    details: List[str]


def _parse_alerts(xml_text: str) -> List[UnitTestAlert]:
    root = et.fromstring(xml_text)
    errors = []
    alerts = root.findall(".//alert", XML_NAMESPACES)
    for alert in alerts:
        a = {}
        title = alert.find(".//title", XML_NAMESPACES)
        a["title"] = title.text if title is not None else ""
        a["kind"] = alert.attrib.get("kind", "")
        a["severity"] = alert.attrib.get("severity", "")
        stack = alert.find(".//stack", XML_NAMESPACES)
        a["stack"] = stack if stack is not None else []
        details = []
        for detail in alert.findall("./details/detail", XML_NAMESPACES):
            detail_str = "\n".join(
                x.attrib["text"]
                for x in detail.iter()
                if "text" in x.attrib is not None
            )
            details.append(detail_str)
        a["details"] = details
        errors.append(a)
    return errors


def run_unit_test(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    unit_test_flags: UnittestFlags = UnittestFlags(),
):
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
                <adtcore:objectReference adtcore:uri="{object_uri}"/>
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
        raise Exception(
            f"{response.status_code} - Failed to run unit test for {object_uri}\n{response.text}"
        )
