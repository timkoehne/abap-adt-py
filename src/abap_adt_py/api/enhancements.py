"""BAdIs: enhancement spots with BAdI definitions and enhancement implementations."""

import xml.etree.ElementTree as et
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from ..compat_typing import Dict, List, Literal, Optional, TypeAlias, TypedDict, Union
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .activate import activate_objects
from .create import _header, _post_object, _put_locked

ADTCORE = "{http://www.sap.com/adt/core}"
ENHS = "{http://www.sap.com/adt/enhancements/enhs}"
ENHO = "{http://www.sap.com/adt/enhancements/enho}"
ENHCORE = "{http://www.sap.com/abapsource/enhancementscore}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"

SPOT_CONTENT_TYPE = "application/vnd.sap.adt.enh.enhs.v2+xml"
IMPLEMENTATION_CONTENT_TYPE = "application/vnd.sap.adt.enh.enhoxhb.v4+xml"

NAMESPACES = (
    'xmlns:enhcore="http://www.sap.com/abapsource/enhancementscore" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
)

# C: character-like, I: integer, N: numeric text, P: packed number, S: string
FilterTypes: TypeAlias = Literal["C", "I", "N", "P", "S"]


class BadiFilter(TypedDict, total=False):
    name: str
    type: FilterTypes
    description: str
    # the values are checked against this data element, e.g. WERKS_D
    data_element: str
    # implementations can only use constant values, no ranges or patterns
    constant_values_only: bool


class BadiDefinition(TypedDict, total=False):
    name: str
    description: str
    # the BAdI interface, it has to include IF_BADI_INTERFACE
    interface: str
    # single use: exactly one implementation is called, multiple use: all of them
    single_use: bool
    # called if no implementation matches, "" for none
    fallback_class: str
    filters: List[BadiFilter]


class EnhancementSpot(TypedDict):
    name: str
    description: str
    package: str
    badis: List[BadiDefinition]


class FilterCondition(TypedDict, total=False):
    filter: str
    # =, <>, <, <=, >, >=, CP (matches pattern) or NP (does not match)
    comparator: str
    value: str
    # a range low <= filter <= high instead of comparator and value
    low: str
    high: str
    # the comparators of a range if they aren't <=
    low_comparator: str
    high_comparator: str


# the conditions of a BAdI implementation: a list of alternatives (OR), each a list of
# conditions that all have to match (AND). An entry of an AND list can also be a list of
# alternative conditions (OR). A flat list of conditions means they all have to match.
FilterConditions: TypeAlias = List[
    Union[FilterCondition, List[Union[FilterCondition, List[FilterCondition]]]]
]


class BadiImplementation(TypedDict, total=False):
    name: str
    # the BAdI definition that is implemented
    badi: str
    implementing_class: str
    description: str
    active: bool
    filters: FilterConditions


class EnhancementImplementation(TypedDict):
    name: str
    description: str
    package: str
    spot: str
    implementations: List[BadiImplementation]


def _spot_uri(name: str) -> str:
    return f"/sap/bc/adt/enhancements/enhsxsb/{quote(name.lower(), safe='')}"


def _implementation_uri(name: str) -> str:
    return f"/sap/bc/adt/enhancements/enhoxhb/{quote(name.lower(), safe='')}"


def _reference(tag: str, object_type: str, name: str, uri: str) -> str:
    return (
        f"<{tag} adtcore:type={quoteattr(object_type)} adtcore:name={quoteattr(name.upper())} "
        f"adtcore:uri={quoteattr(uri)}/>"
    )


def _class_uri(name: str) -> str:
    return f"/sap/bc/adt/oo/classes/{quote(name.lower(), safe='')}"


def _bool(value) -> str:
    return "true" if value else "false"


def _filter_check(data_element: str, tag: str) -> str:
    if not data_element:
        return ""
    reference = _reference(
        "enhcore:checkObject",
        "DTEL/DE",
        data_element,
        f"/sap/bc/adt/ddic/dataelements/{quote(data_element.lower(), safe='')}",
    )
    return f'<{tag} xsi:type="enhcore:DictionaryCheck">{reference}</{tag}>'


