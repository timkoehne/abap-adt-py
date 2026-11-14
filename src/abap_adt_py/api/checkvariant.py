"""ATC check variants of the object kind CHKV (ABAP Cloud style), and the checks they can contain.

A variant lists checks, each with its parameters as JSON (the check's form template holds the defaults). Old
Code Inspector variants such as DEFAULT are not CHKV objects and can't be read this way; run_atc runs both.
"""

import json
import xml.etree.ElementTree as et
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from ..compat_typing import Any, Dict, List, Optional, TypedDict, Union
from ..exceptions import NotFoundError, error_from_response
from ..http_request import HttpRequestParameters, request
from .activate import activate_objects
from .applicationjob import _RANGE_OPTIONS
from .create import _header, _post_object, _put_locked
from .delete import delete_objects

CHECK_VARIANTS = "/sap/bc/adt/atc/checkvariants"
CONTENT_TYPE = "application/vnd.sap.adt.chkvv4+xml"
ADTCORE = "{http://www.sap.com/adt/core}"
CHKV = "{http://www.sap.com/wbobj/atc/chkv}"
CHKVCHECK = "{http://www.sap.com/wbobj/atc/chkvCheck}"
CHKO = "{http://www.sap.com/wbobj/atc/chko}"
CHKC = "{http://www.sap.com/wbobj/atc/chkc}"
CHKOPARAMETER = "{http://www.sap.com/wbobj/atc/chkoParameter}"
FORM_TEMPLATE = "{http://www.sap.com/wbobj/atc/chkvFormTemplate}"

# a parameter value: a single value ("true", "3"), a list of values, or a list of ranges
# {"sign": "include", "option": "containsPattern", "low": "Z*", "high": ""}
ParameterValue = Union[str, List[str], List[Dict[str, str]]]


def check_variant_uri(name: str) -> str:
    return f"{CHECK_VARIANTS}/{quote(name.lower(), safe='')}"


class AtcCheck(TypedDict):
    name: str
    description: str
    # e.g. CI_PERFORMANCE
    category: str
    category_description: str


class AtcCheckParameter(TypedDict):
    name: str
    description: str
    # value (a single value), list (a list of values) or ranges (a list of ranges)
    kind: str
    default: ParameterValue


class AtcCheckDetails(TypedDict):
    name: str
    description: str
    category: str
    parameters: List[AtcCheckParameter]


class CheckVariantCheck(TypedDict):
    name: str
    description: str
    parameters: Dict[str, ParameterValue]


class CheckVariant(TypedDict):
    name: str
    description: str
    package: str
    # active or inactive
    version: str
    checks: List[CheckVariantCheck]


def _get(http_request_parameters, uri, params, accept, what):
    response = request(
        http_request_parameters=http_request_parameters,
        uri=uri,
        method="GET",
        body="",
        params=params,
        accept=accept,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read {what}")
    return response


def list_atc_checks(http_request_parameters: HttpRequestParameters) -> List[AtcCheck]:
    """The checks a check variant can contain, with their categories."""
    response = _get(
        http_request_parameters,
        f"{CHECK_VARIANTS}/formtemplate",
        {},
        "application/xml",
        "the ATC checks",
    )
    checks: List[AtcCheck] = []
    root = et.fromstring(response.text)
    for category in root.iter(f"{FORM_TEMPLATE}availableCheckCategory"):
        category_object = category.find(f"{CHKC}checkCategoryObject")
        category_name = category_description = ""
        if category_object is not None:
            category_name = category_object.get(f"{ADTCORE}name", "")
            category_description = category_object.get(f"{ADTCORE}description", "")
        for check in category.iter(f"{CHKO}checkObject"):
            checks.append(
                {
                    "name": check.get(f"{ADTCORE}name", ""),
                    "description": check.get(f"{ADTCORE}description", ""),
                    "category": category_name,
                    "category_description": category_description,
                }
            )
    return checks


def _default_parameters(
    http_request_parameters: HttpRequestParameters, check: str
) -> List[Dict[str, Any]]:
    """The parameters of a check with their default values, as SAP stores them in a variant."""
    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"{CHECK_VARIANTS}/formtemplate",
        method="GET",
        body="",
        params={"test": check.upper()},
        accept="text/plain",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read the parameters of check {check}")
    try:
        template = json.loads(response.text)
    except ValueError:
        template = {}
    return template.get("parameters", []) if isinstance(template, dict) else []


def _check_object(http_request_parameters: HttpRequestParameters, check: str) -> et.Element:
    """The check's definition. SAP answers the form template of an unknown check with an empty one."""
    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/atc/checks/{quote(check.lower(), safe='')}",
        method="GET",
        body="",
        params={},
        accept="application/vnd.sap.adt.chkov1+xml",
    )
    if response.status_code == 404:
        raise NotFoundError(
            f"{check.upper()} is not an ATC check of this system",
            status_code=404,
            response_text=response.text,
        )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read check {check}")
    return et.fromstring(response.text)


