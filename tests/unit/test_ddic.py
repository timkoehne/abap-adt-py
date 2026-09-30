import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import activate, create, ddic, lock
from helpers import PARAMS, FakeResponse, fixture

ADTCORE = "{http://www.sap.com/adt/core}"
DOMA = "{http://www.sap.com/dictionary/domain}"
DTEL = "{http://www.sap.com/adt/dictionary/dataelements}"
NO_INACTIVE = "<ioc:inactiveObjects xmlns:ioc='http://www.sap.com/abapxml/inactiveCtsObjects'/>"


def parse(body: str) -> et.Element:
    return et.fromstring(body.strip())


def fake_activation(fake_sap):
    return fake_sap(
        activate,
        FakeResponse(200, fixture("activation_success.xml")),
        FakeResponse(200, NO_INACTIVE),
    )


def fake_save(fake_sap, *create_responses):
    """The requests of _put_locked: lock, PUT, unlock."""
    lock_calls = fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    create_calls = fake_sap(create, *create_responses)
    return create_calls, lock_calls


def test_create_domain_with_fixed_values(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    activate_calls = fake_activation(fake_sap)
    assert ddic.create_domain(
        PARAMS,
        "zadtpy_status",
        "$TMP",
        "A & B",
        "DEVELOPER",
        "char",
        1,
        transport="A4HK900001",
        lowercase=True,
        conversion_exit="alpha",
        value_table="t001",
        fixed_values=[{"low": "N", "text": "New & open"}, {"low": "1", "high": "9", "text": "Digits"}],
    )

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/ddic/domains"
    assert call["params"] == {"corrNr": "A4HK900001"}
    assert call["content_type"] == "application/vnd.sap.adt.domains.v2+xml"
    root = parse(call["body"])
    assert root.get(f"{ADTCORE}name") == "ZADTPY_STATUS"
    assert root.get(f"{ADTCORE}description") == "A & B"
    content = root.find(f"{DOMA}content")
    assert content.findtext(f"{DOMA}typeInformation/{DOMA}datatype") == "CHAR"
    assert content.findtext(f"{DOMA}typeInformation/{DOMA}length") == "000001"
    # 0 lets SAP calculate the output length
    assert content.findtext(f"{DOMA}outputInformation/{DOMA}length") == "000000"
    assert content.findtext(f"{DOMA}outputInformation/{DOMA}lowercase") == "true"
    assert content.findtext(f"{DOMA}outputInformation/{DOMA}conversionExit") == "ALPHA"
    value_table = content.find(f"{DOMA}valueInformation/{DOMA}valueTableRef")
    assert value_table.get(f"{ADTCORE}name") == "T001"
    values = [
        [value.findtext(f"{DOMA}{tag}") for tag in ("position", "low", "high", "text")]
        for value in content.iter(f"{DOMA}fixValue")
    ]
    assert values == [["0001", "N", "", "New & open"], ["0002", "1", "9", "Digits"]]
    assert 'adtcore:uri="/sap/bc/adt/ddic/domains/zadtpy_status"' in activate_calls[0]["body"]


def test_get_domain(fake_sap):
    calls = fake_sap(ddic, FakeResponse(200, fixture("domain.xml")))
    assert ddic.get_domain(PARAMS, "ZADTPY_STATUS") == {
        "name": "ZADTPY_STATUS",
        "description": "Order status v2",
        "package": "$TMP",
        "data_type": "CHAR",
        "length": 1,
        "decimals": 0,
        "output_length": 1,
        "conversion_exit": "",
        "sign": False,
        "lowercase": False,
        "value_table": "",
        "fixed_values": [
            {"low": "N", "high": "", "text": "New"},
            {"low": "X", "high": "", "text": "Cancelled"},
        ],
    }
    assert calls[0]["uri"] == "/sap/bc/adt/ddic/domains/zadtpy_status"
    assert calls[0]["accept"] == "application/vnd.sap.adt.domains.v2+xml"


def test_get_domain_value_table(fake_sap):
    fake_sap(ddic, FakeResponse(200, fixture("domain_value_table.xml")))
    domain = ddic.get_domain(PARAMS, "ZADTPY_D2", version="active")
    assert domain["value_table"] == "T001"
    assert domain["conversion_exit"] == "ALPHA"
    assert domain["lowercase"] is True


def test_update_domain_keeps_what_is_not_changed(fake_sap):
    fake_sap(ddic, FakeResponse(200, fixture("domain.xml")))
    create_calls, lock_calls = fake_save(fake_sap, FakeResponse(200))
    fake_activation(fake_sap)

    ddic.update_domain(
        PARAMS, "ZADTPY_STATUS", "DEVELOPER", fixed_values=[{"low": "A", "text": "All"}]
    )

    [put] = create_calls
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/ddic/domains/zadtpy_status")
    root = parse(put["body"])
    assert root.get(f"{ADTCORE}description") == "Order status v2"
    content = root.find(f"{DOMA}content")
    assert content.findtext(f"{DOMA}outputInformation/{DOMA}length") == "000001"
    assert [v.findtext(f"{DOMA}low") for v in content.iter(f"{DOMA}fixValue")] == ["A"]
    assert [c["params"]["_action"] for c in lock_calls] == ["LOCK", "UNLOCK"]


def test_update_domain_type_recalculates_the_output_length(fake_sap):
    fake_sap(ddic, FakeResponse(200, fixture("domain.xml")))
    create_calls, _ = fake_save(fake_sap, FakeResponse(200))

    ddic.update_domain(PARAMS, "ZADTPY_STATUS", "DEVELOPER", length=4, activate=False)

    content = parse(create_calls[0]["body"]).find(f"{DOMA}content")
    assert content.findtext(f"{DOMA}typeInformation/{DOMA}length") == "000004"
    assert content.findtext(f"{DOMA}outputInformation/{DOMA}length") == "000000"
    # the fixed values stay
    assert len(list(content.iter(f"{DOMA}fixValue"))) == 2


def test_create_data_element_saves_the_type_after_creating(fake_sap):
    # creating ignores the type, so the definition is saved under a lock afterwards
    create_calls, _ = fake_save(fake_sap, FakeResponse(201), FakeResponse(200))
    activate_calls = fake_activation(fake_sap)

    ddic.create_data_element(
        PARAMS,
        "zadtpy_status",
        "$TMP",
        "Order status",
        "DEVELOPER",
        domain="zadtpy_status",
        labels={"short": "Status", "long": "Order status"},
        label_lengths={"short": 6},
        parameter_id="zst",
    )

    post, put = create_calls
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/ddic/dataelements")
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/ddic/dataelements/zadtpy_status")
    assert put["content_type"] == "application/vnd.sap.adt.dataelements.v2+xml"
    content = parse(put["body"]).find(f"{DTEL}dataElement")
    assert content.findtext(f"{DTEL}typeKind") == "domain"
    assert content.findtext(f"{DTEL}typeName") == "ZADTPY_STATUS"
    assert content.findtext(f"{DTEL}shortFieldLabel") == "Status"
    assert content.findtext(f"{DTEL}shortFieldLength") == "06"
    assert content.findtext(f"{DTEL}longFieldLabel") == "Order status"
    assert content.findtext(f"{DTEL}longFieldLength") == "40"
    assert content.findtext(f"{DTEL}mediumFieldLabel") == ""
    assert content.findtext(f"{DTEL}setGetParameter") == "ZST"
    assert 'adtcore:name="ZADTPY_STATUS"' in activate_calls[0]["body"]


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"data_type": "dec", "length": 7, "decimals": 2}, ["predefinedAbapType", "", "DEC", "000007", "000002"]),
        ({"reference_to": "zcl_foo"}, ["refToClifType", "ZCL_FOO", "", "000000", "000000"]),
        ({"reference_to": "scarr", "reference_kind": "dictionary"}, ["refToDictionaryType", "SCARR", "", "000000", "000000"]),
        ({"reference_to": "string", "reference_kind": "built_in"}, ["refToPredefinedAbapType", "", "STRING", "000000", "000000"]),
    ],
)
def test_create_data_element_types(fake_sap, kwargs, expected):
    create_calls, _ = fake_save(fake_sap, FakeResponse(201), FakeResponse(200))
    ddic.create_data_element(PARAMS, "ZADTPY_E", "$TMP", "desc", "DEVELOPER", activate=False, **kwargs)

    content = parse(create_calls[1]["body"]).find(f"{DTEL}dataElement")
    tags = ("typeKind", "typeName", "dataType", "dataTypeLength", "dataTypeDecimals")
    assert [content.findtext(f"{DTEL}{tag}") for tag in tags] == expected


