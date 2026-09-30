"""Message classes and their messages."""

import xml.etree.ElementTree as et
from xml.sax.saxutils import quoteattr

from ..compat_typing import List, Optional, TypedDict
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .create import _header, _post_object, _put_locked

ADTCORE = "{http://www.sap.com/adt/core}"
MC = "{http://www.sap.com/adt/MessageClass}"
CONTENT_TYPE = "application/vnd.sap.adt.mc.messageclass+xml"


class Message(TypedDict, total=False):
    # three digits, e.g. "001"
    number: str
    # up to 73 characters, &1 to &4 are placeholders
    text: str
    # True if the text needs no long text to explain it (the default)
    self_explanatory: bool
    # True if the message has a long text
    documented: bool


class MessageClass(TypedDict):
    name: str
    description: str
    package: str
    messages: List[Message]


def _uri(name: str) -> str:
    return f"/sap/bc/adt/messageclass/{name.lower()}"


def _number(number) -> str:
    number = str(number).strip()
    if not number.isdigit() or len(number) > 3:
        raise ValueError(f"message numbers have up to three digits, got {number!r}")
    return number.zfill(3)


def get_message_class(
    http_request_parameters: HttpRequestParameters, name: str
) -> MessageClass:
    response = request(
        http_request_parameters,
        uri=_uri(name),
        method="GET",
        body="",
        params={},
        accept=CONTENT_TYPE,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read message class {name}")

    root = et.fromstring(response.text)
    package = root.find(f"{ADTCORE}packageRef")
    return {
        "name": root.get(f"{ADTCORE}name", ""),
        "description": root.get(f"{ADTCORE}description", ""),
        "package": package.get(f"{ADTCORE}name", "") if package is not None else "",
        "messages": [
            {
                "number": message.get(f"{MC}msgno", ""),
                "text": message.get(f"{MC}msgtext", ""),
                "self_explanatory": message.get(f"{MC}selfexplainatory") == "true",
                "documented": message.get(f"{MC}documented") == "true",
            }
            for message in root.iter(f"{MC}messages")
        ],
    }


def _body(
    message_class: MessageClass,
    owner: str,
    language: str,
    changed: List[Message],
    deleted: List[str],
    lock_handle: str = "",
) -> str:
    # SAP only saves the self-explanatory flag of an existing message if the message
    # carries a lock handle, so every changed message gets the one of the class
    messages = "".join(
        f"<mc:messages mc:msgno={quoteattr(message['number'])} "
        f"mc:msgtext={quoteattr(message.get('text', ''))} "
        f"mc:selfexplainatory=\"{'true' if message.get('self_explanatory', True) else 'false'}\" "
        f"mc:lockhandle={quoteattr(lock_handle)}/>"
        for message in changed
    )
    deleted_messages = "".join(
        f"<mc:deletedmessages mc:msgno={quoteattr(number)}/>" for number in deleted
    )
    header = _header(
        message_class["name"], message_class["description"], owner, "MSAG/N", language
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <mc:messageClass xmlns:mc="http://www.sap.com/adt/MessageClass" {header}>
        <adtcore:packageRef adtcore:name={quoteattr(message_class["package"])}/>
        {messages}{deleted_messages}
    </mc:messageClass>"""


def _save(
    http_request_parameters: HttpRequestParameters,
    message_class: MessageClass,
    owner: str,
    language: str,
    transport: Optional[str],
    changed: List[Message],
    deleted: List[str],
) -> bool:
    return _put_locked(
        http_request_parameters,
        _uri(message_class["name"]),
        # the lock handle is only known once the class is locked
        lambda lock_handle: _body(
            message_class, owner, language, changed, deleted, lock_handle
        ),
        CONTENT_TYPE,
        message_class["name"],
        transport,
    )


def create_message_class(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    messages: Optional[List[Message]] = None,
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    """Create a message class, optionally with messages."""
    name = name.upper()
    message_class: MessageClass = {
        "name": name,
        "description": description,
        "package": package,
        "messages": [],
    }
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/messageclass",
        _body(message_class, owner, language, [], []),
        CONTENT_TYPE,
        name,
        transport,
    )
    if messages:
        # SAP ignores messages when creating the class
        set_messages(
            http_request_parameters, name, messages, owner, language, transport
        )
    return True


def set_messages(
    http_request_parameters: HttpRequestParameters,
    message_class: str,
    messages: List[Message],
    owner: str,
    language: str = "EN",
    transport: Optional[str] = None,
    delete_others: bool = False,
) -> bool:
    """Add or change messages, e.g. [{"number": "001", "text": "Bin &1 is blocked"}].

    Messages not in the list are kept, unless delete_others is True.
    """
    current = get_message_class(http_request_parameters, message_class)
    existing = {message["number"]: message for message in current["messages"]}

    changed = []
    for message in messages:
        if "number" not in message:
            raise ValueError("every message needs a number")
        number = _number(message["number"])
        old = existing.get(number, {})
        changed.append(
            {
                "number": number,
                "text": message.get("text", old.get("text", "")),
                "self_explanatory": message.get(
                    "self_explanatory", old.get("self_explanatory", True)
                ),
            }
        )
    numbers = {message["number"] for message in changed}
    deleted = [n for n in existing if n not in numbers] if delete_others else []

    return _save(
        http_request_parameters, current, owner, language, transport, changed, deleted
    )


def delete_messages(
    http_request_parameters: HttpRequestParameters,
    message_class: str,
    numbers: List[str],
    owner: str,
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    current = get_message_class(http_request_parameters, message_class)
    existing = {message["number"] for message in current["messages"]}
    deleted = [_number(number) for number in numbers]
    missing = [number for number in deleted if number not in existing]
    if missing:
        raise ValueError(
            f"message class {message_class} has no message {', '.join(missing)}"
        )
    return _save(http_request_parameters, current, owner, language, transport, [], deleted)
