import pytest

from abap_adt_py.api import navigation
from helpers import PARAMS, FakeResponse, fixture

CLASS = "/sap/bc/adt/oo/classes/zcl_adtpy_nav"
PROGRAM = "/sap/bc/adt/programs/programs/z_adtpy_nav"
SOURCE = "REPORT z_adtpy_nav.\nDATA(calc) = NEW zcl_adtpy_nav( ).\nDATA(sum) = calc->add( a = 1 b = 2 )."

NAVIGATION_FAILURE = """<?xml version="1.0" encoding="utf-8"?>
<exc:exception xmlns:exc="http://www.sap.com/abapxml/types/communicationframework">
  <namespace id="com.sap.adt"/><type id="NavigationFailure"/>
  <message lang="EN">Incorrect cursor position or object is not included in navigation</message>
</exc:exception>"""


def test_find_definition(fake_sap):
    calls = fake_sap(navigation, FakeResponse(200, fixture("navigation_definition.xml")))
    target = navigation.find_definition(PARAMS, PROGRAM + "/source/main", SOURCE, 3, 18)

    assert target == {"uri": CLASS + "/source/main", "line": 3, "column": 12}
    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/navigation/target"
    assert call["params"] == {
        "uri": PROGRAM + "/source/main#start=3,18;end=3,18",
        "filter": "definition",
    }
    # the current, possibly unsaved source is sent along
    assert call["body"] == SOURCE


@pytest.mark.parametrize(
    "response",
    [FakeResponse(400, NAVIGATION_FAILURE), FakeResponse(200, "")],
    ids=["keyword", "blank"],
)
def test_find_definition_without_target(fake_sap, response):
    fake_sap(navigation, response)
    assert navigation.find_definition(PARAMS, PROGRAM + "/source/main", SOURCE, 4, 0) is None


def test_find_definition_failure_raises(fake_sap):
    fake_sap(navigation, FakeResponse(500, "dump"))
    with pytest.raises(Exception, match="500"):
        navigation.find_definition(PARAMS, PROGRAM + "/source/main", SOURCE, 3, 18)


def test_where_used_method(fake_sap):
    calls = fake_sap(
        navigation,
        FakeResponse(200, fixture("usagereferences_method.xml")),
        FakeResponse(200, fixture("usagesnippets_method.xml")),
    )
    usages = navigation.where_used(PARAMS, CLASS + "/source/main", 3, 12)

    assert calls[0]["uri"] == "/sap/bc/adt/repository/informationsystem/usageReferences"
    assert calls[0]["params"] == {"uri": CLASS + "/source/main#start=3,12"}
    assert calls[1]["uri"] == "/sap/bc/adt/repository/informationsystem/usageSnippets"
    # the snippets are requested for the objects the usage list found
    assert "ABAPFullName;Z_ADTPY_NAV;Z_ADTPY_NAV;\\TY:ZCL_ADTPY_NAV\\ME:ADD" in calls[1]["body"]

    assert usages == [
        {
            "object_name": "Z_ADTPY_NAV",
            "object_type": "PROG/P",
            "package": "$TMP",
            "object_uri": PROGRAM,
            "element": "",
            "location": PROGRAM + "/source/main#start=3,18;end=3,21",
            "line": 3,
            "column": 18,
            "code": "DATA(sum) = calc->add( a = 1 b = 2 ).",
            "usage": "Usage Kind: direct usage, read access",
        }
    ]


def test_where_used_class(fake_sap):
    calls = fake_sap(
        navigation,
        FakeResponse(200, fixture("usagereferences_class.xml")),
        FakeResponse(200, fixture("usagesnippets_class.xml")),
    )
    usages = navigation.where_used(PARAMS, CLASS)

    assert calls[0]["params"] == {"uri": CLASS}
    found = [(u["object_name"], u["element"], u["line"], u["column"]) for u in usages]
    assert found == [
        # usages inside the class itself, attributed to the class with the element they are in
        ("ZCL_ADTPY_NAV", "ADD", 1, 9),
        ("ZCL_ADTPY_NAV", "Public Section", 3, 12),
        ("Z_ADTPY_NAV", "", 2, 5),
        ("Z_ADTPY_NAV", "", 3, 12),
    ]
    assert all(u["object_type"] in ("CLAS/OC", "PROG/P") for u in usages)
    # packages only group the results and are not usages themselves
    assert "$TMP" not in [u["object_name"] for u in usages]


def test_where_used_without_usages(fake_sap):
    empty = """<usagereferences:usageReferenceResult numberOfResults="0"
        xmlns:usagereferences="http://www.sap.com/adt/ris/usageReferences">
        <usagereferences:referencedObjects/>
    </usagereferences:usageReferenceResult>"""
    calls = fake_sap(navigation, FakeResponse(200, empty))
    assert navigation.where_used(PARAMS, CLASS) == []
    assert len(calls) == 1  # no snippet request without usages


def test_where_used_object_without_snippets(fake_sap):
    fake_sap(
        navigation,
        FakeResponse(200, fixture("usagereferences_method.xml")),
        FakeResponse(200, fixture("usagesnippets_method.xml").replace("Z_ADTPY_NAV;Z_ADTPY_NAV", "OTHER;OTHER")),
    )
    [usage] = navigation.where_used(PARAMS, CLASS + "/source/main", 3, 12)
    assert usage["object_name"] == "Z_ADTPY_NAV"
    assert (usage["location"], usage["line"], usage["code"]) == ("", None, "")


def test_where_used_failure_raises(fake_sap):
    fake_sap(navigation, FakeResponse(404, "not found"))
    with pytest.raises(Exception, match="404"):
        navigation.where_used(PARAMS, CLASS)


def test_code_completion(fake_sap):
    calls = fake_sap(navigation, FakeResponse(200, fixture("codecompletion.xml")))
    source = SOURCE + "\nDATA(x) = calc->a"
    proposals = navigation.code_completion(PARAMS, PROGRAM + "/source/main", source, 4, 17)

    assert proposals == [{"identifier": "ADD", "kind": 3, "prefix_length": 1}]
    assert calls[0]["params"]["uri"] == PROGRAM + "/source/main#start=4,17"
    assert calls[0]["body"] == source


def test_code_completion_failure_raises(fake_sap):
    fake_sap(navigation, FakeResponse(500, "dump"))
    with pytest.raises(Exception, match="500"):
        navigation.code_completion(PARAMS, PROGRAM + "/source/main", SOURCE, 1, 0)
