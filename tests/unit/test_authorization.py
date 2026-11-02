import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import authorization, create, delete, lock, syntax
from abap_adt_py.exceptions import AdtError
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


AUTH = "{http://www.sap.com/iam/auth}"


def test_create_authorization_field(fake_sap):
    calls = fake_sap(create, FakeResponse(201), FakeResponse(200))
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    authorization.create_authorization_field(
        PARAMS, "zadtpy_af1", "$TMP", "DEVELOPER", "s_carr_id", "scarr", transport="A4HK900001"
    )

    post, put = calls
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/aps/iam/auth")
    assert post["params"] == {"corrNr": "A4HK900001"}
    assert post["content_type"] == "application/vnd.sap.adt.blues.v1+xml"
    root = parse(post["body"])
    assert root.get(f"{ADTCORE}name") == "ZADTPY_AF1"
    assert root.get(f"{ADTCORE}type") == "AUTH"
    assert root.findtext(f"{AUTH}content/{AUTH}rollName") == ""

    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/aps/iam/auth/zadtpy_af1")
    assert put["params"]["corrNr"] == "A4HK900001"
    content = parse(put["body"]).find(f"{AUTH}content")
    assert content.findtext(f"{AUTH}fieldName") == "ZADTPY_AF1"
    assert content.findtext(f"{AUTH}rollName") == "S_CARR_ID"
    assert content.findtext(f"{AUTH}checkTable") == "SCARR"


def test_create_authorization_field_reports_check_errors(fake_sap):
    fake_sap(create, FakeResponse(201), FakeResponse(400, fixture("authorization_field_save_error.xml")))
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    checks = fake_sap(syntax, FakeResponse(200, fixture("authorization_field_check.xml")))
    deletes = fake_sap(delete, FakeResponse(200, fixture("deletion_success.xml")))

    with pytest.raises(AdtError) as error:
        authorization.create_authorization_field(
            PARAMS, "ZADTPY_AF1", "$TMP", "DEVELOPER", "S_CARR_ID", "T001"
        )

    # only the errors, not the warning and the information
    assert str(error.value) == (
        "400 - Failed to save ZADTPY_AF1: Object T001 does not exist in TADIR; "
        "Check table T001 does not actively exist."
    )
    assert "application/vnd.sap.adt.blues.v1+xml" in checks[0]["body"]
    # the empty field is removed again
    assert "/sap/bc/adt/aps/iam/auth/zadtpy_af1" in deletes[0]["body"]


def test_get_authorization_field(fake_sap):
    calls = fake_sap(authorization, FakeResponse(200, fixture("authorization_field.xml")))
    assert authorization.get_authorization_field(PARAMS, "ZADTPY_AF1") == {
        "name": "ZADTPY_AF1",
        "description": "Airline Code",
        "package": "$TMP",
        "data_element": "S_CARR_ID",
        "check_table": "SCARR",
    }
    assert calls[0]["uri"] == "/sap/bc/adt/aps/iam/auth/zadtpy_af1"


def test_update_authorization_field(fake_sap):
    fake_sap(authorization, FakeResponse(200, fixture("authorization_field.xml")))
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    calls = fake_sap(create, FakeResponse(200))

    authorization.update_authorization_field(PARAMS, "ZADTPY_AF1", "DEVELOPER", check_table="")

    put = calls[0]
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/aps/iam/auth/zadtpy_af1")
    content = parse(put["body"]).find(f"{AUTH}content")
    assert content.findtext(f"{AUTH}rollName") == "S_CARR_ID"
    assert content.findtext(f"{AUTH}checkTable") == ""
