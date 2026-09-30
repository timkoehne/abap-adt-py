import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import create, lock, messageclass
from helpers import PARAMS, FakeResponse, fixture

MC = "{http://www.sap.com/adt/MessageClass}"
HANDLE = "AD111DBD5E2316FBF7AA949C8B2AEC2B5C27CD4E"


def parse(body: str) -> et.Element:
    return et.fromstring(body.strip())


def fake_save(fake_sap, *create_responses):
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    return fake_sap(create, *create_responses)


def sent_messages(body: str):
    return [
        {key.replace(MC, ""): value for key, value in message.attrib.items()}
        for message in parse(body).iter(f"{MC}messages")
    ]


def test_get_message_class(fake_sap):
    calls = fake_sap(messageclass, FakeResponse(200, fixture("messageclass.xml")))
    message_class = messageclass.get_message_class(PARAMS, "ZADTPY_MSG")

    assert calls[0]["uri"] == "/sap/bc/adt/messageclass/zadtpy_msg"
    assert message_class["description"] == "adt-py messages"
    assert message_class["package"] == "$TMP"
    assert message_class["messages"] == [
        {"number": "001", "text": "Bin &1 is blocked", "self_explanatory": True, "documented": False},
        {"number": "002", "text": "Quantity &1 is invalid", "self_explanatory": True, "documented": False},
        {"number": "003", "text": "Needs a long text", "self_explanatory": False, "documented": True},
    ]


def test_create_message_class_saves_messages_afterwards(fake_sap):
    # SAP ignores messages when creating the class
    fake_sap(
        messageclass,
        FakeResponse(200, fixture("messageclass.xml").replace("<mc:messages", "<mc:ignored")),
    )
    calls = fake_save(fake_sap, FakeResponse(201), FakeResponse(200))

    messageclass.create_message_class(
        PARAMS, "zadtpy_msg", "$TMP", "desc", "DEVELOPER",
        messages=[{"number": "1", "text": "Bin &1 is blocked"}],
    )

    post, put = calls
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/messageclass")
    assert sent_messages(post["body"]) == []
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/messageclass/zadtpy_msg")
    assert put["params"] == {"lockHandle": HANDLE}
    assert sent_messages(put["body"]) == [
        {"msgno": "001", "msgtext": "Bin &1 is blocked", "selfexplainatory": "true", "lockhandle": HANDLE}
    ]


def test_set_messages_keeps_unchanged_values(fake_sap):
    fake_sap(messageclass, FakeResponse(200, fixture("messageclass.xml")))
    calls = fake_save(fake_sap, FakeResponse(200))

    messageclass.set_messages(
        PARAMS, "ZADTPY_MSG",
        [{"number": "003", "text": "New text"}, {"number": "004", "text": "Added", "self_explanatory": False}],
        "DEVELOPER", transport="A4HK900001",
    )

    put = calls[0]
    assert put["params"] == {"lockHandle": HANDLE, "corrNr": "A4HK900001"}
    assert [(m["msgno"], m["msgtext"], m["selfexplainatory"]) for m in sent_messages(put["body"])] == [
        ("003", "New text", "false"),
        ("004", "Added", "false"),
    ]
    assert list(parse(put["body"]).iter(f"{MC}deletedmessages")) == []


def test_set_messages_can_delete_the_others(fake_sap):
    fake_sap(messageclass, FakeResponse(200, fixture("messageclass.xml")))
    calls = fake_save(fake_sap, FakeResponse(200))

    messageclass.set_messages(
        PARAMS, "ZADTPY_MSG", [{"number": "001", "text": "Only"}], "DEVELOPER", delete_others=True
    )

    deleted = [m.get(f"{MC}msgno") for m in parse(calls[0]["body"]).iter(f"{MC}deletedmessages")]
    assert deleted == ["002", "003"]


def test_delete_messages(fake_sap):
    fake_sap(messageclass, FakeResponse(200, fixture("messageclass.xml")))
    calls = fake_save(fake_sap, FakeResponse(200))

    messageclass.delete_messages(PARAMS, "ZADTPY_MSG", ["2"], "DEVELOPER")

    body = parse(calls[0]["body"])
    assert [m.get(f"{MC}msgno") for m in body.iter(f"{MC}deletedmessages")] == ["002"]
    assert sent_messages(calls[0]["body"]) == []


def test_delete_unknown_message_fails(fake_sap):
    fake_sap(messageclass, FakeResponse(200, fixture("messageclass.xml")))
    with pytest.raises(ValueError, match="no message 999"):
        messageclass.delete_messages(PARAMS, "ZADTPY_MSG", ["999"], "DEVELOPER")


@pytest.mark.parametrize("number", ["1000", "A1", ""])
def test_invalid_message_numbers(fake_sap, number):
    fake_sap(messageclass, FakeResponse(200, fixture("messageclass.xml")))
    with pytest.raises(ValueError, match="three digits"):
        messageclass.set_messages(PARAMS, "ZADTPY_MSG", [{"number": number, "text": "x"}], "DEVELOPER")
