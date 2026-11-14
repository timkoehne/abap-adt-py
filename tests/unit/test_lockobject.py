import xml.etree.ElementTree as et

from abap_adt_py.api import create, lockobject
from helpers import PARAMS, FakeResponse, fixture

ENQU = "{http://www.sap.com/adt/ddic/enqu}"
ADTCORE = "{http://www.sap.com/adt/core}"


def test_create_lock_object(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    lockobject.create_lock_object(
        PARAMS, "ezadtlk", "$TMP", "adt test", "DEVELOPER", "zadtlkh",
        secondary_tables=[{"table": "zadtlki", "lock_mode": "s"}],
        parameters=["mandt", "ID", {"name": "POS", "table": "zadtlki", "field": "pos"}],
        transport="A4HK900001", activate=False,
    )

    post = calls[0]
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/ddic/lockobjects/sources")
    assert post["content_type"] == "application/vnd.sap.adt.lockobjects.v1+xml"
    assert post["params"] == {"corrNr": "A4HK900001"}
    root = et.fromstring(post["body"].strip())
    assert (root.get(f"{ADTCORE}name"), root.get(f"{ADTCORE}type")) == ("EZADTLK", "ENQU/DL")
    content = root.find(f"{ENQU}content")
    assert content.findtext(f"{ENQU}primaryTable/{ENQU}tableName") == "ZADTLKH"
    assert content.findtext(f"{ENQU}primaryTable/{ENQU}lockMode") == "E"
    assert content.findtext(f"{ENQU}secondaryTables/{ENQU}secondaryTable/{ENQU}lockMode") == "S"
    assert [
        (p.findtext(f"{ENQU}parameterName"), p.findtext(f"{ENQU}tableName"), p.findtext(f"{ENQU}fieldName"))
        for p in content.iter(f"{ENQU}lockParameter")
    ] == [("MANDT", "ZADTLKH", "MANDT"), ("ID", "ZADTLKH", "ID"), ("POS", "ZADTLKI", "POS")]


def test_without_parameters_sap_proposes_them(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    lockobject.create_lock_object(PARAMS, "EZADTLK", "$TMP", "adt test", "DEVELOPER", "ZADTLKH", activate=False)
    root = et.fromstring(calls[0]["body"].strip())
    assert list(root.find(f"{ENQU}content/{ENQU}lockParameters")) == []


def test_get_lock_object(fake_sap):
    calls = fake_sap(lockobject, FakeResponse(200, fixture("lock_object.xml")))
    assert lockobject.get_lock_object(PARAMS, "EZADTLK") == {
        "name": "EZADTLK",
        "description": "adt test",
        "package": "$TMP",
        "primary_table": "ZADTLKH",
        "lock_mode": "E",
        "secondary_tables": [{"table": "ZADTLKI", "lock_mode": "S"}],
        "parameters": [
            {"name": "MANDT", "table": "ZADTLKH", "field": "MANDT", "wanted": True},
            {"name": "ID", "table": "ZADTLKH", "field": "ID", "wanted": True},
            {"name": "POS", "table": "ZADTLKI", "field": "POS", "wanted": True},
        ],
        "allow_rfc": True,
        "lock_modules": ["ENQUEUE_EZADTLK", "DEQUEUE_EZADTLK"],
        "version": "active",
    }
    assert calls[0]["uri"] == "/sap/bc/adt/ddic/lockobjects/sources/ezadtlk"
