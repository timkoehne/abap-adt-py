"""Application jobs: job catalog entries (SAJC) and job templates (SAJT), and application log objects (APLO).

All three are objects with a JSON source (the ABAP file format): created empty, then their source is saved under a
lock and activated. A job catalog entry names the class that runs in the job (it implements IF_APJ_DT_EXEC_OBJECT
and IF_APJ_RT_EXEC_OBJECT); SAP adds the class's parameters to the entry when it is saved. A job template refers to
a catalog entry and holds values for its parameters; CL_APJ_RT_API=>SCHEDULE_JOB schedules a job from a template.
"""

import json
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from ..compat_typing import Any, Dict, List, Optional, TypedDict, Union
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .activate import activate_objects
from .create import _header, _post_object, _put_locked

CATALOGS = "/sap/bc/adt/applicationjob/catalogs"
TEMPLATES = "/sap/bc/adt/applicationjob/templates"
LOG_OBJECTS = "/sap/bc/adt/applicationlog/objects"
ADTCORE = "{http://www.sap.com/adt/core}"


def catalog_entry_uri(name: str) -> str:
    return f"{CATALOGS}/{quote(name.lower(), safe='')}"


def template_uri(name: str) -> str:
    return f"{TEMPLATES}/{quote(name.lower(), safe='')}"


def log_object_uri(name: str) -> str:
    return f"{LOG_OBJECTS}/{quote(name.lower(), safe='')}"


def _header_json(description: str, language: str) -> Dict[str, str]:
    return {"description": description, "originalLanguage": language.lower()}


def _create_json_object(
    http_request_parameters: HttpRequestParameters,
    collection: str,
    uri: str,
    name: str,
    object_type: str,
    package: str,
    description: str,
    owner: str,
    source: Dict[str, Any],
    content_type: str,
    language: str,
    transport: Optional[str],
    activate: bool,
) -> bool:
    _post_object(
        http_request_parameters,
        collection,
        f"""<?xml version="1.0" encoding="UTF-8"?>
        <blue:blueSource xmlns:blue="http://www.sap.com/wbobj/blue" {_header(name, description, owner, object_type, language)}>
            <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        </blue:blueSource>""",
        content_type,
        name,
        transport,
    )
    _save_source(http_request_parameters, uri, name, source, transport)
    if activate:
        # a job catalog entry activated right after saving fails with "Report or class  is invalid" (with no
        # name) until its saved source has been read once
        _read_source(http_request_parameters, uri, name)
        activate_objects(http_request_parameters, [(name, uri)])
    return True


def _save_source(
    http_request_parameters: HttpRequestParameters,
    uri: str,
    name: str,
    source: Dict[str, Any],
    transport: Optional[str],
) -> None:
    _put_locked(
        http_request_parameters,
        f"{uri}/source/main",
        json.dumps(source, indent=2),
        "application/json; charset=utf-8",
        name,
        transport,
        lock_uri=uri,
    )


def _read_source(
    http_request_parameters: HttpRequestParameters, uri: str, what: str
) -> Dict[str, Any]:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"{uri}/source/main",
        method="GET",
        body="",
        params={},
        accept="application/json",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read {what}")
    return json.loads(response.text)


class JobCatalogEntry(TypedDict):
    name: str
    description: str
    # the class whose IF_APJ_RT_EXEC_OBJECT~EXECUTE runs in the job
    class_name: str
    # the parameters of the class (IF_APJ_DT_EXEC_OBJECT~GET_PARAMETERS) with their screen settings, e.g.
    # {"name": "P_ID", "mandatory": True}
    parameters: List[Dict[str, Any]]
    # the whole JSON source, e.g. with exit classes, sections and groups
    source: Dict[str, Any]


