"""Authorization objects (SU21) and authorization fields (SU20)."""

import xml.etree.ElementTree as et
from xml.sax.saxutils import escape, quoteattr

from ..compat_typing import List, Optional, TypedDict
from ..exceptions import AdtError, error_from_response
from ..http_request import HttpRequestParameters, request
from .create import _header, _post_object, _put_locked
from .delete import delete_objects
from .syntax import syntax_check

ADTCORE = "{http://www.sap.com/adt/core}"
SUSO = "{http://www.sap.com/iam/suso}"
AUTH = "{http://www.sap.com/iam/auth}"
CONTENT_TYPE = "application/vnd.sap.adt.blues.v1+xml"


class AuthorizationObject(TypedDict):
    name: str
    description: str
    package: str
    # e.g. AAAB (cross-application authorization objects)
    object_class: str
    # authorization fields, e.g. ["BUKRS", "ACTVT"]
    fields: List[str]
    # allowed values of ACTVT, e.g. ["02", "03"]
    activities: List[str]


def _uri(name: str) -> str:
    return f"/sap/bc/adt/aps/iam/suso/{name.lower()}"


def _body(authorization_object: AuthorizationObject, owner: str, language: str) -> str:
    if len(authorization_object["fields"]) > 10:
        raise ValueError("an authorization object has at most 10 fields")
    fields = "".join(
        f"<suso:authField><suso:name>{escape(field.upper())}</suso:name></suso:authField>"
        for field in authorization_object["fields"]
    )
    activities = "".join(
        f"<suso:activity><suso:code>{escape(activity)}</suso:code></suso:activity>"
        for activity in authorization_object["activities"]
    )
    header = _header(
        authorization_object["name"],
        authorization_object["description"],
        owner,
        "SUSO/B",
        language,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <suso:suso xmlns:suso="http://www.sap.com/iam/suso" {header}>
        <adtcore:packageRef adtcore:name={quoteattr(authorization_object["package"])}/>
        <suso:content>
            <suso:objectClassName>{escape(authorization_object["object_class"].upper())}</suso:objectClassName>
            <suso:authFields>{fields}</suso:authFields>
            <suso:activities>{activities}</suso:activities>
        </suso:content>
    </suso:suso>"""


def create_authorization_object(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    object_class: str,
    fields: List[str],
    activities: Optional[List[str]] = None,
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    """Create an authorization object, e.g. fields ["BUKRS", "ACTVT"] and activities
    ["02", "03"]. Activities are the allowed values of the ACTVT field.
    """
    authorization_object: AuthorizationObject = {
        "name": name.upper(),
        "description": description,
        "package": package,
        "object_class": object_class,
        "fields": list(fields),
        "activities": list(activities or []),
    }
    return _post_object(
        http_request_parameters,
        "/sap/bc/adt/aps/iam/suso",
        _body(authorization_object, owner, language),
        CONTENT_TYPE,
        name,
        transport,
    )


def get_authorization_object(
    http_request_parameters: HttpRequestParameters, name: str
) -> AuthorizationObject:
    response = request(
        http_request_parameters,
        uri=_uri(name),
        method="GET",
        body="",
        params={},
        accept=CONTENT_TYPE,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read authorization object {name}")

    root = et.fromstring(response.text)
    content = root.find(f"{SUSO}content")
    if content is None:
        content = et.Element("empty")
    package = root.find(f"{ADTCORE}packageRef")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": package.get(f"{ADTCORE}name", "") if package is not None else "",
        "object_class": (content.findtext(f"{SUSO}objectClassName") or "").strip(),
        "fields": [
            (field.findtext(f"{SUSO}name") or "").strip()
            for field in content.iter(f"{SUSO}authField")
        ],
        "activities": [
            (activity.findtext(f"{SUSO}code") or "").strip()
            for activity in content.findall(f"{SUSO}activities/{SUSO}activity")
        ],
    }


def update_authorization_object(
    http_request_parameters: HttpRequestParameters,
    name: str,
    owner: str,
    language: str = "EN",
    transport: Optional[str] = None,
    description: Optional[str] = None,
    object_class: Optional[str] = None,
    fields: Optional[List[str]] = None,
    activities: Optional[List[str]] = None,
) -> bool:
    """Change an authorization object. Arguments left at None keep their value."""
    authorization_object = get_authorization_object(http_request_parameters, name)
    changes = {
        "description": description,
        "object_class": object_class,
        "fields": fields,
        "activities": activities,
    }
    authorization_object.update({k: v for k, v in changes.items() if v is not None})  # type: ignore[typeddict-item]
    return _put_locked(
        http_request_parameters,
        _uri(name),
        _body(authorization_object, owner, language),
        CONTENT_TYPE,
        name,
        transport,
    )


class AuthorizationField(TypedDict):
    name: str
    # the data element's text, SAP doesn't keep a description of its own
    description: str
    package: str
    data_element: str
    # table with the allowed values, empty if there is none
    check_table: str


def _field_uri(name: str) -> str:
    return f"/sap/bc/adt/aps/iam/auth/{name.lower()}"


def _field_body(
    name: str, package: str, owner: str, language: str, data_element: str, check_table: str
) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <auth:auth xmlns:auth="http://www.sap.com/iam/auth" {_header(name, "", owner, "AUTH", language)}>
        <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        <auth:content>
            <auth:fieldName>{escape(name)}</auth:fieldName>
            <auth:rollName>{escape(data_element.upper())}</auth:rollName>
            <auth:checkTable>{escape(check_table.upper())}</auth:checkTable>
        </auth:content>
    </auth:auth>"""


def _save_field(
    http_request_parameters: HttpRequestParameters,
    name: str,
    body: str,
    transport: Optional[str],
) -> None:
    try:
        _put_locked(
            http_request_parameters, _field_uri(name), body, CONTENT_TYPE, name, transport
        )
    except AdtError as error:
        if error.status_code != 400:
            raise
        # SAP only says that the field contains errors, its check tells which
        errors = [
            message["short_text"]
            for message in syntax_check(
                http_request_parameters,
                _field_uri(name),
                _field_uri(name),
                body,
                content_type=CONTENT_TYPE,
            )
            if message["type"] in ("E", "A")
        ]
        if not errors:
            raise
        message = "; ".join(errors)
        raise AdtError(
            f"400 - Failed to save {name}: {message}",
            status_code=400,
            sap_type=error.sap_type,
            sap_message=message,
            response_text=error.response_text,
        ) from error


def create_authorization_field(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    owner: str,
    data_element: str,
    check_table: str = "",
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    """Create an authorization field, typed by an existing data element.

    The field is active right away and takes its description from the data element.
    """
    name = name.upper()
    # created empty and saved afterwards: only saving explains why a definition is wrong
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/aps/iam/auth",
        _field_body(name, package, owner, language, "", ""),
        CONTENT_TYPE,
        name,
        transport,
    )
    try:
        _save_field(
            http_request_parameters,
            name,
            _field_body(name, package, owner, language, data_element, check_table),
            transport,
        )
    except AdtError:
        try:
            delete_objects(http_request_parameters, [_field_uri(name)], transport)
        except AdtError:
            pass
        raise
    return True


def get_authorization_field(
    http_request_parameters: HttpRequestParameters, name: str
) -> AuthorizationField:
    response = request(
        http_request_parameters,
        uri=_field_uri(name),
        method="GET",
        body="",
        params={},
        accept=CONTENT_TYPE,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read authorization field {name}")

    root = et.fromstring(response.text)
    content = root.find(f"{AUTH}content")
    if content is None:
        content = et.Element("empty")
    package = root.find(f"{ADTCORE}packageRef")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": package.get(f"{ADTCORE}name", "") if package is not None else "",
        "data_element": (content.findtext(f"{AUTH}rollName") or "").strip(),
        "check_table": (content.findtext(f"{AUTH}checkTable") or "").strip(),
    }


def update_authorization_field(
    http_request_parameters: HttpRequestParameters,
    name: str,
    owner: str,
    language: str = "EN",
    transport: Optional[str] = None,
    data_element: Optional[str] = None,
    check_table: Optional[str] = None,
) -> bool:
    """Change an authorization field. Arguments left at None keep their value,
    check_table="" removes the check table.
    """
    field = get_authorization_field(http_request_parameters, name)
    _save_field(
        http_request_parameters,
        field["name"],
        _field_body(
            field["name"],
            field["package"],
            owner,
            language,
            field["data_element"] if data_element is None else data_element,
            field["check_table"] if check_table is None else check_table,
        ),
        transport,
    )
    return True
