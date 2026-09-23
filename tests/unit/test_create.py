import xml.etree.ElementTree as et

import pytest

from abap_adt_py.api import create
from helpers import PARAMS, FakeResponse

ADTCORE = "{http://www.sap.com/adt/core}"
PAK = "{http://www.sap.com/adt/packages}"


def parse(body: str) -> et.Element:
    return et.fromstring(body.strip())


def test_create_program(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    assert create.create(PARAMS, "PROG/P", "Z_TEST", "$TMP", "Test", "DEVELOPER")

    call = calls[0]
    assert call["method"] == "POST"
    assert call["uri"] == "/sap/bc/adt/programs/programs"
    assert call["params"] == {}
    root = parse(call["body"])
    assert root.tag == "{http://www.sap.com/adt/programs/programs}abapProgram"
    assert root.get(f"{ADTCORE}name") == "Z_TEST"
    assert root.get(f"{ADTCORE}type") == "PROG/P"
    assert root.get(f"{ADTCORE}responsible") == "DEVELOPER"
    assert root.find(f"{ADTCORE}packageRef").get(f"{ADTCORE}name") == "$TMP"


def test_create_escapes_description(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    description = 'Tom & Jerry "quoted" <x>'
    create.create(PARAMS, "CLAS/OC", "ZCL_TEST", "$TMP", description, "DEVELOPER")

    assert parse(calls[0]["body"]).get(f"{ADTCORE}description") == description


def test_create_function_module_uses_group(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    create.create(PARAMS, "FUGR/FF", "Z_FM", "ZGROUP", "Test", "DEVELOPER")

    assert calls[0]["uri"] == "/sap/bc/adt/functions/groups/ZGROUP/fmodules"
    container = parse(calls[0]["body"]).find(f"{ADTCORE}containerRef")
    assert container.get(f"{ADTCORE}type") == "FUGR/F"
    assert container.get(f"{ADTCORE}uri") == "ZGROUP"


def test_create_with_transport(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    create.create(
        PARAMS, "PROG/P", "Z_TEST", "ZPKG", "Test", "DEVELOPER", "A4HK900001"
    )
    assert calls[0]["params"] == {"corrNr": "A4HK900001"}


def test_create_failure_raises(fake_sap):
    fake_sap(create, FakeResponse(400, "already exists"))
    with pytest.raises(Exception, match="400.*Z_TEST"):
        create.create(PARAMS, "PROG/P", "Z_TEST", "$TMP", "Test", "DEVELOPER")


def test_create_test_class_include(fake_sap):
    calls = fake_sap(create, FakeResponse(200))
    create.create_test_class_include(PARAMS, "ZCL_TEST", "HANDLE", "A4HK900001")

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/oo/classes/ZCL_TEST/includes"
    assert call["params"] == {"lockHandle": "HANDLE", "corrNr": "A4HK900001"}
    root = parse(call["body"])
    assert root.get("{http://www.sap.com/adt/oo/classes}includeType") == "testclasses"


def test_create_local_package(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    create.create_package(PARAMS, "$ZPKG", "Local", "DEVELOPER", parent="$TMP")

    call = calls[0]
    assert call["uri"] == "/sap/bc/adt/packages"
    assert call["params"] == {}
    root = parse(call["body"])
    assert root.get(f"{ADTCORE}name") == "$ZPKG"
    assert root.find(f"{PAK}superPackage").get(f"{ADTCORE}name") == "$TMP"
    assert root.find(f"{PAK}attributes").get(f"{PAK}recordChanges") == "false"
    component = root.find(f"{PAK}transport/{PAK}softwareComponent")
    assert component.get(f"{PAK}name") == "LOCAL"


def test_create_transportable_package(fake_sap):
    calls = fake_sap(create, FakeResponse(201))
    create.create_package(
        PARAMS,
        "ZPKG",
        "Transportable",
        "DEVELOPER",
        package_type="structure",
        transport_layer="ZDEV",
        transport="A4HK900001",
    )

    call = calls[0]
    assert call["params"] == {"corrNr": "A4HK900001"}
    root = parse(call["body"])
    attributes = root.find(f"{PAK}attributes")
    assert attributes.get(f"{PAK}packageType") == "structure"
    # SAP refuses non-local packages unless change recording is switched on
    assert attributes.get(f"{PAK}recordChanges") == "true"
    transport = root.find(f"{PAK}transport")
    assert transport.find(f"{PAK}softwareComponent").get(f"{PAK}name") == "HOME"
    assert transport.find(f"{PAK}transportLayer").get(f"{PAK}name") == "ZDEV"


def test_create_package_failure_raises(fake_sap):
    fake_sap(create, FakeResponse(400, "Change recording must be activated"))
    with pytest.raises(Exception, match="Change recording"):
        create.create_package(PARAMS, "ZPKG", "x", "DEVELOPER")
