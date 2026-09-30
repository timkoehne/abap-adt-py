"""Number range objects.

ADT only handles the object itself. Its intervals are customizing and have to be
maintained in ABAP, e.g. with CL_NUMBERRANGE_INTERVALS.
"""

import json
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from ..compat_typing import Literal, Optional, TypeAlias
from .activate import activate_objects
from .create import _header, _post_object, _put_locked
from ..http_request import HttpRequestParameters

Buffering: TypeAlias = Literal["none", "mainBuffer", "parallel"]


def _uri(name: str) -> str:
    return f"/sap/bc/adt/numberranges/objects/{quote(name.lower(), safe='')}"


def create_number_range_object(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    number_length_domain: str,
    percent_warning: float = 10.0,
    buffering: Buffering = "none",
    buffered_numbers: int = 0,
    subobject_data_element: str = "",
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create a number range object and activate it.

    number_length_domain is a NUMC or CHAR domain that sets the length of the numbers,
    e.g. NUM10. The object has no intervals yet.
    """
    name = name.upper()
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/numberranges/objects",
        f"""<?xml version="1.0" encoding="UTF-8"?>
        <blue:blueSource xmlns:blue="http://www.sap.com/wbobj/blue" {_header(name, description, owner, "NROB/NRO", language)}>
            <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        </blue:blueSource>""",
        "application/vnd.sap.adt.blues.v1+xml",
        name,
        transport,
    )
    # SAP ignores the attributes on creation, they are part of the (JSON) source
    source = {
        "formatVersion": "1",
        "header": {"description": description, "originalLanguage": language.lower()},
        "interval": {
            "numberLengthDomain": number_length_domain.upper(),
            "percentWarning": float(percent_warning),
            "subType": subobject_data_element.upper(),
            "untilYear": False,
            "rolling": True,
            "prefix": False,
        },
        "configuration": {"buffering": buffering, "bufferedNumbers": int(buffered_numbers)},
    }
    _put_locked(
        http_request_parameters,
        f"{_uri(name)}/source/main",
        json.dumps(source, indent=2),
        "application/json; charset=utf-8",
        name,
        transport,
        lock_uri=_uri(name),
    )
    if activate:
        activate_objects(http_request_parameters, [(name, _uri(name))])
    return True
