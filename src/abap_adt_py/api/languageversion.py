"""ABAP language version of an object: Standard ABAP, ABAP for Cloud Development or ABAP for Key Users.

The version is the attribute adtcore:abapLanguageVersion of the object's metadata. It is changed like in the
object's properties in ADT: the metadata is saved again with the new version, which leaves the object inactive,
and activation makes it the active version. Activation fails if the code uses what the new version forbids, e.g.
an API that isn't released for cloud development; the active version then stays as it was.
"""

import re
import xml.etree.ElementTree as et

from ..compat_typing import List, Literal, Optional, TypeAlias, TypedDict
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .activate import activate_objects
from .create import _put_locked

LanguageVersions: TypeAlias = Literal["standard", "cloudDevelopment", "keyUser"]

# the values of PROGDIR-UCCHECK and DD02L-ABAP_LANGUAGE_VERSION are accepted too
_ALIASES = {
    "standard": "standard",
    "x": "standard",
    "": "standard",
    "clouddevelopment": "cloudDevelopment",
    "cloud": "cloudDevelopment",
    "5": "cloudDevelopment",
    "keyuser": "keyUser",
    "2": "keyUser",
}
_ATTRIBUTE = re.compile(r'adtcore:abapLanguageVersion="([^"]*)"')
ADTCORE = "{http://www.sap.com/adt/core}"
NAMEDITEM = "{http://www.sap.com/adt/nameditem}"


def language_version(version: str) -> str:
    """The ADT name of a language version: standard, cloudDevelopment or keyUser (also from X, 5 and 2)."""
    normalized = _ALIASES.get((version or "").strip().lower())
    if normalized is None:
        raise ValueError(
            f"unknown ABAP language version {version!r}: use standard, cloudDevelopment or keyUser"
        )
    return normalized


class LanguageVersion(TypedDict):
    name: str
    type: str
    uri: str
    # standard, cloudDevelopment or keyUser; "" for objects without a version (message classes, includes,
    # function modules, which have the version of their function group)
    version: str
    # the versions the object may have, e.g. ["keyUser", "cloudDevelopment", "standard"]
    allowed: List[str]


def _read_metadata(http_request_parameters: HttpRequestParameters, object_uri: str):
    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        method="GET",
        body="",
        params={},
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read {object_uri}")
    return response


def allowed_language_versions(
    http_request_parameters: HttpRequestParameters, object_uri: str
) -> List[str]:
    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/informationsystem/abaplanguageversions",
        method="GET",
        body="",
        params={"uri": object_uri},
        accept="application/vnd.sap.adt.nameditems.v1+xml",
    )
    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to read the allowed language versions of {object_uri}"
        )
    return [
        (item.findtext(f"{NAMEDITEM}name") or "").strip()
        for item in et.fromstring(response.text).iter(f"{NAMEDITEM}namedItem")
    ]


def get_language_version(
    http_request_parameters: HttpRequestParameters, object_uri: str
) -> LanguageVersion:
    response = _read_metadata(http_request_parameters, object_uri)
    root = et.fromstring(response.text)
    version = root.get(f"{ADTCORE}abapLanguageVersion")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "type": root.get(f"{ADTCORE}type", ""),
        "uri": object_uri,
        "version": version or "",
        "allowed": (
            allowed_language_versions(http_request_parameters, object_uri)
            if version is not None
            else []
        ),
    }


def set_language_version(
    http_request_parameters: HttpRequestParameters,
    object_uri: str,
    version: str,
    transport: Optional[str] = None,
    activate: bool = True,
) -> bool:
    """Change the language version of an object and activate it.

    Raises ActivationError if the object's code is not valid in the new version; the active version then stays
    as it was and the new one is left inactive.
    """
    version = language_version(version)
    response = _read_metadata(http_request_parameters, object_uri)
    current = _ATTRIBUTE.search(response.text)
    if current is None:
        raise ValueError(f"{object_uri} has no ABAP language version of its own")
    root = et.fromstring(response.text)
    name = root.get(f"{ADTCORE}name", "")
    if current.group(1) != version:
        # the metadata is saved as it was read, with the content type it came with
        content_type = (response.headers.get("content-type") or "application/xml").split(";")[0]
        body = _ATTRIBUTE.sub(
            f'adtcore:abapLanguageVersion="{version}"', response.text, count=1
        )
        _put_locked(http_request_parameters, object_uri, body, content_type, name, transport)
    if activate:
        activate_objects(http_request_parameters, [(name, object_uri)])
    return True
