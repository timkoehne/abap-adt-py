import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import create, lock
from abap_adt_py.exceptions import AdtError
from helpers import PARAMS, FakeResponse, fixture

ADTCORE = "{http://www.sap.com/adt/core}"
DOMA = "{http://www.sap.com/dictionary/domain}"
TTYP = "{http://www.sap.com/dictionary/tabletype}"
SRVB = "{http://www.sap.com/adt/ddic/ServiceBindings}"


def parse(body: str) -> et.Element:
    return et.fromstring(body.strip())


@pytest.mark.parametrize(
    "object_type, path",
    [
        ("TABL/DS", "/sap/bc/adt/ddic/structures"),
        ("SRVD/SRV", "/sap/bc/adt/ddic/srvd/sources"),
        ("BDEF/BDO", "/sap/bc/adt/bo/behaviordefinitions"),
    ],
)
def test_create_source_based_types(fake_sap, object_type, path):
    calls = fake_sap(create, FakeResponse(201))
    create.create(PARAMS, object_type, "ZADTPY_X", "$TMP", "desc", "DEVELOPER")

    assert calls[0]["uri"] == path
    root = parse(calls[0]["body"])
    assert root.get(f"{ADTCORE}type") == object_type
    assert root.get(f"{ADTCORE}name") == "ZADTPY_X"


def test_create_service_definition_is_a_definition():
    body = create._build_body("desc", "ZADTPY_SD", "$TMP", "DEVELOPER", "SRVD/SRV")
    assert parse(body).get("{http://www.sap.com/adt/ddic/srvdsources}srvdSourceType") == "S"


def test_create_domain(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    assert create.create_domain(
        PARAMS, "ZADTPY_D", "$TMP", "A & B", "DEVELOPER", "char", 10, transport="A4HK900001"
    )

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/ddic/domains"
    assert call["params"] == {"corrNr": "A4HK900001"}
    assert call["content_type"] == "application/vnd.sap.adt.domains.v2+xml"
    root = parse(call["body"])
    assert root.get(f"{ADTCORE}description") == "A & B"
    info = root.find(f"{DOMA}content/{DOMA}typeInformation")
    assert info.findtext(f"{DOMA}datatype") == "CHAR"
    assert info.findtext(f"{DOMA}length") == "000010"
    assert info.findtext(f"{DOMA}decimals") == "000000"


def test_create_table_type_saves_the_row_type_after_creating(fake_sap):
    # creating ignores the row type, so the definition is saved under a lock afterwards
    create_calls = fake_sap(create, FakeResponse(201), FakeResponse(200))
    lock_calls = fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))

    assert create.create_table_type(
        PARAMS, "ZADTPY_TT", "$TMP", "desc", "DEVELOPER", row_type="scarr"
    )

    post, put = create_calls
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/ddic/tabletypes")
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/ddic/tabletypes/zadtpy_tt")
    assert put["params"] == {"lockHandle": "AD111DBD5E2316FBF7AA949C8B2AEC2B5C27CD4E"}
    row = parse(put["body"]).find(f"{TTYP}rowType")
    assert row.findtext(f"{TTYP}typeKind") == "dictionaryType"
    assert row.findtext(f"{TTYP}typeName") == "SCARR"
    assert parse(put["body"]).get(f"{ADTCORE}description") == "desc"
    assert [c["params"]["_action"] for c in lock_calls] == ["LOCK", "UNLOCK"]


def test_create_table_type_of_built_in_type(fake_sap):
    create_calls = fake_sap(create, FakeResponse(201), FakeResponse(200))
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    create.create_table_type(
        PARAMS, "ZADTPY_TT", "$TMP", "desc", "DEVELOPER", data_type="char", length=20
    )

    row = parse(create_calls[1]["body"]).find(f"{TTYP}rowType")
    assert row.findtext(f"{TTYP}typeKind") == "predefinedAbapType"
    assert row.findtext(f"{TTYP}builtInType/{TTYP}dataType") == "CHAR"
    assert row.findtext(f"{TTYP}builtInType/{TTYP}length") == "000020"


def test_create_table_type_unlocks_when_saving_fails(fake_sap):
    fake_sap(create, FakeResponse(201), FakeResponse(400, "invalid row type"))
    lock_calls = fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))

    with pytest.raises(AdtError, match="Failed to save table type ZADTPY_TT"):
        create.create_table_type(
            PARAMS, "ZADTPY_TT", "$TMP", "desc", "DEVELOPER", row_type="NOPE"
        )
    assert lock_calls[-1]["params"]["_action"] == "UNLOCK"


@pytest.mark.parametrize("kwargs", [{}, {"row_type": "SCARR", "data_type": "CHAR"}])
def test_create_table_type_needs_exactly_one_row_type(kwargs):
    with pytest.raises(ValueError):
        create.create_table_type(PARAMS, "ZADTPY_TT", "$TMP", "desc", "DEVELOPER", **kwargs)


def test_create_service_binding(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    create.create_service_binding(
        PARAMS, "ZADTPY_SB", "$TMP", "desc", "DEVELOPER", "zadtpy_sd", category="web_api"
    )

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/businessservices/bindings"
    root = parse(call["body"])
    definition = root.find(f"{SRVB}services/{SRVB}content/{SRVB}serviceDefinition")
    assert definition.get(f"{ADTCORE}name") == "ZADTPY_SD"
    binding = root.find(f"{SRVB}binding")
    assert (binding.get(f"{SRVB}type"), binding.get(f"{SRVB}version")) == ("ODATA", "V4")
    assert binding.get(f"{SRVB}category") == "1"  # 0 = UI, 1 = Web API


def test_descriptions_carry_the_language(fake_sap):
    # without the language SAP silently drops the description
    calls = fake_sap(create, FakeResponse(201))
    create.create_domain(PARAMS, "ZADTPY_D", "$TMP", "desc", "DEVELOPER", "CHAR", 1, language="de")
    root = parse(calls[0]["body"])
    assert root.get(f"{ADTCORE}language") == "DE"
    assert root.get(f"{ADTCORE}masterLanguage") == "DE"
