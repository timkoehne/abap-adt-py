"""Release state of an API (class, interface, table, CDS view, function module, data element, ...).

SAP releases an object under contracts: C1 for the use in ABAP for Cloud Development and key user apps,
C0 for extensions, C2 for remote use, C3 and C4 for configuration and ABAP-managed database procedures.
Objects that are not released name their successors, if SAP has one.
"""

import xml.etree.ElementTree as et
from urllib.parse import quote

from ..compat_typing import List, TypedDict
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request

ADTCORE = "{http://www.sap.com/adt/core}"
ARS = "{http://www.sap.com/adt/ars}"
CONTRACTS = ("c0", "c1", "c2", "c3", "c4")
# states in which an API can be used, a deprecated one with a warning
USABLE_STATES = ("RELEASED", "DEPRECATED")


class Successor(TypedDict):
    name: str
    type: str
    uri: str


class ReleaseContract(TypedDict):
    # C0 ... C4
    contract: str
    # e.g. RELEASED, DEPRECATED, NOT_RELEASED, NOT_TO_BE_RELEASED, NOT_TO_BE_RELEASED_STABLE
    state: str
    state_description: str
    # whether the contract allows the use in ABAP for Cloud Development / in key user apps
    use_in_cloud_development: bool
    use_in_key_user_apps: bool
    successors: List[Successor]
    # a concept named as successor instead of objects, e.g. for a whole framework
    successor_concept: str
    comment: str


class ApiReleaseState(TypedDict):
    name: str
    type: str
    uri: str
    # state of the C1 contract, NOT_RELEASED if the object has none
    state: str
    # usable in ABAP for Cloud Development (language version 5) / in key user apps (language version 2)
    cloud_development: bool
    key_user: bool
    # successors named by any contract, e.g. I_CURRENCY for table TCURX
    successors: List[Successor]
    contracts: List[ReleaseContract]


def _bool(value) -> bool:
    return (value or "").strip().lower() == "true"


def _contract(element: et.Element) -> ReleaseContract:
    status = element.find(f"{ARS}status")
    concept = ""
    if _bool(element.findtext(f"{ARS}useConceptAsSuccessor")):
        concept = (element.findtext(f"{ARS}successorConceptName") or "").strip()
    return {
        "contract": element.get(f"{ARS}contract", ""),
        "state": status.get(f"{ARS}state", "") if status is not None else "",
        "state_description": status.get(f"{ARS}stateDescription", "") if status is not None else "",
        "use_in_cloud_development": _bool(element.get(f"{ARS}useInSAPCloudPlatform")),
        "use_in_key_user_apps": _bool(element.get(f"{ARS}useInKeyUserApps")),
        "successors": [
            {
                "name": successor.get(f"{ADTCORE}name", ""),
                "type": successor.get(f"{ADTCORE}type", ""),
                "uri": successor.get(f"{ADTCORE}uri", ""),
            }
            for successor in element.iterfind(f"{ARS}successors/{ARS}successor")
        ],
        "successor_concept": concept,
        "comment": element.get(f"{ARS}comment", ""),
    }


def parse_api_release(xml_text: str) -> ApiReleaseState:
    root = et.fromstring(xml_text)
    obj = root.find(f"{ARS}releasableObject")
    if obj is None:
        obj = et.Element("empty")
    # the contracts are direct children; ars:behaviour holds elements of the same names with what may be changed
    contracts = [_contract(element) for c in CONTRACTS for element in root.findall(f"{ARS}{c}Release")]
    c1 = next((c for c in contracts if c["contract"] == "C1"), None)
    usable = c1 is not None and c1["state"] in USABLE_STATES
    successors: List[Successor] = []
    for contract in contracts:
        for successor in contract["successors"]:
            if successor not in successors:
                successors.append(successor)
    return {
        "name": obj.get(f"{ADTCORE}name", ""),
        "type": obj.get(f"{ADTCORE}type", ""),
        "uri": obj.get(f"{ADTCORE}uri", ""),
        "state": c1["state"] if c1 else "NOT_RELEASED",
        "cloud_development": usable and c1 is not None and c1["use_in_cloud_development"],
        "key_user": usable and c1 is not None and c1["use_in_key_user_apps"],
        "successors": successors,
        "contracts": contracts,
    }


def get_api_release_state(
    http_request_parameters: HttpRequestParameters, object_uri: str
) -> ApiReleaseState:
    """Release state of an object, e.g. /sap/bc/adt/ddic/tables/tcurx."""
    # the object's uri is one segment of the request's path; its own escapes (e.g. %2f in /ui2/cl_json) are
    # escaped again
    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/apireleases/" + quote(object_uri, safe=""),
        method="GET",
        body="",
        params={},
        accept="application/vnd.sap.adt.apirelease.v10+xml",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read the release state of {object_uri}")
    return parse_api_release(response.text)