@pytest.mark.parametrize("kwargs", [{}, {"domain": "A", "data_type": "CHAR"}])
def test_create_data_element_needs_exactly_one_type(kwargs):
    with pytest.raises(ValueError):
        ddic.create_data_element(PARAMS, "ZADTPY_E", "$TMP", "desc", "DEVELOPER", **kwargs)


def test_create_data_element_rejects_too_long_labels(fake_sap):
    fake_save(fake_sap, FakeResponse(201))
    with pytest.raises(ValueError, match="short label"):
        ddic.create_data_element(
            PARAMS, "ZADTPY_E", "$TMP", "desc", "DEVELOPER", domain="X", labels={"short": "x" * 11}
        )


def test_get_data_element(fake_sap):
    fake_sap(ddic, FakeResponse(200, fixture("data_element.xml")))
    assert ddic.get_data_element(PARAMS, "ZADTPY_STATUS") == {
        "name": "ZADTPY_STATUS",
        "description": "Order status",
        "package": "$TMP",
        "type_kind": "domain",
        "type_name": "ZADTPY_STATUS",
        "data_type": "CHAR",
        "length": 1,
        "decimals": 0,
        "labels": {"short": "Stat.", "medium": "Order status", "long": "Order status", "heading": "St"},
        "label_lengths": {"short": 10, "medium": 20, "long": 40, "heading": 55},
        "search_help": "",
        "search_help_parameter": "",
        "parameter_id": "BUK",
        "default_component_name": "",
        "change_document": False,
    }


