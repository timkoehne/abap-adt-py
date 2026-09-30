import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import authorization, create, lock
from helpers import PARAMS, FakeResponse, fixture

ADTCORE = "{http://www.sap.com/adt/core}"
SUSO = "{http://www.sap.com/iam/suso}"


def parse(body: str) -> et.Element:
    return et.fromstring(body.strip())


def test_create_authorization_object(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    authorization.create_authorization_object(
        PARAMS, "zadtpy_ao1", "$TMP", "desc", "DEVELOPER", "aaab",
        ["bukrs", "ACTVT"], ["02", "03"], transport="A4HK900001",
    )

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/aps/iam/suso"
    assert call["params"] == {"corrNr": "A4HK900001"}
    assert call["content_type"] == "application/vnd.sap.adt.blues.v1+xml"
    root = parse(call["body"])
    assert root.get(f"{ADTCORE}name") == "ZADTPY_AO1"
    assert root.get(f"{ADTCORE}type") == "SUSO/B"
    content = root.find(f"{SUSO}content")
    assert content.findtext(f"{SUSO}objectClassName") == "AAAB"
    assert [f.findtext(f"{SUSO}name") for f in content.iter(f"{SUSO}authField")] == ["BUKRS", "ACTVT"]
    assert [a.findtext(f"{SUSO}code") for a in content.iter(f"{SUSO}activity")] == ["02", "03"]


def test_at_most_ten_fields(fake_sap):
    with pytest.raises(ValueError, match="10 fields"):
        authorization.create_authorization_object(
            PARAMS, "ZADTPY_AO1", "$TMP", "desc", "DEVELOPER", "AAAB", [f"F{i}" for i in range(11)]
        )


def test_get_authorization_object(fake_sap):
    calls = fake_sap(authorization, FakeResponse(200, fixture("authorization_object.xml")))
    assert authorization.get_authorization_object(PARAMS, "ZADTPY_AO1") == {
        "name": "ZADTPY_AO1",
        "description": "adt-py company code",
        "package": "$TMP",
        "object_class": "AAAB",
        "fields": ["BUKRS", "ACTVT"],
        "activities": ["02", "03"],
    }
    assert calls[0]["uri"] == "/sap/bc/adt/aps/iam/suso/zadtpy_ao1"


def test_update_authorization_object(fake_sap):
    fake_sap(authorization, FakeResponse(200, fixture("authorization_object.xml")))
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    calls = fake_sap(create, FakeResponse(200))

    authorization.update_authorization_object(PARAMS, "ZADTPY_AO1", "DEVELOPER", activities=["03"])

    put = calls[0]
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/aps/iam/suso/zadtpy_ao1")
    content = parse(put["body"]).find(f"{SUSO}content")
    assert [f.findtext(f"{SUSO}name") for f in content.iter(f"{SUSO}authField")] == ["BUKRS", "ACTVT"]
    assert [a.findtext(f"{SUSO}code") for a in content.iter(f"{SUSO}activity")] == ["03"]
    assert parse(put["body"]).get(f"{ADTCORE}description") == "adt-py company code"
