"""Errors raised by abap_adt_py.

All errors derive from AdtError, so ``except AdtError`` catches everything the
library raises for SAP responses. AdtError derives from Exception, so existing
``except Exception`` handlers keep working.

    AdtError
    ├── AuthenticationError      login failed (wrong user or password)
    ├── SessionError             session or CSRF token expired, log in again
    ├── NotFoundError            object, check variant, ... does not exist
    ├── LockError
    │   ├── ObjectLockedError    object is locked by another user or session
    │   └── InvalidLockHandleError  object not locked, or the lock handle is wrong
    ├── ActivationError          activation failed, see .messages
    ├── TransportError           transport request could not be released, ...
    ├── QueryError               SQL query failed (data preview)
    └── ClassRunError            runtime error while running a class
"""

import html
import re
import xml.etree.ElementTree as et

from .compat_typing import List, Optional


class AdtError(Exception):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        sap_type: str = "",
        sap_message: str = "",
        response_text: str = "",
    ):
        super().__init__(message)
        # HTTP status of the failed request, None if the error isn't about a response
        self.status_code = status_code
        # SAP's exception type, e.g. ExceptionResourceNotFound
        self.sap_type = sap_type
        # SAP's message text, e.g. "Z_TEST does not exist"
        self.sap_message = sap_message
        # the complete response body
        self.response_text = response_text


class AuthenticationError(AdtError):
    pass


class SessionError(AdtError):
    pass


class NotFoundError(AdtError):
    pass


class LockError(AdtError):
    pass


class ObjectLockedError(LockError):
    pass


class InvalidLockHandleError(LockError):
    pass


class ActivationError(AdtError):
    def __init__(self, message: str, messages: Optional[List[dict]] = None, **kwargs):
        super().__init__(message, **kwargs)
        # the activation messages, e.g. [{"type": "E", "shortText": "...", "href": ...}]
        self.messages = messages or []


class TransportError(AdtError):
    pass


class QueryError(AdtError):
    pass


class ClassRunError(AdtError):
    pass


def _parse_sap_error(text: str):
    """SAP's exception type and message from an error response body."""
    if "<" not in text:
        return "", text.strip()

    try:
        root = et.fromstring(text)
    except et.ParseError:
        root = None

    if root is not None:
        sap_type = root.find("type")
        message = root.findtext("message", "")
        # messages like "I::000" are placeholders without any text
        if re.fullmatch(r"\w*::\d+", message.strip()):
            message = ""
        return (sap_type.get("id", "") if sap_type is not None else ""), message.strip()

    # HTML error pages: runtime errors carry the message in <span id="msgText">
    match = re.search(r'<span id="msgText">(.*?)</span>', text, re.S) or re.search(
        r"<title>(.*?)</title>", text, re.S
    )
    if match:
        return "", re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    return "", ""


def error_from_response(response, action: str, error_class=None) -> AdtError:
    """Build the error for a failed response.

    action describes what failed, e.g. "Failed to lock /sap/bc/adt/...".
    error_class is used when the status doesn't map to a more specific error.
    """
    status = response.status_code
    text = response.text or ""
    sap_type, sap_message = _parse_sap_error(text)
    if not sap_message:
        sap_message = getattr(response, "reason", "") or text.strip()[:500]

    headers = getattr(response, "headers", None) or {}
    if status == 401:
        cls = AuthenticationError
    elif status == 403 and headers.get("x-csrf-token", "").lower() == "required":
        cls = SessionError
    elif status == 404:
        cls = NotFoundError
    elif status == 423:
        cls = InvalidLockHandleError
    else:
        cls = error_class or AdtError

    return cls(
        f"{status} - {action}: {sap_message}",
        status_code=status,
        sap_type=sap_type,
        sap_message=sap_message,
        response_text=text,
    )
