"""Domains and data elements."""

import xml.etree.ElementTree as et
from xml.sax.saxutils import escape, quoteattr

from ..compat_typing import Dict, List, Literal, Optional, TypeAlias, TypedDict
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .activate import activate_objects
from .create import _header, _post_object, _put_locked

ADTCORE = "{http://www.sap.com/adt/core}"
DOMA = "{http://www.sap.com/dictionary/domain}"
DTEL = "{http://www.sap.com/adt/dictionary/dataelements}"

DOMAIN_CONTENT_TYPE = "application/vnd.sap.adt.domains.v2+xml"
DATA_ELEMENT_CONTENT_TYPE = "application/vnd.sap.adt.dataelements.v2+xml"


class FixedValue(TypedDict, total=False):
    # a single value, or the lower limit of an interval
    low: str
    # the upper limit of an interval, empty for a single value
    high: str
    text: str


class Domain(TypedDict):
    name: str
    description: str
    package: str
    data_type: str
    length: int
    decimals: int
    output_length: int
    conversion_exit: str
    sign: bool
    lowercase: bool
    value_table: str
    fixed_values: List[FixedValue]


def _get(
    http_request_parameters: HttpRequestParameters,
    uri: str,
    accept: str,
    version: Optional[str],
    what: str,
) -> et.Element:
    response = request(
        http_request_parameters,
        uri=uri,
        method="GET",
        body="",
        params={"version": version} if version else {},
        accept=accept,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read {what}")
    return et.fromstring(response.text)


def _text(element: et.Element, path: str) -> str:
    return (element.findtext(path) or "").strip()


def _int(element: et.Element, path: str) -> int:
    text = _text(element, path)
    return int(text) if text.isdigit() else 0


def _bool(element: et.Element, path: str) -> bool:
    return _text(element, path) == "true"


def _xml_bool(value: bool) -> str:
    return "true" if value else "false"


def _package(root: et.Element) -> str:
    ref = root.find(f"{ADTCORE}packageRef")
    return ref.get(f"{ADTCORE}name", "") if ref is not None else ""


def _parse_domain(root: et.Element) -> Domain:
    content = root.find(f"{DOMA}content")
    if content is None:
        content = et.Element("empty")
    value_table = content.find(f"{DOMA}valueInformation/{DOMA}valueTableRef")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": _package(root),
        "data_type": _text(content, f"{DOMA}typeInformation/{DOMA}datatype"),
        "length": _int(content, f"{DOMA}typeInformation/{DOMA}length"),
        "decimals": _int(content, f"{DOMA}typeInformation/{DOMA}decimals"),
        "output_length": _int(content, f"{DOMA}outputInformation/{DOMA}length"),
        "conversion_exit": _text(content, f"{DOMA}outputInformation/{DOMA}conversionExit"),
        "sign": _bool(content, f"{DOMA}outputInformation/{DOMA}signExists"),
        "lowercase": _bool(content, f"{DOMA}outputInformation/{DOMA}lowercase"),
        "value_table": value_table.get(f"{ADTCORE}name", "") if value_table is not None else "",
        "fixed_values": [
            {
                # a space is a valid fixed value, e.g. "not set" in XFELD
                "low": value.findtext(f"{DOMA}low") or "",
                "high": value.findtext(f"{DOMA}high") or "",
                "text": _text(value, f"{DOMA}text"),
            }
            for value in content.iter(f"{DOMA}fixValue")
        ],
    }