def _kind(parameter: Dict[str, Any]) -> str:
    if "valueRangeList" in parameter:
        return "ranges"
    if "valueList" in parameter:
        return "list"
    return "value"


def _value(parameter: Dict[str, Any]) -> ParameterValue:
    return parameter.get(
        {"ranges": "valueRangeList", "list": "valueList", "value": "value"}[_kind(parameter)], ""
    )


def get_atc_check(http_request_parameters: HttpRequestParameters, check: str) -> AtcCheckDetails:
    """A check's description, category and parameters with their descriptions and default values."""
    root = _check_object(http_request_parameters, check)
    defaults = _default_parameters(http_request_parameters, check)
    category = root.find(f"{CHKO}content/{CHKO}category")
    descriptions = {
        (p.findtext(f"{CHKOPARAMETER}parameterName") or "").strip(): (
            p.findtext(f"{CHKOPARAMETER}parameterDescription") or ""
        ).strip()
        for p in root.iter(f"{CHKOPARAMETER}parameter")
    }
    return {
        "name": root.get(f"{ADTCORE}name", check.upper()),
        "description": root.get(f"{ADTCORE}description", ""),
        "category": category.get(f"{ADTCORE}name", "") if category is not None else "",
        "parameters": [
            {
                "name": p.get("name", ""),
                "description": descriptions.get(p.get("name", ""), ""),
                "kind": _kind(p),
                "default": _value(p),
            }
            for p in defaults
        ],
    }


def get_check_variant(http_request_parameters: HttpRequestParameters, name: str) -> CheckVariant:
    response = _get(
        http_request_parameters, check_variant_uri(name), {}, CONTENT_TYPE, f"check variant {name}"
    )
    root = et.fromstring(response.text)
    package = root.find(f"{ADTCORE}packageRef")
    checks: List[CheckVariantCheck] = []
    for check in root.iter(f"{CHKVCHECK}check"):
        check_object = check.find(f"{CHKO}checkObject")
        values = (check.findtext(f"{CHKVCHECK}parameterValueXml") or "").strip()
        try:
            parameters = json.loads(values).get("parameters", []) if values else []
        except ValueError:
            parameters = []
        checks.append(
            {
                "name": check_object.get(f"{ADTCORE}name", "") if check_object is not None else "",
                "description": (
                    check_object.get(f"{ADTCORE}description", "") if check_object is not None else ""
                ),
                "parameters": {p.get("name", ""): _value(p) for p in parameters},
            }
        )
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": package.get(f"{ADTCORE}name", "") if package is not None else "",
        "version": root.get(f"{ADTCORE}version", ""),
        "checks": checks,
    }


