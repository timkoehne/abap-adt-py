import json
import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import checkvariant, create, lock
from abap_adt_py.exceptions import NotFoundError
from helpers import PARAMS, FakeResponse, fixture

CHKVCHECK = "{http://www.sap.com/wbobj/atc/chkvCheck}"
CHKO = "{http://www.sap.com/wbobj/atc/chko}"
ADTCORE = "{http://www.sap.com/adt/core}"


def test_list_atc_checks(fake_sap):
    fake_sap(checkvariant, FakeResponse(200, fixture("atc_check_formtemplate.xml")))
    checks = checkvariant.list_atc_checks(PARAMS)
    assert len(checks) == 16
    assert checks[0] == {
        "name": "SLIN_VERS",
        "description": "ABAP Language Version Check",
        "category": "SYCM_CLOUD_READINESS",
        "category_description": "ABAP Cloud Readiness",
    }
    assert checks[-1]["category"] == "CI_DICTIONARY"


def test_get_atc_check(fake_sap):
    calls = fake_sap(
        checkvariant,
        FakeResponse(200, fixture("atc_check_sysubrc.xml")),
        FakeResponse(200, fixture("atc_check_defaults_sysubrc.json")),
    )
    check = checkvariant.get_atc_check(PARAMS, "ci_sysubrc")

    assert calls[0]["uri"] == "/sap/bc/adt/atc/checks/ci_sysubrc"
    assert calls[1]["params"] == {"test": "CI_SYSUBRC"}
    assert (check["name"], check["description"], check["category"]) == (
        "CI_SYSUBRC", "Check of SY-SUBRC Handling", "CI_ROBUSTNESS"
    )
    assert check["parameters"][0] == {
        "name": "ReadDB", "description": "Reading DB Accesses", "kind": "value", "default": "false"
    }
    assert check["parameters"][-1] == {
        "name": "AnyStatement", "description": check["parameters"][-1]["description"], "kind": "list", "default": []
    }


def test_unknown_check(fake_sap):
    fake_sap(checkvariant, FakeResponse(404, fixture("error_not_found.xml")))
    with pytest.raises(NotFoundError, match="CI_NONE is not an ATC check"):
        checkvariant.get_atc_check(PARAMS, "ci_none")


def test_get_check_variant(fake_sap):
    calls = fake_sap(checkvariant, FakeResponse(200, fixture("check_variant.xml")))
    variant = checkvariant.get_check_variant(PARAMS, "ZADT_CHKV1")

    assert calls[0]["uri"] == "/sap/bc/adt/atc/checkvariants/zadt_chkv1"
    assert calls[0]["accept"] == "application/vnd.sap.adt.chkvv4+xml"
    assert (variant["name"], variant["description"], variant["package"], variant["version"]) == (
        "ZADT_CHKV1", "adt test", "$TMP", "active"
    )
    assert [check["name"] for check in variant["checks"]] == ["CI_SYSUBRC", "CI_NO_ORDER_BY"]
    assert variant["checks"][0]["parameters"]["ReadDB"] == "true"
    assert variant["checks"][0]["parameters"]["AnyStatement"] == []


def test_variant_not_found(fake_sap):
    fake_sap(checkvariant, FakeResponse(404, fixture("check_variant_missing.xml")))
    with pytest.raises(NotFoundError, match="Error while importing object"):
        checkvariant.get_check_variant(PARAMS, "ZADT_NONE")


def test_save_creates_the_variant_with_defaults_and_overrides(fake_sap, monkeypatch):
    calls = fake_sap(
        checkvariant,
        FakeResponse(200, fixture("atc_check_sysubrc.xml")),
        FakeResponse(200, fixture("atc_check_defaults_sysubrc.json")),
        FakeResponse(404, fixture("check_variant_missing.xml")),
    )
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    writes = fake_sap(create, FakeResponse(201), FakeResponse(200))
    activations = []
    monkeypatch.setattr(checkvariant, "activate_objects", lambda params, objects: activations.append(objects))

    checkvariant.save_check_variant(
        PARAMS, "zadt_chkv1", "$TMP", "adt test", "DEVELOPER",
        [{"name": "ci_sysubrc", "parameters": {"readdb": True, "AnyStatement": ["MODIFY"]}}],
    )

    assert [c["uri"] for c in calls] == [
        "/sap/bc/adt/atc/checks/ci_sysubrc",
        "/sap/bc/adt/atc/checkvariants/formtemplate",
        "/sap/bc/adt/atc/checkvariants/zadt_chkv1",
    ]
    post, put = writes
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/atc/checkvariants")
    assert 'adtcore:type="CHKV/TYP"' in post["body"]
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/atc/checkvariants/zadt_chkv1")
    assert put["content_type"] == "application/vnd.sap.adt.chkvv4+xml"
    check = et.fromstring(put["body"].strip()).find(f".//{CHKVCHECK}check")
    assert check.find(f"{CHKO}checkObject").get(f"{ADTCORE}name") == "CI_SYSUBRC"
    values = json.loads(check.findtext(f"{CHKVCHECK}parameterValueXml"))
    parameters = {p["name"]: p for p in values["parameters"]}
    assert values["checkName"] == "CI_SYSUBRC"
    assert parameters["ReadDB"] == {"name": "ReadDB", "value": "true"}
    assert parameters["WriteDB"] == {"name": "WriteDB", "value": "false"}
    assert parameters["AnyStatement"] == {"name": "AnyStatement", "valueList": ["MODIFY"]}
    assert activations == [[("ZADT_CHKV1", "/sap/bc/adt/atc/checkvariants/zadt_chkv1")]]


def test_save_refuses_unknown_parameters(fake_sap):
    fake_sap(
        checkvariant,
        FakeResponse(200, fixture("atc_check_sysubrc.xml")),
        FakeResponse(200, fixture("atc_check_defaults_sysubrc.json")),
    )
    with pytest.raises(ValueError, match="CI_SYSUBRC has no parameter Nonsense; its parameters: ReadDB, WriteDB"):
        checkvariant.save_check_variant(
            PARAMS, "ZADT_CHKV1", "$TMP", "x", "DEVELOPER", [{"name": "CI_SYSUBRC", "parameters": {"Nonsense": 1}}]
        )


def test_range_parameters_take_short_forms():
    defaults = [{"name": "GlobalTypes", "valueRangeList": []}]
    values = json.loads(checkvariant._parameter_values(
        "CI_ABAP_NAMING", defaults, {"GlobalTypes": [{"sign": "I", "option": "CP", "low": "TY_*"}, "T_*"]}
    ))
    assert values["parameters"][0]["valueRangeList"] == [
        {"sign": "include", "option": "containsPattern", "low": "TY_*", "high": ""},
        {"sign": "include", "option": "equals", "low": "T_*", "high": ""},
    ]