def _spot_body(spot: EnhancementSpot, owner: str, language: str) -> str:
    definitions = ""
    for badi in spot["badis"]:
        if not badi.get("interface"):
            raise ValueError(f"BAdI {badi.get('name')} needs an interface")
        fallback_class = badi.get("fallback_class", "")
        filters = "".join(
            f"<enhs:filter enhs:filterName={quoteattr(f['name'].upper())} "
            f"enhs:filterType={quoteattr(f.get('type', 'C'))} "
            f"enhs:shorttext={quoteattr(f.get('description', ''))}"
            + (' enhs:onlyConstantFilterValues="true"' if f.get("constant_values_only") else "")
            + f">{_filter_check(f.get('data_element', ''), 'enhs:filterCheck')}</enhs:filter>"
            for f in badi.get("filters", [])
        )
        interface = badi["interface"]
        definitions += (
            f"<enhs:badiDefinition enhs:name={quoteattr(badi['name'].upper())} "
            f"enhs:shorttext={quoteattr(badi.get('description', ''))} "
            f"enhs:singleUse=\"{_bool(badi.get('single_use', False))}\" "
            f'enhs:useFallbackClass="{_bool(fallback_class)}" enhs:contextMode="N">'
            + _reference(
                "enhs:interface",
                "INTF/OI",
                interface,
                f"/sap/bc/adt/oo/interfaces/{quote(interface.lower(), safe='')}",
            )
            + (
                _reference("enhs:defaultClass", "CLAS/OC", fallback_class, _class_uri(fallback_class))
                if fallback_class
                else ""
            )
            + (f"<enhs:filters>{filters}</enhs:filters>" if filters else "")
            + "</enhs:badiDefinition>"
        )

    header = _header(spot["name"], spot["description"], owner, "ENHS/XSB", language)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <enhs:objectData xmlns:enhs="http://www.sap.com/adt/enhancements/enhs" {NAMESPACES} {header}>
        <adtcore:packageRef adtcore:name={quoteattr(spot["package"])}/>
        <enhs:contentCommon enhs:toolType="BADI_DEF"/>
        <enhs:contentSpecific><enhs:badiTechnology><enhs:badiDefinitions>
            {definitions}
        </enhs:badiDefinitions></enhs:badiTechnology></enhs:contentSpecific>
    </enhs:objectData>"""


def _get(
    http_request_parameters: HttpRequestParameters, uri: str, accept: str, what: str
) -> et.Element:
    response = request(
        http_request_parameters, uri=uri, method="GET", body="", params={}, accept=accept
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read {what}")
    return et.fromstring(response.text)


def _package(root: et.Element) -> str:
    ref = root.find(f"{ADTCORE}packageRef")
    return ref.get(f"{ADTCORE}name", "") if ref is not None else ""


def _referenced_name(element: et.Element, path: str) -> str:
    ref = element.find(path)
    return ref.get(f"{ADTCORE}name", "") if ref is not None else ""


def create_enhancement_spot(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    badis: List[BadiDefinition],
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create an enhancement spot with BAdI definitions and activate it.

    e.g. badis=[{"name": "ZBADI_CHECK", "interface": "ZIF_CHECK", "single_use": False,
    "filters": [{"name": "PLANT", "type": "C", "data_element": "WERKS_D"}]}]
    The interfaces have to exist and include IF_BADI_INTERFACE.
    """
    spot: EnhancementSpot = {
        "name": name.upper(),
        "description": description,
        "package": package,
        "badis": badis,
    }
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/enhancements/enhsxsb",
        _spot_body(spot, owner, language),
        SPOT_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _spot_uri(name))])
    return True