def _domain_body(domain: Domain, owner: str, language: str) -> str:
    value_table = domain["value_table"].upper()
    value_table_ref = (
        f'<doma:valueTableRef adtcore:type="TABL/DT" adtcore:name={quoteattr(value_table)} '
        f"adtcore:uri={quoteattr('/sap/bc/adt/ddic/tables/' + value_table.lower())}/>"
        if value_table
        else "<doma:valueTableRef/>"
    )
    fixed_values = "".join(
        f"""
                <doma:fixValue>
                    <doma:position>{position:04d}</doma:position>
                    <doma:low>{escape(value.get("low", ""))}</doma:low>
                    <doma:high>{escape(value.get("high", ""))}</doma:high>
                    <doma:text>{escape(value.get("text", ""))}</doma:text>
                </doma:fixValue>"""
        for position, value in enumerate(domain["fixed_values"], start=1)
    )
    header = _header(domain["name"], domain["description"], owner, "DOMA/DD", language)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <doma:domain xmlns:doma="http://www.sap.com/dictionary/domain" {header}>
        <adtcore:packageRef adtcore:name={quoteattr(domain["package"])}/>
        <doma:content>
            <doma:typeInformation>
                <doma:datatype>{escape(domain["data_type"].upper())}</doma:datatype>
                <doma:length>{int(domain["length"]):06d}</doma:length>
                <doma:decimals>{int(domain["decimals"]):06d}</doma:decimals>
            </doma:typeInformation>
            <doma:outputInformation>
                <doma:length>{int(domain["output_length"]):06d}</doma:length>
                <doma:style>00</doma:style>
                <doma:conversionExit>{escape(domain["conversion_exit"].upper())}</doma:conversionExit>
                <doma:signExists>{_xml_bool(domain["sign"])}</doma:signExists>
                <doma:lowercase>{_xml_bool(domain["lowercase"])}</doma:lowercase>
                <doma:ampmFormat>false</doma:ampmFormat>
            </doma:outputInformation>
            <doma:valueInformation>
                {value_table_ref}
                <doma:appendExists>false</doma:appendExists>
                <doma:fixValues>{fixed_values}
                </doma:fixValues>
            </doma:valueInformation>
        </doma:content>
    </doma:domain>"""


def _domain_uri(name: str) -> str:
    return f"/sap/bc/adt/ddic/domains/{name.lower()}"


def create_domain(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    data_type: str,
    length: int,
    decimals: int = 0,
    language: str = "EN",
    transport: Optional[str] = None,
    output_length: int = 0,
    conversion_exit: str = "",
    sign: bool = False,
    lowercase: bool = False,
    value_table: str = "",
    fixed_values: Optional[List[FixedValue]] = None,
    activate: bool = True,
) -> bool:
    """Create a domain with a built-in data type, e.g. data_type="CHAR", length=10.

    output_length 0 lets SAP calculate it. fixed_values are single values
    ({"low": "N", "text": "New"}) or intervals ({"low": "1", "high": "9", "text": ...}).
    """
    domain: Domain = {
        "name": name.upper(),
        "description": description,
        "package": package,
        "data_type": data_type,
        "length": length,
        "decimals": decimals,
        "output_length": output_length,
        "conversion_exit": conversion_exit,
        "sign": sign,
        "lowercase": lowercase,
        "value_table": value_table,
        "fixed_values": list(fixed_values or []),
    }
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/ddic/domains",
        _domain_body(domain, owner, language),
        DOMAIN_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _domain_uri(name))])
    return True


def get_domain(
    http_request_parameters: HttpRequestParameters,
    name: str,
    version: Optional[Literal["active", "inactive"]] = None,
) -> Domain:
    """Read a domain. Without a version SAP returns the inactive version if there is one."""
    root = _get(
        http_request_parameters,
        _domain_uri(name),
        DOMAIN_CONTENT_TYPE,
        version,
        f"domain {name}",
    )
    return _parse_domain(root)


def update_domain(
    http_request_parameters: HttpRequestParameters,
    name: str,
    owner: str,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
    description: Optional[str] = None,
    data_type: Optional[str] = None,
    length: Optional[int] = None,
    decimals: Optional[int] = None,
    output_length: Optional[int] = None,
    conversion_exit: Optional[str] = None,
    sign: Optional[bool] = None,
    lowercase: Optional[bool] = None,
    value_table: Optional[str] = None,
    fixed_values: Optional[List[FixedValue]] = None,
) -> bool:
    """Change a domain. Arguments left at None keep their current value.

    fixed_values replaces all fixed values, [] removes them.
    """
    domain = get_domain(http_request_parameters, name)
    changes = {
        "description": description,
        "data_type": data_type,
        "length": length,
        "decimals": decimals,
        "output_length": output_length,
        "conversion_exit": conversion_exit,
        "sign": sign,
        "lowercase": lowercase,
        "value_table": value_table,
        "fixed_values": fixed_values,
    }
    changes = {key: value for key, value in changes.items() if value is not None}
    if output_length is None and any(
        key in changes for key in ("data_type", "length", "decimals", "sign")
    ):
        # let SAP calculate the output length for the new type
        changes["output_length"] = 0
    domain.update(changes)  # type: ignore[typeddict-item]

    _put_locked(
        http_request_parameters,
        _domain_uri(name),
        _domain_body(domain, owner, language),
        DOMAIN_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _domain_uri(name))])
    return True


class FieldLabels(TypedDict, total=False):
    short: str
    medium: str
    long: str
    heading: str


LABELS = ("short", "medium", "long", "heading")
# the most characters each label can have
MAX_LABEL_LENGTHS: Dict[str, int] = {"short": 10, "medium": 20, "long": 40, "heading": 55}

# how SAP names the kinds of types a data element can have
DataElementTypeKinds: TypeAlias = Literal[
    # typed by a domain
    "domain",
    # a built-in type, e.g. CHAR 10
    "predefinedAbapType",
    # TYPE REF TO a built-in type, e.g. STRING
    "refToPredefinedAbapType",
    # TYPE REF TO a dictionary type (structure, table type, data element)
    "refToDictionaryType",
    # TYPE REF TO a class or interface
    "refToClifType",
]


class DataElement(TypedDict):
    name: str
    description: str
    package: str
    type_kind: str
    # domain, dictionary type, class or interface, empty for built-in types
    type_name: str
    data_type: str
    length: int
    decimals: int
    labels: FieldLabels
    # the output lengths of the labels
    label_lengths: Dict[str, int]
    search_help: str
    search_help_parameter: str
    parameter_id: str
    default_component_name: str
    change_document: bool


_LABEL_TAGS = {
    "short": "shortField",
    "medium": "mediumField",
    "long": "longField",
    "heading": "headingField",
}


def _parse_data_element(root: et.Element) -> DataElement:
    content = root.find(f"{DTEL}dataElement")
    if content is None:
        content = et.Element("empty")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": _package(root),
        "type_kind": _text(content, f"{DTEL}typeKind"),
        "type_name": _text(content, f"{DTEL}typeName"),
        "data_type": _text(content, f"{DTEL}dataType"),
        "length": _int(content, f"{DTEL}dataTypeLength"),
        "decimals": _int(content, f"{DTEL}dataTypeDecimals"),
        "labels": {
            label: _text(content, f"{DTEL}{tag}Label") for label, tag in _LABEL_TAGS.items()
        },  # type: ignore[typeddict-item]
        "label_lengths": {
            label: _int(content, f"{DTEL}{tag}Length") for label, tag in _LABEL_TAGS.items()
        },
        "search_help": _text(content, f"{DTEL}searchHelp"),
        "search_help_parameter": _text(content, f"{DTEL}searchHelpParameter"),
        "parameter_id": _text(content, f"{DTEL}setGetParameter"),
        "default_component_name": _text(content, f"{DTEL}defaultComponentName"),
        "change_document": _bool(content, f"{DTEL}changeDocument"),
    }


def _data_element_body(data_element: DataElement, owner: str, language: str) -> str:
    labels = ""
    for label, tag in _LABEL_TAGS.items():
        text = data_element["labels"].get(label, "")
        max_length = MAX_LABEL_LENGTHS[label]
        if len(text) > max_length:
            raise ValueError(f"the {label} label can have at most {max_length} characters")
        # labels are shown with their maximum length unless a shorter one is given
        length = data_element["label_lengths"].get(label) or max_length
        labels += f"""
            <dtel:{tag}Label>{escape(text)}</dtel:{tag}Label>
            <dtel:{tag}Length>{max(length, len(text)):02d}</dtel:{tag}Length>
            <dtel:{tag}MaxLength>{max_length:02d}</dtel:{tag}MaxLength>"""

    header = _header(
        data_element["name"], data_element["description"], owner, "DTEL/DE", language
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <blue:wbobj xmlns:blue="http://www.sap.com/wbobj/dictionary/dtel" {header}>
        <adtcore:packageRef adtcore:name={quoteattr(data_element["package"])}/>
        <dtel:dataElement xmlns:dtel="http://www.sap.com/adt/dictionary/dataelements">
            <dtel:typeKind>{escape(data_element["type_kind"])}</dtel:typeKind>
            <dtel:typeName>{escape(data_element["type_name"].upper())}</dtel:typeName>
            <dtel:dataType>{escape(data_element["data_type"].upper())}</dtel:dataType>
            <dtel:dataTypeLength>{int(data_element["length"]):06d}</dtel:dataTypeLength>
            <dtel:dataTypeDecimals>{int(data_element["decimals"]):06d}</dtel:dataTypeDecimals>{labels}
            <dtel:searchHelp>{escape(data_element["search_help"].upper())}</dtel:searchHelp>
            <dtel:searchHelpParameter>{escape(data_element["search_help_parameter"].upper())}</dtel:searchHelpParameter>
            <dtel:setGetParameter>{escape(data_element["parameter_id"].upper())}</dtel:setGetParameter>
            <dtel:defaultComponentName>{escape(data_element["default_component_name"].upper())}</dtel:defaultComponentName>
            <dtel:deactivateInputHistory>false</dtel:deactivateInputHistory>
            <dtel:changeDocument>{_xml_bool(data_element["change_document"])}</dtel:changeDocument>
            <dtel:leftToRightDirection>false</dtel:leftToRightDirection>
            <dtel:deactivateBIDIFiltering>false</dtel:deactivateBIDIFiltering>
        </dtel:dataElement>
    </blue:wbobj>"""


