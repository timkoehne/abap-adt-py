import json
import xml.etree.ElementTree as et

from abap_adt_py.api import applicationjob, create, lock
from helpers import PARAMS, FakeResponse, fixture

ADTCORE = "{http://www.sap.com/adt/core}"


def _install(fake_sap, monkeypatch, *reads):
    writes = fake_sap(create, FakeResponse(201), FakeResponse(200))
    locks = fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    read_calls = fake_sap(applicationjob, *reads)
    activations = []
    monkeypatch.setattr(applicationjob, "activate_objects", lambda params, objects: activations.append(objects))
    return writes, locks, read_calls, activations


def test_create_job_catalog_entry(fake_sap, monkeypatch):
    writes, locks, reads, activations = _install(
        fake_sap, monkeypatch, FakeResponse(200, fixture("job_catalog_entry.json"))
    )
    applicationjob.create_job_catalog_entry(
        PARAMS, "zadtpjc_r", "$TMP", "adt test", "DEVELOPER", "zcl_adtpjob_r",
        parameters=[{"name": "P_ID", "mandatory": True}], transport="A4HK900001",
    )

    post, put = writes
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/applicationjob/catalogs")
    assert post["content_type"] == "application/vnd.sap.adt.blues.v2+xml"
    assert post["params"] == {"corrNr": "A4HK900001"}
    root = et.fromstring(post["body"].strip())
    assert (root.get(f"{ADTCORE}name"), root.get(f"{ADTCORE}type")) == ("ZADTPJC_R", "SAJC")
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/applicationjob/catalogs/zadtpjc_r/source/main")
    assert json.loads(put["body"]) == {
        "formatVersion": "1",
        "header": {"description": "adt test", "originalLanguage": "en"},
        "generalInformation": {"className": "ZCL_ADTPJOB_R"},
        "parameters": [{"name": "P_ID", "mandatory": True}],
    }
    assert [c["uri"] for c in locks] == ["/sap/bc/adt/applicationjob/catalogs/zadtpjc_r"] * 2
    # the saved source is read before the activation, which fails otherwise
    assert reads[0]["uri"] == "/sap/bc/adt/applicationjob/catalogs/zadtpjc_r/source/main"
    assert activations == [[("ZADTPJC_R", "/sap/bc/adt/applicationjob/catalogs/zadtpjc_r")]]


def test_get_job_catalog_entry(fake_sap):
    fake_sap(applicationjob, FakeResponse(200, fixture("job_catalog_entry.json")))
    entry = applicationjob.get_job_catalog_entry(PARAMS, "ZADTPJC_R")
    assert (entry["name"], entry["description"], entry["class_name"]) == ("ZADTPJC_R", "adt test", "ZCL_ADTPJOB_R")
    assert entry["parameters"] == [{"name": "P_ID", "mandatory": True}, {"name": "S_DATE"}]


def test_create_job_template_with_single_values_and_ranges(fake_sap, monkeypatch):
    writes, _, _, _ = _install(fake_sap, monkeypatch, FakeResponse(200, fixture("job_template.json")))
    applicationjob.create_job_template(
        PARAMS, "ZADTPJT_R", "$TMP", "adt test", "DEVELOPER", "zadtpjc_r",
        parameters={"p_id": "A1", "S_DATE": [{"sign": "I", "option": "BT", "low": "20250101", "high": "20251231"}]},
    )
    post, put = writes
    assert post["uri"] == "/sap/bc/adt/applicationjob/templates"
    assert 'adtcore:type="SAJT"' in post["body"]
    source = json.loads(put["body"])
    assert source["generalInformation"] == {"catalogName": "ZADTPJC_R"}
    assert source["parameters"] == json.loads(fixture("job_template.json"))["parameters"]


def test_get_job_template(fake_sap):
    fake_sap(applicationjob, FakeResponse(200, fixture("job_template.json")))
    template = applicationjob.get_job_template(PARAMS, "ZADTPJT_R")
    assert template["catalog_entry"] == "ZADTPJC_R"
    assert template["parameters"] == {
        "P_ID": "A1",
        "S_DATE": [{"sign": "include", "option": "between", "low": "20250101", "high": "20251231"}],
    }


def test_create_application_log_object(fake_sap, monkeypatch):
    writes, _, _, activations = _install(fake_sap, monkeypatch, FakeResponse(200, fixture("application_log_object.json")))
    applicationjob.create_application_log_object(
        PARAMS, "zadtplog_r", "$TMP", "adt test", "DEVELOPER", [{"name": "run", "description": "Runs"}]
    )
    post, put = writes
    assert post["uri"] == "/sap/bc/adt/applicationlog/objects"
    assert post["content_type"] == "application/vnd.sap.adt.blues.v1+xml"
    assert 'adtcore:type="APLO/TYP"' in post["body"]
    assert json.loads(put["body"]) == json.loads(fixture("application_log_object.json"))
    assert activations == [[("ZADTPLOG_R", "/sap/bc/adt/applicationlog/objects/zadtplog_r")]]


def test_get_application_log_object(fake_sap):
    calls = fake_sap(applicationjob, FakeResponse(200, fixture("application_log_object.json")))
    assert applicationjob.get_application_log_object(PARAMS, "zadtplog_r") == {
        "name": "ZADTPLOG_R",
        "description": "adt test",
        "subobjects": [{"name": "RUN", "description": "Runs"}],
    }
    assert calls[0]["accept"] == "application/json"