def get_enhancement_spot(
    http_request_parameters: HttpRequestParameters, name: str
) -> EnhancementSpot:
    """Read an enhancement spot with its BAdI definitions."""
    root = _get(
        http_request_parameters, _spot_uri(name), SPOT_CONTENT_TYPE, f"enhancement spot {name}"
    )
    badis: List[BadiDefinition] = []
    for badi in root.iter(f"{ENHS}badiDefinition"):
        fallback_class = _referenced_name(badi, f"{ENHS}defaultClass")
        badis.append(
            {
                "name": badi.get(f"{ENHS}name", ""),
                "description": badi.get(f"{ENHS}shorttext", ""),
                "interface": _referenced_name(badi, f"{ENHS}interface"),
                "single_use": badi.get(f"{ENHS}singleUse") == "true",
                "fallback_class": fallback_class
                if badi.get(f"{ENHS}useFallbackClass") == "true"
                else "",
                "filters": [
                    {
                        "name": f.get(f"{ENHS}filterName", ""),
                        "type": f.get(f"{ENHS}filterType", ""),  # type: ignore[typeddict-item]
                        "description": f.get(f"{ENHS}shorttext", ""),
                        "data_element": _referenced_name(
                            f, f"{ENHS}filterCheck/{ENHCORE}checkObject"
                        ),
                        "constant_values_only": f.get(f"{ENHS}onlyConstantFilterValues")
                        == "true",
                    }
                    for f in badi.iter(f"{ENHS}filter")
                ],
            }
        )
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": _package(root),
        "badis": badis,
    }


def _filter_token(condition: FilterCondition, implementation: str) -> str:
    name = condition["filter"].upper()
    reference = f"#//badi/contentSpecific///{implementation}/filterTree/filterProperty.{name}"
    if "low" in condition or "high" in condition:
        return (
            f'<enho:filterToken xsi:type="enho:RangeFilter" enho:filterName={quoteattr(name)} '
            f"enho:comparatorLeft={quoteattr(condition.get('low_comparator', '<='))} "
            f"enho:valueLeft={quoteattr(condition.get('low', ''))} "
            f"enho:comparatorRight={quoteattr(condition.get('high_comparator', '<='))} "
            f"enho:valueRight={quoteattr(condition.get('high', ''))} "
            f"enho:filterProperty={quoteattr(reference)}/>"
        )
    return (
        f'<enho:filterToken xsi:type="enho:Filter" enho:filterName={quoteattr(name)} '
        f"enho:comparator={quoteattr(condition.get('comparator', '='))} "
        f"enho:value={quoteattr(condition.get('value', ''))} "
        f"enho:filterProperty={quoteattr(reference)}/>"
    )


def _token_group(kind: str, tokens: List[str]) -> str:
    # SAP writes a group only if it has more than one entry
    if len(tokens) == 1:
        return tokens[0]
    return f'<enho:filterToken xsi:type="enho:{kind}">{"".join(tokens)}</enho:filterToken>'


def _filter_tree(filters: FilterConditions, implementation: str) -> List[str]:
    """The filter tokens for the conditions, see FilterConditions."""
    if not filters:
        return []
    # a flat list of conditions: all of them have to match
    alternatives = [filters] if all(isinstance(f, dict) for f in filters) else filters
    ors = []
    for alternative in alternatives:
        conditions = [alternative] if isinstance(alternative, dict) else alternative
        ands = []
        for condition in conditions:
            if isinstance(condition, dict):
                ands.append(_filter_token(condition, implementation))  # type: ignore[arg-type]
            else:
                ands.append(
                    _token_group("Or", [_filter_token(c, implementation) for c in condition])
                )
        ors.append(_token_group("And", ands))
    return [_token_group("Or", ors)]


def _filter_names(filters: FilterConditions) -> List[str]:
    names = []
    for entry in filters:
        if isinstance(entry, dict):
            names.append(entry["filter"].upper())
        else:
            names.extend(_filter_names(entry))  # type: ignore[arg-type]
    return names