def create_job_catalog_entry(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    class_name: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create a job catalog entry for a class and activate it.

    parameters are the screen settings of the class's parameters, e.g. [{"name": "P_ID", "mandatory": True}]
    (also hidden, readOnly, group, ...; the titles come from the class); SAP adds every parameter of the class
    that is left out.
    """
    name = name.upper()
    source: Dict[str, Any] = {
        "formatVersion": "1",
        "header": _header_json(description, language),
        "generalInformation": {"className": class_name.upper()},
    }
    if parameters:
        source["parameters"] = parameters
    return _create_json_object(
        http_request_parameters,
        CATALOGS,
        catalog_entry_uri(name),
        name,
        "SAJC",
        package,
        description,
        owner,
        source,
        "application/vnd.sap.adt.blues.v2+xml",
        language,
        transport,
        activate,
    )


def get_job_catalog_entry(
    http_request_parameters: HttpRequestParameters, name: str
) -> JobCatalogEntry:
    source = _read_source(
        http_request_parameters, catalog_entry_uri(name), f"job catalog entry {name}"
    )
    return {
        "name": name.upper(),
        "description": source.get("header", {}).get("description", ""),
        "class_name": source.get("generalInformation", {}).get("className", ""),
        "parameters": source.get("parameters", []),
        "source": source,
    }


ParameterValue = Union[str, List[Dict[str, str]]]


class JobTemplate(TypedDict):
    name: str
    description: str
    catalog_entry: str
    # parameter name: a single value, or a list of ranges {"sign": "include", "option": "equals", "low": ..., "high": ...}
    parameters: Dict[str, ParameterValue]
    source: Dict[str, Any]


_RANGE_OPTIONS = {
    "EQ": "equals",
    "BT": "between",
    "GT": "greaterThan",
    "CP": "containsPattern",
    "NE": "notEqual",
    "NB": "notBetween",
    "NP": "notContainsPattern",
    "GE": "greaterEqual",
    "LT": "lessThan",
    "LE": "lessEqual",
}


def _value_range(value_range: Dict[str, str]) -> Dict[str, str]:
    sign = value_range.get("sign", "include")
    option = value_range.get("option", "equals")
    result = {
        "sign": {"I": "include", "E": "exclude"}.get(sign.upper(), sign),
        "option": _RANGE_OPTIONS.get(option.upper(), option),
        "low": str(value_range.get("low", "")),
    }
    if value_range.get("high"):
        result["high"] = str(value_range["high"])
    return result


def _template_parameters(parameters: Dict[str, ParameterValue]) -> Dict[str, Any]:
    single = [
        {"name": name.upper(), "value": str(value)}
        for name, value in parameters.items()
        if not isinstance(value, list)
    ]
    ranges = [
        {"name": name.upper(), "valueRanges": [_value_range(r) for r in value]}
        for name, value in parameters.items()
        if isinstance(value, list)
    ]
    result: Dict[str, Any] = {}
    if single:
        result["singleValueParameters"] = single
    if ranges:
        result["valueRangesParameters"] = ranges
    return result


def create_job_template(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    catalog_entry: str,
    parameters: Optional[Dict[str, ParameterValue]] = None,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create a job template for an active job catalog entry and activate it.

    parameters holds values of the catalog entry's parameters: a single value ({"P_ID": "A1"}) or a list of ranges
    ({"S_ID": [{"sign": "include", "option": "between", "low": "A", "high": "C"}]}; I/E and EQ, BT, ... work too).
    """
    name = name.upper()
    source: Dict[str, Any] = {
        "formatVersion": "1",
        "header": _header_json(description, language),
        "generalInformation": {"catalogName": catalog_entry.upper()},
    }
    if parameters:
        source["parameters"] = _template_parameters(parameters)
    return _create_json_object(
        http_request_parameters,
        TEMPLATES,
        template_uri(name),
        name,
        "SAJT",
        package,
        description,
        owner,
        source,
        "application/vnd.sap.adt.blues.v2+xml",
        language,
        transport,
        activate,
    )


def get_job_template(
    http_request_parameters: HttpRequestParameters, name: str
) -> JobTemplate:
    source = _read_source(http_request_parameters, template_uri(name), f"job template {name}")
    parameters: Dict[str, ParameterValue] = {}
    values = source.get("parameters", {})
    for parameter in values.get("singleValueParameters", []):
        parameters[parameter.get("name", "")] = parameter.get("value", "")
    for parameter in values.get("valueRangesParameters", []):
        parameters[parameter.get("name", "")] = parameter.get("valueRanges", [])
    return {
        "name": name.upper(),
        "description": source.get("header", {}).get("description", ""),
        "catalog_entry": source.get("generalInformation", {}).get("catalogName", ""),
        "parameters": parameters,
        "source": source,
    }


class LogSubobject(TypedDict):
    name: str
    description: str


class ApplicationLogObject(TypedDict):
    name: str
    description: str
    subobjects: List[LogSubobject]


def create_application_log_object(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    subobjects: Optional[List[LogSubobject]] = None,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create an application log object with subobjects, e.g. [{"name": "RUN", "description": "Runs"}],
    and activate it. CL_BALI_LOG writes logs for it.
    """
    name = name.upper()
    source = {
        "formatVersion": "1",
        "header": _header_json(description, language),
        "subobjects": [
            {"name": s["name"].upper(), "description": s.get("description", "")}
            for s in subobjects or []
        ],
    }
    return _create_json_object(
        http_request_parameters,
        LOG_OBJECTS,
        log_object_uri(name),
        name,
        "APLO/TYP",
        package,
        description,
        owner,
        source,
        "application/vnd.sap.adt.blues.v1+xml",
        language,
        transport,
        activate,
    )


def get_application_log_object(
    http_request_parameters: HttpRequestParameters, name: str
) -> ApplicationLogObject:
    source = _read_source(
        http_request_parameters, log_object_uri(name), f"application log object {name}"
    )
    return {
        "name": name.upper(),
        "description": source.get("header", {}).get("description", ""),
        "subobjects": [
            {"name": s.get("name", ""), "description": s.get("description", "")}
            for s in source.get("subobjects", [])
        ],
    }
