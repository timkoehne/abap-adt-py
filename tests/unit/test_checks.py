import base64
import re

import pytest

from abap_adt_py.api import objectstructure, syntax, unittest
from helpers import PARAMS, FakeResponse, fixture

CLASS = "/sap/bc/adt/oo/classes/zcl_adtpy_fixture"


def check_message(uri: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
    <chkrun:checkRunReports xmlns:chkrun="http://www.sap.com/adt/checkrun">
        <chkrun:checkReport><chkrun:checkMessageList>
            <chkrun:checkMessage chkrun:uri="{uri}" chkrun:type="W" chkrun:shortText="text"/>
        </chkrun:checkMessageList></chkrun:checkReport>
    </chkrun:checkRunReports>"""


def test_syntax_check_error(fake_sap):
    calls = fake_sap(syntax, FakeResponse(200, fixture("syntaxcheck_error.xml")))
    source = "CLASS zcl_adtpy_fixture DEFINITION. ENDCLASS."
    messages = syntax.syntax_check(PARAMS, CLASS, CLASS + "/source/main", source)

    # the position comes as #start=9,12;end=9,25
    assert messages == [
        {
            "uri": CLASS,
            "type": "E",
            "short_text": 'Field "UNDEFINED_VAR" is unknown.',
            "line": 9,
            "offset": 12,
        }
    ]
    content = re.search(r"<chkrun:content>(.*)</chkrun:content>", calls[0]["body"])
    assert base64.b64decode(content.group(1)).decode() == source


def test_syntax_check_clean(fake_sap):
    fake_sap(syntax, FakeResponse(200, fixture("syntaxcheck_clean.xml")))
    assert syntax.syntax_check(PARAMS, CLASS, CLASS + "/source/main", "x") == []


@pytest.mark.parametrize(
    "uri, line, offset",
    [
        (CLASS + "/source/main#start=1,6", 1, 6),
        (CLASS + "/source/main#start=3,0;end=3,4", 3, 0),
    ],
)
def test_syntax_check_positions(fake_sap, uri, line, offset):
    fake_sap(syntax, FakeResponse(200, check_message(uri)))
    [message] = syntax.syntax_check(PARAMS, CLASS, CLASS + "/source/main", "x")
    assert message["uri"] == CLASS
    assert (message["line"], message["offset"]) == (line, offset)


def test_syntax_check_without_position(fake_sap):
    fake_sap(syntax, FakeResponse(200, check_message(CLASS)))
    [message] = syntax.syntax_check(PARAMS, CLASS, CLASS + "/source/main", "x")
    assert "line" not in message and "offset" not in message


def test_syntax_check_failure_raises(fake_sap):
    fake_sap(syntax, FakeResponse(500, "dump"))
    with pytest.raises(Exception, match="500"):
        syntax.syntax_check(PARAMS, CLASS, CLASS + "/source/main", "x")


def test_run_unit_test_reports_failures(fake_sap):
    calls = fake_sap(unittest, FakeResponse(200, fixture("unittest_failure.xml")))
    [alert] = unittest.run_unit_test(PARAMS, CLASS)

    assert alert["title"] == "Critical Assertion Error: 'expected failure'"
    assert alert["kind"] == "failedAssertion"
    assert alert["severity"] == "critical"
    assert alert["details"][0] == "Different values\nExpected [5] Actual [3]"
    assert alert["test_class"] == "LTC"
    assert alert["test_method"] == "FAILS"
    assert alert["stack"] == [
        {
            "uri": CLASS + "/includes/testclasses#start=11,0;end=11,0",
            "type": "CLAS/OCN/testclasses",
            "name": "ZCL_ADTPY_FIXTURE",
            "description": "Include: <ZCL_ADTPY_FIXTURE=============CCAU> Line: <11> (FAILS)",
        }
    ]
    assert f'adtcore:uri="{CLASS}"' in calls[0]["body"]


def test_run_unit_test_alert_outside_a_method(fake_sap):
    result = """<aunit:runResult xmlns:aunit="http://www.sap.com/adt/aunit"
        xmlns:adtcore="http://www.sap.com/adt/core">
      <program adtcore:name="ZCL_X"><testClasses>
        <testClass adtcore:name="LTC"><alerts>
          <alert kind="warning" severity="tolerable"><title>No test methods</title></alert>
        </alerts></testClass>
      </testClasses></program>
    </aunit:runResult>"""
    fake_sap(unittest, FakeResponse(200, result))
    [alert] = unittest.run_unit_test(PARAMS, CLASS)

    assert alert["title"] == "No test methods"
    assert (alert["test_class"], alert["test_method"]) == ("LTC", "")
    assert alert["details"] == [] and alert["stack"] == []


def test_run_unit_test_all_passing(fake_sap):
    passing = fixture("unittest_failure.xml")
    passing = passing[: passing.index("<alerts>")] + passing[passing.index("</alerts>") + len("</alerts>") :]
    fake_sap(unittest, FakeResponse(200, passing))
    assert unittest.run_unit_test(PARAMS, CLASS) == []


def test_run_unit_test_flags(fake_sap):
    calls = fake_sap(unittest, FakeResponse(200, fixture("unittest_failure.xml")))
    flags = unittest.UnittestFlags(dangerous=True, long=True)
    unittest.run_unit_test(PARAMS, CLASS, flags)

    body = calls[0]["body"]
    assert 'harmless="true" dangerous="true" critical="false"' in body
    assert 'short="true" medium="false" long="true"' in body


def test_run_unit_test_failure_raises(fake_sap):
    fake_sap(unittest, FakeResponse(404, "not found"))
    with pytest.raises(Exception, match="404"):
        unittest.run_unit_test(PARAMS, CLASS)


def test_object_structure(fake_sap):
    calls = fake_sap(
        objectstructure, FakeResponse(200, fixture("objectstructure_class.xml"))
    )
    structure = objectstructure.object_structure(PARAMS, CLASS)

    assert calls[0]["uri"] == CLASS + "/objectstructure"
    assert structure["name"] == "ZCL_ADTPY_FIXTURE"
    assert structure["type"] == "CLAS/OC"
    names = [component["name"] for component in structure["components"]]
    assert {"ADD", "LTC", "PASSES", "FAILS"} <= set(names)
