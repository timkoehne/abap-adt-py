import re

import pytest

from abap_adt_py.api import atc
from helpers import PARAMS, FakeResponse, fixture

CLASS = "/sap/bc/adt/oo/classes/zcl_adtpy_atc"
WORKLIST = FakeResponse(200, "CAB27D7F2DFC1FE1AE83AEC36B17A069")


def variants(name="ZABAP_CLOUD_DEVELOPMENT"):
    return FakeResponse(200, fixture("atc_variants.xml").replace("ZABAP_CLOUD_DEVELOPMENT", name))


def test_default_check_variant(fake_sap):
    calls = fake_sap(atc, FakeResponse(200, fixture("atc_customizing.xml")))
    assert atc.default_check_variant(PARAMS) == "ZABAP_CLOUD_DEVELOPMENT"
    assert calls[0]["uri"] == "/sap/bc/adt/atc/customizing"


def test_list_check_variants(fake_sap):
    calls = fake_sap(atc, FakeResponse(200, fixture("atc_variants.xml")))
    assert atc.list_check_variants(PARAMS, "Z*", 5) == [
        {
            "name": "ZABAP_CLOUD_DEVELOPMENT",
            "description": "Default ATC variant for ABAP Cloud Development",
        }
    ]
    assert calls[0]["params"] == {"name": "Z*", "maxItemCount": 5}


def test_run_atc(fake_sap):
    calls = fake_sap(
        atc,
        variants(),
        WORKLIST,
        FakeResponse(200, fixture("atc_run.xml")),
        FakeResponse(200, fixture("atc_worklist.xml")),
    )
    result = atc.run_atc(PARAMS, CLASS, "zabap_cloud_development", max_findings=50)

    assert [(c["method"], c["uri"]) for c in calls] == [
        ("GET", "/sap/bc/adt/atc/variants"),
        ("POST", "/sap/bc/adt/atc/worklists"),
        ("POST", "/sap/bc/adt/atc/runs"),
        ("GET", "/sap/bc/adt/atc/worklists/CAB27D7F2DFC1FE1AE83AEC36B17A069"),
    ]
    assert calls[1]["params"] == {"checkVariant": "ZABAP_CLOUD_DEVELOPMENT"}
    assert calls[2]["params"] == {"worklistId": "CAB27D7F2DFC1FE1AE83AEC36B17A069"}
    assert f'adtcore:uri="{CLASS}"' in calls[2]["body"]
    assert 'maximumVerdicts="50"' in calls[2]["body"]

    assert result["check_variant"] == "ZABAP_CLOUD_DEVELOPMENT"
    assert {"type": "TOOL_FAILURE", "description": "Check not executable, due to missing prerequisites"} in result["infos"]
    assert sorted(f["priority"] for f in result["findings"]) == [1, 2, 2, 3]

    [released_api] = [f for f in result["findings"] if f["priority"] == 1]
    assert released_api["object_name"] == "ZCL_ADTPY_ATC"
    assert released_api["object_type"] == "CLAS"
    assert released_api["package"] == "$ZADTPY_ATC"
    assert released_api["check_title"] == "Usage of Released APIs"
    assert released_api["message_id"] == "NOT_TO_REL"
    assert released_api["message"] == "Usage of API that will not be released."
    assert released_api["uri"] == CLASS + "/source/main"
    assert (released_api["line"], released_api["column"]) == (9, 0)
    assert released_api["documentation_uri"].startswith("/sap/bc/adt/documentation/atc/documents/")
    assert released_api["tags"]["REF_OBJ_NAME"] == "TADIR"


def test_run_atc_uses_default_variant(fake_sap):
    calls = fake_sap(
        atc,
        FakeResponse(200, fixture("atc_customizing.xml")),
        WORKLIST,
        FakeResponse(200, fixture("atc_run.xml")),
        FakeResponse(200, fixture("atc_worklist.xml")),
    )
    result = atc.run_atc(PARAMS, [CLASS, "/sap/bc/adt/packages/zpkg"])

    assert calls[0]["uri"] == "/sap/bc/adt/atc/customizing"
    assert calls[1]["params"] == {"checkVariant": "ZABAP_CLOUD_DEVELOPMENT"}
    assert calls[2]["body"].count("<adtcore:objectReference ") == 2
    assert result["check_variant"] == "ZABAP_CLOUD_DEVELOPMENT"


def test_run_atc_rejects_unknown_variant(fake_sap):
    # SAP would run an unknown variant without checks and report no findings
    fake_sap(atc, FakeResponse(200, fixture("atc_variants.xml").replace("<nameditem:namedItem>", "<ignored>").replace("</nameditem:namedItem>", "</ignored>")))
    with pytest.raises(Exception, match="ZDOES_NOT_EXIST does not exist"):
        atc.run_atc(PARAMS, CLASS, "ZDOES_NOT_EXIST")


def test_run_atc_variant_must_match_exactly(fake_sap):
    fake_sap(atc, variants("ZABAP_CLOUD_DEVELOPMENT_2"))
    with pytest.raises(Exception, match="does not exist"):
        atc.run_atc(PARAMS, CLASS, "ZABAP_CLOUD_DEVELOPMENT")


def test_finding_without_position(fake_sap):
    worklist = fixture("atc_worklist.xml").replace("/source/main#start=9,0", "", 1)
    fake_sap(
        atc,
        variants(),
        WORKLIST,
        FakeResponse(200, fixture("atc_run.xml")),
        FakeResponse(200, worklist),
    )
    findings = atc.run_atc(PARAMS, CLASS, "ZABAP_CLOUD_DEVELOPMENT")["findings"]

    assert findings[0]["uri"] == CLASS
    assert (findings[0]["line"], findings[0]["column"]) == (None, None)


def test_run_atc_failure_raises(fake_sap):
    fake_sap(atc, variants(), WORKLIST, FakeResponse(500, "dump"))
    with pytest.raises(Exception, match="500 - Failed to run ATC"):
        atc.run_atc(PARAMS, CLASS, "ZABAP_CLOUD_DEVELOPMENT")


def test_atc_documentation_as_text(fake_sap):
    calls = fake_sap(atc, FakeResponse(200, fixture("atc_documentation.html")))
    text = atc.atc_documentation(PARAMS, "/sap/bc/adt/documentation/atc/documents/itemid/X/index/3")

    assert calls[0]["accept"] == "application/vnd.sap.adt.docu.v1+html"
    assert re.search(r"</?[a-zA-Z][a-zA-Z0-9]*[\s>/]", text) is None  # no HTML tags left
    assert text.startswith("Appl. Comp. Check / Check Class / Message Code")
    assert "- Referenced Object: TADIR (TABL)" in text.splitlines()
    assert "\n\n\n" not in text


def test_atc_documentation_as_html(fake_sap):
    fake_sap(atc, FakeResponse(200, fixture("atc_documentation.html")))
    html = atc.atc_documentation(PARAMS, "/doc", as_html=True)
    assert html == fixture("atc_documentation.html")
