import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import activate, create, enhancements, lock
from helpers import PARAMS, FakeResponse, fixture

ADTCORE = "{http://www.sap.com/adt/core}"
ENHS = "{http://www.sap.com/adt/enhancements/enhs}"
ENHO = "{http://www.sap.com/adt/enhancements/enho}"
ENHCORE = "{http://www.sap.com/abapsource/enhancementscore}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
NO_INACTIVE = "<ioc:inactiveObjects xmlns:ioc='http://www.sap.com/abapxml/inactiveCtsObjects'/>"


def parse(body: str) -> et.Element:
    return et.fromstring(body.strip())


def fake_activation(fake_sap):
    return fake_sap(
        activate,
        FakeResponse(200, fixture("activation_success.xml")),
        FakeResponse(200, NO_INACTIVE),
    )


def test_create_enhancement_spot(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    activate_calls = fake_activation(fake_sap)

    enhancements.create_enhancement_spot(
        PARAMS, "zes_adtpy", "$TMP", "spot", "DEVELOPER",
        [
            {
                "name": "zbadi_adtpy",
                "interface": "zif_adtpy_badi",
                "filters": [{"name": "plant", "type": "C", "data_element": "werks_d"}],
            },
            {"name": "ZBADI_SINGLE", "interface": "ZIF_X", "single_use": True, "fallback_class": "zcl_fallback"},
        ],
    )

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/enhancements/enhsxsb"
    assert call["content_type"] == "application/vnd.sap.adt.enh.enhs.v2+xml"
    root = parse(call["body"])
    assert root.get(f"{ADTCORE}type") == "ENHS/XSB"
    assert root.find(f"{ENHS}contentCommon").get(f"{ENHS}toolType") == "BADI_DEF"
    multiple, single = root.iter(f"{ENHS}badiDefinition")
    assert multiple.get(f"{ENHS}name") == "ZBADI_ADTPY"
    assert multiple.get(f"{ENHS}singleUse") == "false"
    assert multiple.get(f"{ENHS}useFallbackClass") == "false"
    assert multiple.find(f"{ENHS}interface").get(f"{ADTCORE}name") == "ZIF_ADTPY_BADI"
    [plant] = multiple.iter(f"{ENHS}filter")
    assert (plant.get(f"{ENHS}filterName"), plant.get(f"{ENHS}filterType")) == ("PLANT", "C")
    check = plant.find(f"{ENHS}filterCheck")
    assert check.get(f"{XSI}type") == "enhcore:DictionaryCheck"
    assert check.find(f"{ENHCORE}checkObject").get(f"{ADTCORE}name") == "WERKS_D"
    assert single.get(f"{ENHS}singleUse") == "true"
    assert single.get(f"{ENHS}useFallbackClass") == "true"
    assert single.find(f"{ENHS}defaultClass").get(f"{ADTCORE}name") == "ZCL_FALLBACK"
    assert single.find(f"{ENHS}filters") is None
    assert 'adtcore:uri="/sap/bc/adt/enhancements/enhsxsb/zes_adtpy"' in activate_calls[0]["body"]


def test_spot_badi_needs_an_interface(fake_sap):
    with pytest.raises(ValueError, match="needs an interface"):
        enhancements.create_enhancement_spot(PARAMS, "ZES", "$TMP", "d", "DEVELOPER", [{"name": "ZBADI"}])


def test_get_enhancement_spot(fake_sap):
    calls = fake_sap(enhancements, FakeResponse(200, fixture("enhancement_spot.xml")))
    assert enhancements.get_enhancement_spot(PARAMS, "ZES_ADTPY") == {
        "name": "ZES_ADTPY",
        "description": "adt-py spot",
        "package": "$TMP",
        "badis": [
            {
                "name": "ZBADI_ADTPY",
                "description": "adt-py badi",
                "interface": "ZIF_ADTPY_BADI",
                "single_use": False,
                "fallback_class": "",
                "filters": [
                    {
                        "name": "PLANT",
                        "type": "C",
                        "description": "Plant",
                        "data_element": "WERKS_D",
                        "constant_values_only": False,
                    }
                ],
            }
        ],
    }
    assert calls[0]["uri"] == "/sap/bc/adt/enhancements/enhsxsb/zes_adtpy"


def create_implementation(fake_sap, filters):
    fake_sap(enhancements, FakeResponse(200, fixture("enhancement_spot.xml")))
    calls = fake_sap(create, FakeResponse(201))
    enhancements.create_enhancement_implementation(
        PARAMS, "zei_adtpy", "$TMP", "impl", "DEVELOPER", "zes_adtpy",
        [{"name": "zimpl", "badi": "zbadi_adtpy", "implementing_class": "zcl_impl", "filters": filters}],
        activate=False,
    )
    return parse(calls[0]["body"])


def tokens(element):
    """The filter tokens as nested lists, e.g. ["Or", ["Filter", ...], ...]."""
    result = []
    for token in element.findall(f"{ENHO}filterToken"):
        kind = token.get(f"{XSI}type").replace("enho:", "")
        if kind in ("And", "Or"):
            result.append([kind] + tokens(token))
        elif kind == "Filter":
            result.append(f"{token.get(f'{ENHO}filterName')}{token.get(f'{ENHO}comparator')}{token.get(f'{ENHO}value')}")
        else:
            result.append(
                f"{token.get(f'{ENHO}valueLeft')}{token.get(f'{ENHO}comparatorLeft')}"
                f"{token.get(f'{ENHO}filterName')}{token.get(f'{ENHO}comparatorRight')}{token.get(f'{ENHO}valueRight')}"
            )
    return result


def test_create_enhancement_implementation(fake_sap):
    root = create_implementation(fake_sap, [{"filter": "plant", "value": "1000"}])

    assert root.get(f"{ADTCORE}type") == "ENHO/XHB"
    # SAP needs the spot as a used object to create the implementation
    usage = root.find(f"{ENHO}contentCommon/{ENHO}usages/{ENHCORE}referencedObject")
    assert usage.get(f"{ENHCORE}element_usage") == "EXTO"
    assert usage.find(f"{ENHCORE}objectReference").get(f"{ADTCORE}name") == "ZES_ADTPY"
    [implementation] = root.iter(f"{ENHO}badiImplementation")
    assert implementation.get(f"{ENHO}name") == "ZIMPL"
    assert implementation.get(f"{ENHO}active") == "true"
    assert implementation.find(f"{ENHO}badiDefinition").get(f"{ADTCORE}uri") == (
        "/sap/bc/adt/enhancements/enhsxsb/zes_adtpy#type=enhs%2fxb;name=zbadi_adtpy"
    )
    assert implementation.find(f"{ENHO}implementingClass").get(f"{ADTCORE}name") == "ZCL_IMPL"
    tree = implementation.find(f"{ENHO}filterTree")
    assert tokens(tree) == ["PLANT=1000"]
    # the filter's type and check are copied from the BAdI definition
    [prop] = tree.findall(f"{ENHO}filterProperty")
    assert (prop.get(f"{ENHO}filterName"), prop.get(f"{ENHO}filterType")) == ("PLANT", "C")
    assert prop.find(f"{ENHO}filterCheck/{ENHCORE}checkObject").get(f"{ADTCORE}name") == "WERKS_D"


@pytest.mark.parametrize(
    "filters, expected",
    [
        ([{"filter": "PLANT", "value": "1"}, {"filter": "PLANT", "comparator": "<>", "value": "2"}],
         [["And", "PLANT=1", "PLANT<>2"]]),
        ([[{"filter": "PLANT", "value": "1"}], [{"filter": "PLANT", "low": "3", "high": "9"}]],
         [["Or", "PLANT=1", "3<=PLANT<=9"]]),
        ([[{"filter": "PLANT", "value": "1"}, [{"filter": "PLANT", "value": "2"}, {"filter": "PLANT", "value": "3"}]]],
         [["And", "PLANT=1", ["Or", "PLANT=2", "PLANT=3"]]]),
    ],
)
def test_filter_conditions(fake_sap, filters, expected):
    root = create_implementation(fake_sap, filters)
    assert tokens(root.find(f".//{ENHO}filterTree")) == expected


def test_unknown_filter_fails(fake_sap):
    fake_sap(enhancements, FakeResponse(200, fixture("enhancement_spot.xml")))
    with pytest.raises(ValueError, match="has no filter REGION"):
        enhancements.create_enhancement_implementation(
            PARAMS, "ZEI", "$TMP", "d", "DEVELOPER", "ZES_ADTPY",
            [{"name": "ZI", "badi": "ZBADI_ADTPY", "implementing_class": "ZCL", "filters": [{"filter": "region", "value": "1"}]}],
        )


def test_unknown_badi_fails(fake_sap):
    fake_sap(enhancements, FakeResponse(200, fixture("enhancement_spot.xml")))
    with pytest.raises(ValueError, match="has no BAdI ZBADI_OTHER"):
        enhancements.create_enhancement_implementation(
            PARAMS, "ZEI", "$TMP", "d", "DEVELOPER", "ZES_ADTPY",
            [{"name": "ZI", "badi": "ZBADI_OTHER", "implementing_class": "ZCL"}],
        )


def test_get_enhancement_implementation(fake_sap):
    fake_sap(enhancements, FakeResponse(200, fixture("enhancement_implementation.xml")))
    assert enhancements.get_enhancement_implementation(PARAMS, "ZEI_ADTPY") == {
        "name": "ZEI_ADTPY",
        "description": "adt-py implementation",
        "package": "$TMP",
        "spot": "ZES_ADTPY",
        "implementations": [
            {
                "name": "ZBADI_ADTPY_IMPL",
                "badi": "ZBADI_ADTPY",
                "implementing_class": "ZCL_ADTPY_BADI_IMPL",
                "description": "",
                "active": True,
                "filters": [
                    [{"filter": "PLANT", "comparator": "=", "value": "2000"}],
                    [{"filter": "PLANT", "low": "3000", "high": "3999"}],
                ],
            }
        ],
    }


def test_update_enhancement_implementation_keeps_the_implementations(fake_sap):
    fake_sap(
        enhancements,
        FakeResponse(200, fixture("enhancement_implementation.xml")),
        FakeResponse(200, fixture("enhancement_spot.xml")),
    )
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    calls = fake_sap(create, FakeResponse(200))

    enhancements.update_enhancement_implementation(
        PARAMS, "ZEI_ADTPY", "DEVELOPER", description="new", activate=False
    )

    put = calls[0]
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/enhancements/enhoxhb/zei_adtpy")
    root = parse(put["body"])
    assert root.get(f"{ADTCORE}description") == "new"
    assert tokens(root.find(f".//{ENHO}filterTree")) == [["Or", "PLANT=2000", "3000<=PLANT<=3999"]]