def _implementation_body(
    implementation: EnhancementImplementation,
    badi_filters: Dict[str, Dict[str, BadiFilter]],
    owner: str,
    language: str,
) -> str:
    spot = implementation["spot"].upper()
    spot_uri = _spot_uri(spot)
    badi_implementations = ""
    for badi_implementation in implementation["implementations"]:
        badi = badi_implementation["badi"].upper()
        if badi not in badi_filters:
            raise ValueError(f"enhancement spot {spot} has no BAdI {badi}")
        name = badi_implementation["name"].upper()
        filters = badi_implementation.get("filters", [])

        tree = ""
        used_filters = list(dict.fromkeys(_filter_names(filters)))
        if used_filters:
            properties = ""
            for filter_name in used_filters:
                definition = badi_filters[badi].get(filter_name)
                if definition is None:
                    raise ValueError(f"BAdI {badi} has no filter {filter_name}")
                # the type and check have to match the BAdI definition
                properties += (
                    f"<enho:filterProperty enho:filterName={quoteattr(filter_name)} "
                    f"enho:filterType={quoteattr(definition.get('type', 'C'))}>"
                    f"{_filter_check(definition.get('data_element', ''), 'enho:filterCheck')}"
                    "</enho:filterProperty>"
                )
            tokens = "".join(_filter_tree(filters, name))
            tree = f"<enho:filterTree>{tokens}{properties}</enho:filterTree>"

        badi_uri = f"{spot_uri}#type=enhs%2fxb;name={quote(badi.lower(), safe='')}"
        implementing_class = badi_implementation["implementing_class"]
        badi_implementations += (
            f"<enho:badiImplementation enho:name={quoteattr(name)} "
            f"enho:shortText={quoteattr(badi_implementation.get('description', ''))} "
            f"enho:active=\"{_bool(badi_implementation.get('active', True))}\">"
            + _reference("enho:enhancementSpot", "ENHS/XSB", spot, spot_uri)
            + _reference("enho:badiDefinition", "ENHS/XB", badi, badi_uri)
            + _reference(
                "enho:implementingClass",
                "CLAS/OC",
                implementing_class,
                _class_uri(implementing_class),
            )
            + tree
            + "</enho:badiImplementation>"
        )

    # SAP needs the spot as a used object to create the implementation
    usage = (
        '<enhcore:referencedObject enhcore:program_id="R3TR" enhcore:element_usage="EXTO">'
        + _reference("enhcore:objectReference", "ENHS/XSB", spot, spot_uri)
        + _reference("enhcore:mainObjectReference", "ENHS/XSB", spot, spot_uri)
        + "</enhcore:referencedObject>"
    )
    header = _header(
        implementation["name"], implementation["description"], owner, "ENHO/XHB", language
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <enho:objectData xmlns:enho="http://www.sap.com/adt/enhancements/enho" {NAMESPACES} {header}>
        <adtcore:packageRef adtcore:name={quoteattr(implementation["package"])}/>
        <enho:contentCommon enho:toolType="BADI_IMPL"><enho:usages>{usage}</enho:usages></enho:contentCommon>
        <enho:contentSpecific><enho:badiTechnology><enho:badiImplementations>
            {badi_implementations}
        </enho:badiImplementations></enho:badiTechnology></enho:contentSpecific>
    </enho:objectData>"""


def _badi_filters(
    http_request_parameters: HttpRequestParameters, spot: str
) -> Dict[str, Dict[str, BadiFilter]]:
    definition = get_enhancement_spot(http_request_parameters, spot)
    return {
        badi["name"].upper(): {f["name"].upper(): f for f in badi.get("filters", [])}
        for badi in definition["badis"]
    }


def create_enhancement_implementation(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    spot: str,
    implementations: List[BadiImplementation],
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create an enhancement implementation for a spot with BAdI implementations.

    e.g. implementations=[{"name": "ZBADI_CHECK_1000", "badi": "ZBADI_CHECK",
    "implementing_class": "ZCL_CHECK_1000",
    "filters": [{"filter": "PLANT", "value": "1000"}]}]
    """
    implementation: EnhancementImplementation = {
        "name": name.upper(),
        "description": description,
        "package": package,
        "spot": spot,
        "implementations": implementations,
    }
    body = _implementation_body(
        implementation, _badi_filters(http_request_parameters, spot), owner, language
    )
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/enhancements/enhoxhb",
        body,
        IMPLEMENTATION_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _implementation_uri(name))])
    return True