def _data_element_uri(name: str) -> str:
    return f"/sap/bc/adt/ddic/dataelements/{name.lower()}"


ReferenceKinds: TypeAlias = Literal["class", "dictionary", "built_in"]


def _data_element_type(
    domain: Optional[str],
    data_type: Optional[str],
    reference_to: Optional[str],
    reference_kind: ReferenceKinds,
) -> Dict[str, str]:
    """type_kind, type_name and data_type for the ways a data element can be typed."""
    if sum(value is not None for value in (domain, data_type, reference_to)) != 1:
        raise ValueError("pass exactly one of domain, data_type and reference_to")
    if domain is not None:
        return {"type_kind": "domain", "type_name": domain, "data_type": ""}
    if data_type is not None:
        return {"type_kind": "predefinedAbapType", "type_name": "", "data_type": data_type}
    kinds = {
        "class": "refToClifType",
        "dictionary": "refToDictionaryType",
        "built_in": "refToPredefinedAbapType",
    }
    if reference_kind == "built_in":
        return {"type_kind": kinds[reference_kind], "type_name": "", "data_type": reference_to or ""}
    return {"type_kind": kinds[reference_kind], "type_name": reference_to or "", "data_type": ""}


def create_data_element(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    domain: Optional[str] = None,
    data_type: Optional[str] = None,
    length: int = 0,
    decimals: int = 0,
    reference_to: Optional[str] = None,
    reference_kind: ReferenceKinds = "class",
    labels: Optional[FieldLabels] = None,
    label_lengths: Optional[Dict[str, int]] = None,
    search_help: str = "",
    search_help_parameter: str = "",
    parameter_id: str = "",
    default_component_name: str = "",
    change_document: bool = False,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create a data element and activate it.

    Typed by a domain (domain="ZSTATUS"), a built-in type (data_type="CHAR", length=10)
    or as a reference: TYPE REF TO a class or interface (reference_to="ZCL_FOO"), a
    dictionary type (reference_kind="dictionary") or a built-in type
    (reference_to="STRING", reference_kind="built_in"). labels are the field labels, e.g.
    {"short": "Status", "medium": "Order status", "long": ..., "heading": ...}.
    """
    kind = _data_element_type(domain, data_type, reference_to, reference_kind)
    data_element: DataElement = {
        "name": name.upper(),
        "description": description,
        "package": package,
        "type_kind": kind["type_kind"],
        "type_name": kind["type_name"],
        "data_type": kind["data_type"],
        "length": length if data_type is not None else 0,
        "decimals": decimals if data_type is not None else 0,
        "labels": dict(labels or {}),  # type: ignore[typeddict-item]
        "label_lengths": dict(label_lengths or {}),
        "search_help": search_help,
        "search_help_parameter": search_help_parameter,
        "parameter_id": parameter_id,
        "default_component_name": default_component_name,
        "change_document": change_document,
    }
    # SAP ignores the definition when creating a data element,
    # so it is created first and saved afterwards, like in the editor
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/ddic/dataelements",
        f"""<?xml version="1.0" encoding="UTF-8"?>
        <blue:wbobj xmlns:blue="http://www.sap.com/wbobj/dictionary/dtel" {_header(name.upper(), description, owner, "DTEL/DE", language)}>
            <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        </blue:wbobj>""",
        DATA_ELEMENT_CONTENT_TYPE,
        name,
        transport,
    )
    _put_locked(
        http_request_parameters,
        _data_element_uri(name),
        _data_element_body(data_element, owner, language),
        DATA_ELEMENT_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _data_element_uri(name))])
    return True


def get_data_element(
    http_request_parameters: HttpRequestParameters,
    name: str,
    version: Optional[Literal["active", "inactive"]] = None,
) -> DataElement:
    """Read a data element. Without a version SAP returns the inactive version if there is one."""
    root = _get(
        http_request_parameters,
        _data_element_uri(name),
        DATA_ELEMENT_CONTENT_TYPE,
        version,
        f"data element {name}",
    )
    return _parse_data_element(root)


def update_data_element(
    http_request_parameters: HttpRequestParameters,
    name: str,
    owner: str,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
    description: Optional[str] = None,
    domain: Optional[str] = None,
    data_type: Optional[str] = None,
    length: Optional[int] = None,
    decimals: Optional[int] = None,
    reference_to: Optional[str] = None,
    reference_kind: ReferenceKinds = "class",
    labels: Optional[FieldLabels] = None,
    label_lengths: Optional[Dict[str, int]] = None,
    search_help: Optional[str] = None,
    search_help_parameter: Optional[str] = None,
    parameter_id: Optional[str] = None,
    default_component_name: Optional[str] = None,
    change_document: Optional[bool] = None,
) -> bool:
    """Change a data element. Arguments left at None keep their current value.

    Passing domain, data_type or reference_to changes the type. labels only changes
    the labels it contains.
    """
    data_element = get_data_element(http_request_parameters, name)

    if domain is not None or data_type is not None or reference_to is not None:
        data_element.update(_data_element_type(domain, data_type, reference_to, reference_kind))  # type: ignore[typeddict-item]
        data_element["length"] = (length or 0) if data_type is not None else 0
        data_element["decimals"] = (decimals or 0) if data_type is not None else 0
    elif data_element["type_kind"] in ("predefinedAbapType", "refToPredefinedAbapType"):
        if length is not None:
            data_element["length"] = length
        if decimals is not None:
            data_element["decimals"] = decimals

    for label, text in (labels or {}).items():
        if label not in LABELS:
            raise ValueError(f"unknown label {label}, expected one of {', '.join(LABELS)}")
        data_element["labels"][label] = text  # type: ignore[literal-required]
    data_element["label_lengths"].update(label_lengths or {})
    for label, text in data_element["labels"].items():
        # a label that got longer needs a longer output length
        if len(text) > data_element["label_lengths"].get(label, 0):
            data_element["label_lengths"][label] = MAX_LABEL_LENGTHS[label]

    changes = {
        "description": description,
        "search_help": search_help,
        "search_help_parameter": search_help_parameter,
        "parameter_id": parameter_id,
        "default_component_name": default_component_name,
        "change_document": change_document,
    }
    data_element.update({k: v for k, v in changes.items() if v is not None})  # type: ignore[typeddict-item]

    _put_locked(
        http_request_parameters,
        _data_element_uri(name),
        _data_element_body(data_element, owner, language),
        DATA_ELEMENT_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _data_element_uri(name))])
    return True