def test_update_data_element_changes_only_the_given_labels(fake_sap):
    fake_sap(ddic, FakeResponse(200, fixture("data_element.xml")))
    create_calls, _ = fake_save(fake_sap, FakeResponse(200))

    ddic.update_data_element(
        PARAMS, "ZADTPY_STATUS", "DEVELOPER", labels={"heading": "Status"}, activate=False
    )

    content = parse(create_calls[0]["body"]).find(f"{DTEL}dataElement")
    assert content.findtext(f"{DTEL}headingFieldLabel") == "Status"
    assert content.findtext(f"{DTEL}shortFieldLabel") == "Stat."
    assert content.findtext(f"{DTEL}typeName") == "ZADTPY_STATUS"
    assert content.findtext(f"{DTEL}setGetParameter") == "BUK"


def test_update_data_element_type(fake_sap):
    fake_sap(ddic, FakeResponse(200, fixture("data_element.xml")))
    create_calls, _ = fake_save(fake_sap, FakeResponse(200))

    ddic.update_data_element(
        PARAMS, "ZADTPY_STATUS", "DEVELOPER", data_type="NUMC", length=4, activate=False
    )

    content = parse(create_calls[0]["body"]).find(f"{DTEL}dataElement")
    assert content.findtext(f"{DTEL}typeKind") == "predefinedAbapType"
    assert content.findtext(f"{DTEL}typeName") == ""
    assert content.findtext(f"{DTEL}dataType") == "NUMC"
    assert content.findtext(f"{DTEL}dataTypeLength") == "000004"