def _parse_condition(token: et.Element) -> FilterCondition:
    name = token.get(f"{ENHO}filterName", "")
    if token.get(f"{XSI}type") == "enho:RangeFilter":
        condition: FilterCondition = {
            "filter": name,
            "low": token.get(f"{ENHO}valueLeft", ""),
            "high": token.get(f"{ENHO}valueRight", ""),
        }
        for key, attribute in (("low_comparator", "comparatorLeft"), ("high_comparator", "comparatorRight")):
            comparator = token.get(f"{ENHO}{attribute}", "<=")
            if comparator != "<=":
                condition[key] = comparator  # type: ignore[literal-required]
        return condition
    return {
        "filter": name,
        "comparator": token.get(f"{ENHO}comparator", "="),
        "value": token.get(f"{ENHO}value", ""),
    }


def _parse_filter_tree(tree: Optional[et.Element]) -> FilterConditions:
    """The conditions as a list of alternatives (OR), each a list of conditions (AND)."""
    if tree is None:
        return []
    tokens = tree.findall(f"{ENHO}filterToken")
    if not tokens:
        return []
    [top] = tokens

    def kind(token):
        return token.get(f"{XSI}type", "").replace("enho:", "")

    def children(token):
        return token.findall(f"{ENHO}filterToken")

    def parse_and_entry(token):
        if kind(token) == "Or":
            return [_parse_condition(child) for child in children(token)]
        return _parse_condition(token)

    def parse_and(token):
        if kind(token) == "And":
            return [parse_and_entry(child) for child in children(token)]
        return [parse_and_entry(token)]

    if kind(top) == "Or":
        # the alternatives of the outer OR
        return [parse_and(child) for child in children(top)]
    return [parse_and(top)]


def get_enhancement_implementation(
    http_request_parameters: HttpRequestParameters, name: str
) -> EnhancementImplementation:
    """Read an enhancement implementation with its BAdI implementations.

    filters are returned as a list of alternatives (OR), each a list of conditions that
    all have to match (AND), e.g. [[{"filter": "PLANT", "comparator": "=", "value": "1000"}]]
    """
    root = _get(
        http_request_parameters,
        _implementation_uri(name),
        IMPLEMENTATION_CONTENT_TYPE,
        f"enhancement implementation {name}",
    )
    implementations: List[BadiImplementation] = []
    spot = ""
    for implementation in root.iter(f"{ENHO}badiImplementation"):
        spot = spot or _referenced_name(implementation, f"{ENHO}enhancementSpot")
        implementations.append(
            {
                "name": implementation.get(f"{ENHO}name", ""),
                "badi": _referenced_name(implementation, f"{ENHO}badiDefinition"),
                "implementing_class": _referenced_name(implementation, f"{ENHO}implementingClass"),
                "description": implementation.get(f"{ENHO}shortText", ""),
                "active": implementation.get(f"{ENHO}active") == "true",
                "filters": _parse_filter_tree(implementation.find(f"{ENHO}filterTree")),
            }
        )
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": _package(root),
        "spot": spot,
        "implementations": implementations,
    }


def update_enhancement_implementation(
    http_request_parameters: HttpRequestParameters,
    name: str,
    owner: str,
    implementations: Optional[List[BadiImplementation]] = None,
    description: Optional[str] = None,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Change an enhancement implementation and activate it.

    implementations replaces all BAdI implementations; None keeps them.
    """
    implementation = get_enhancement_implementation(http_request_parameters, name)
    if implementations is not None:
        implementation["implementations"] = implementations
    if description is not None:
        implementation["description"] = description
    body = _implementation_body(
        implementation,
        _badi_filters(http_request_parameters, implementation["spot"]),
        owner,
        language,
    )
    _put_locked(
        http_request_parameters,
        _implementation_uri(name),
        body,
        IMPLEMENTATION_CONTENT_TYPE,
        name,
        transport,
    )
    if activate:
        activate_objects(http_request_parameters, [(name.upper(), _implementation_uri(name))])
    return True