def _range(value_range: Dict[str, Any]) -> Dict[str, str]:
    sign = str(value_range.get("sign", "include"))
    option = str(value_range.get("option", "equals"))
    return {
        "sign": {"I": "include", "E": "exclude"}.get(sign.upper(), sign),
        "option": _RANGE_OPTIONS.get(option.upper(), option),
        "low": str(value_range.get("low", "")),
        "high": str(value_range.get("high", "")),
    }


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parameter_values(
    check: str, defaults: List[Dict[str, Any]], overrides: Dict[str, Any]
) -> str:
    """The check's parameters as JSON: its defaults with the overrides."""
    names = {p.get("name", "").lower(): p for p in defaults}
    unknown = [n for n in overrides if n.lower() not in names]
    if unknown:
        raise ValueError(
            f"check {check} has no parameter {', '.join(unknown)}; its parameters: "
            + (", ".join(p.get("name", "") for p in defaults) or "none")
        )
    parameters = [dict(p) for p in defaults]
    for name, value in overrides.items():
        parameter = next(p for p in parameters if p.get("name", "").lower() == name.lower())
        kind = _kind(parameter)
        if kind == "value":
            if isinstance(value, (list, dict)):
                raise ValueError(f"parameter {parameter['name']} of check {check} takes a single value")
            parameter["value"] = _text(value)
        else:
            if not isinstance(value, list):
                raise ValueError(f"parameter {parameter['name']} of check {check} takes a list")
            if kind == "list":
                parameter["valueList"] = [_text(v) for v in value]
            else:
                parameter["valueRangeList"] = [
                    _range(v if isinstance(v, dict) else {"low": v}) for v in value
                ]
    return json.dumps({"checkName": check, "parameters": parameters}, indent=2)


def save_check_variant(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    checks: List[Dict[str, Any]],
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create a check variant, or overwrite it, with these checks and activate it.

    checks: [{"name": "CI_SYSUBRC", "parameters": {"ReadDB": True}}, {"name": "CI_NO_ORDER_BY"}]; parameters left
    out keep the check's defaults. A list parameter takes a list, a range parameter a list of ranges
    {"sign": "include", "option": "containsPattern", "low": "Z*"} (I/E and EQ, CP, ... work too).
    Raises ActivationError if a check refuses its parameters; the variant then stays inactive.
    """
    name = name.upper()
    uri = check_variant_uri(name)
    # SAP accepts an unknown check and dumps when the variant is activated, so every check is read first
    entries = []
    for check in checks:
        check_name = check["name"].upper()
        _check_object(http_request_parameters, check_name)
        defaults = _default_parameters(http_request_parameters, check_name)
        values = _parameter_values(check_name, defaults, check.get("parameters") or {})
        entries.append(
            '<chkvcheck:check xmlns:chkvcheck="http://www.sap.com/wbobj/atc/chkvCheck">'
            f'<chko:checkObject adtcore:name={quoteattr(check_name)} xmlns:chko="http://www.sap.com/wbobj/atc/chko"/>'
            f"<chkvcheck:parameterValueXml>{escape(values)}</chkvcheck:parameterValueXml></chkvcheck:check>"
        )
    header = _header(name, description, owner, "CHKV/TYP", language)
    package_ref = f"<adtcore:packageRef adtcore:name={quoteattr(package)}/>"
    namespace = 'xmlns:chkv="http://www.sap.com/wbobj/atc/chkv"'

    try:
        get_check_variant(http_request_parameters, name)
    except NotFoundError:
        _post_object(
            http_request_parameters,
            CHECK_VARIANTS,
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <chkv:checkvariant {namespace} {header}>{package_ref}</chkv:checkvariant>""",
            CONTENT_TYPE,
            name,
            transport,
        )
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <chkv:checkvariant {namespace} {header}>
        {package_ref}
        <chkv:content>
            <chkv:name>{escape(name)}</chkv:name>
            <chkv:remoteEnabled>false</chkv:remoteEnabled>
            <chkv:referencedVariant/>
            {"".join(entries)}
        </chkv:content>
    </chkv:checkvariant>"""
    _put_locked(http_request_parameters, uri, body, CONTENT_TYPE, name, transport)
    if activate:
        activate_objects(http_request_parameters, [(name, uri)])
    return True


def delete_check_variant(
    http_request_parameters: HttpRequestParameters, name: str, transport: Optional[str] = None
) -> bool:
    return delete_objects(http_request_parameters, [check_variant_uri(name)], transport)
