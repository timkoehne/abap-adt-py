"""Lock objects (SE11, ENQU). Activation generates the function modules ENQUEUE_<name> and DEQUEUE_<name>;
in ABAP for Cloud Development a lock object is used through CL_ABAP_LOCK_OBJECT_FACTORY instead.
"""

import xml.etree.ElementTree as et
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from ..compat_typing import List, Optional, TypedDict, Union
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .activate import activate_objects
from .create import _header, _post_object

LOCK_OBJECTS = "/sap/bc/adt/ddic/lockobjects/sources"
CONTENT_TYPE = "application/vnd.sap.adt.lockobjects.v1+xml"
ADTCORE = "{http://www.sap.com/adt/core}"
ENQU = "{http://www.sap.com/adt/ddic/enqu}"


def lock_object_uri(name: str) -> str:
    return f"{LOCK_OBJECTS}/{quote(name.lower(), safe='')}"


class LockTable(TypedDict):
    table: str
    # E write lock, S shared lock, X exclusive (not cumulative)
    lock_mode: str


class LockParameter(TypedDict):
    name: str
    table: str
    field: str
    # False: the field is not a parameter of the generated function modules
    wanted: bool


class LockObject(TypedDict):
    name: str
    description: str
    package: str
    primary_table: str
    lock_mode: str
    secondary_tables: List[LockTable]
    parameters: List[LockParameter]
    allow_rfc: bool
    # ENQUEUE_<name> and DEQUEUE_<name>, once the lock object is active
    lock_modules: List[str]
    # active or inactive
    version: str


def _parameter(parameter: Union[str, dict], primary_table: str) -> str:
    if isinstance(parameter, str):
        parameter = {"name": parameter}
    field = parameter.get("field") or parameter["name"]
    return (
        "<enqu:lockParameter>"
        f"<enqu:parameterWanted>{'false' if parameter.get('wanted') is False else 'true'}</enqu:parameterWanted>"
        f"<enqu:parameterName>{escape(parameter['name'].upper())}</enqu:parameterName>"
        f"<enqu:tableName>{escape((parameter.get('table') or primary_table).upper())}</enqu:tableName>"
        f"<enqu:fieldName>{escape(field.upper())}</enqu:fieldName>"
        "</enqu:lockParameter>"
    )


def create_lock_object(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    primary_table: str,
    lock_mode: str = "E",
    secondary_tables: Optional[List[LockTable]] = None,
    parameters: Optional[List[Union[str, dict]]] = None,
    allow_rfc: bool = False,
    language: str = "EN",
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Create a lock object and activate it, which generates ENQUEUE_<name> and DEQUEUE_<name>.

    The name starts with E (EZ... for customer objects). lock_mode: E write lock, S shared lock, X exclusive
    (not cumulative). secondary_tables are tables linked to the primary table by a foreign key, e.g.
    [{"table": "ZITEM", "lock_mode": "S"}]. parameters are the lock arguments: field names of the primary table
    (["MANDT", "ID"]) or {"name", "table", "field"}; left out, SAP takes the primary table's key fields.
    """
    name = name.upper()
    primary_table = primary_table.upper()
    secondary = "".join(
        "<enqu:secondaryTable>"
        f"<enqu:tableName>{escape(table['table'].upper())}</enqu:tableName>"
        f"<enqu:lockMode>{escape(table.get('lock_mode', lock_mode).upper())}</enqu:lockMode>"
        "</enqu:secondaryTable>"
        for table in secondary_tables or []
    )
    lock_parameters = "".join(_parameter(p, primary_table) for p in parameters or [])
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <enqu:lockobject xmlns:enqu="http://www.sap.com/adt/ddic/enqu" {_header(name, description, owner, "ENQU/DL", language)}>
        <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        <enqu:content>
            <enqu:allowRFC>{"true" if allow_rfc else "false"}</enqu:allowRFC>
            <enqu:primaryTable>
                <enqu:tableName>{escape(primary_table)}</enqu:tableName>
                <enqu:lockMode>{escape(lock_mode.upper())}</enqu:lockMode>
            </enqu:primaryTable>
            <enqu:secondaryTables>{secondary}</enqu:secondaryTables>
            <enqu:lockParameters>{lock_parameters}</enqu:lockParameters>
        </enqu:content>
    </enqu:lockobject>"""
    _post_object(http_request_parameters, LOCK_OBJECTS, body, CONTENT_TYPE, name, transport)
    if activate:
        activate_objects(http_request_parameters, [(name, lock_object_uri(name))])
    return True


def get_lock_object(http_request_parameters: HttpRequestParameters, name: str) -> LockObject:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=lock_object_uri(name),
        method="GET",
        body="",
        params={},
        accept=CONTENT_TYPE,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read lock object {name}")

    root = et.fromstring(response.text)
    content = root.find(f"{ENQU}content")
    if content is None:
        content = et.Element("empty")
    package = root.find(f"{ADTCORE}packageRef")

    def text(element: et.Element, tag: str) -> str:
        return (element.findtext(f"{ENQU}{tag}") or "").strip()

    primary = content.find(f"{ENQU}primaryTable")
    if primary is None:
        primary = et.Element("empty")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": package.get(f"{ADTCORE}name", "") if package is not None else "",
        "primary_table": text(primary, "tableName"),
        "lock_mode": text(primary, "lockMode"),
        "secondary_tables": [
            {"table": text(table, "tableName"), "lock_mode": text(table, "lockMode")}
            for table in content.iterfind(f"{ENQU}secondaryTables/{ENQU}secondaryTable")
        ],
        "parameters": [
            {
                "name": text(parameter, "parameterName"),
                "table": text(parameter, "tableName"),
                "field": text(parameter, "fieldName"),
                "wanted": text(parameter, "parameterWanted") == "true",
            }
            for parameter in content.iterfind(f"{ENQU}lockParameters/{ENQU}lockParameter")
        ],
        "allow_rfc": text(content, "allowRFC") == "true",
        "lock_modules": [
            module.get(f"{ADTCORE}name", "")
            for module in content.iterfind(f"{ENQU}lockModules/{ENQU}lockModule")
        ],
        "version": root.get(f"{ADTCORE}version", ""),
    }
