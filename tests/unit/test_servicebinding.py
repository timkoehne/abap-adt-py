import pytest

from abap_adt_py.api import servicebinding
from abap_adt_py.exceptions import AdtError
from helpers import PARAMS, FakeResponse, fixture

PUBLISHED = """<?xml version="1.0" encoding="utf-8"?><asx:abap version="1.0" xmlns:asx="http://www.sap.com/abapxml"><asx:values><DATA><SEVERITY>OK</SEVERITY><SHORT_TEXT>ZADTPY_PUB_SB published locally</SHORT_TEXT><LONG_TEXT/></DATA></asx:values></asx:abap>"""
URL = "/sap/opu/odata4/sap/zadtpy_pub_sb/srvd/sap/zadtpy_pub_sb/0001/"


def test_publish_service_binding(fake_sap):
    calls = fake_sap(
        servicebinding,
        FakeResponse(200, fixture("service_binding.xml")),
        FakeResponse(200, PUBLISHED),
        FakeResponse(200, fixture("service_binding_odatav4.xml")),
    )

    assert servicebinding.publish_service_binding(PARAMS, "zadtpy_pub_sb") == [URL]

    read, publish, details = calls
    assert read["uri"] == "/sap/bc/adt/businessservices/bindings/zadtpy_pub_sb"
    assert (publish["method"], publish["uri"]) == ("POST", "/sap/bc/adt/businessservices/odatav4/publishjobs")
    assert publish["params"] == {"servicename": "ZADTPY_PUB_SB", "serviceversion": "0001"}
    assert 'adtcore:name="ZADTPY_PUB_SB"' in publish["body"]
    # SAP only finds the published service with the name in upper case
    assert details["uri"] == "/sap/bc/adt/businessservices/odatav4/ZADTPY_PUB_SB"
    assert details["params"] == {
        "servicename": "ZADTPY_PUB_SB",
        "serviceversion": "0001",
        "srvdname": "ZADTPY_PUB_SD",
    }


def test_publish_failure_with_status_200(fake_sap):
    fake_sap(
        servicebinding,
        FakeResponse(200, fixture("service_binding.xml")),
        FakeResponse(200, fixture("publish_failed.xml")),
    )
    with pytest.raises(AdtError) as error:
        servicebinding.publish_service_binding(PARAMS, "ZADTPY_PUB_SB")
    assert str(error.value) == (
        "200 - Failed to publish ZADTPY_PUB_SB: Local Publish of ZADTPY_NOPE_SB failed; "
        "Service Binding ZADTPY_NOPE_SB does not exist."
    )


def test_unpublish_service_binding(fake_sap):
    calls = fake_sap(
        servicebinding,
        FakeResponse(200, fixture("service_binding.xml")),
        FakeResponse(200, PUBLISHED.replace("published", "un-published")),
    )
    assert servicebinding.unpublish_service_binding(PARAMS, "ZADTPY_PUB_SB")
    assert calls[1]["uri"] == "/sap/bc/adt/businessservices/odatav4/unpublishjobs"


def test_get_service_binding(fake_sap):
    fake_sap(
        servicebinding,
        FakeResponse(200, fixture("service_binding.xml")),
        FakeResponse(200, fixture("service_binding_odatav4.xml")),
    )
    assert servicebinding.get_service_binding(PARAMS, "ZADTPY_PUB_SB") == {
        "name": "ZADTPY_PUB_SB",
        "description": "adt-py binding",
        "package": "$TMP",
        "binding_type": "ODATA",
        "binding_version": "V4",
        "category": "ui",
        "published": True,
        "services": [
            {"name": "ZADTPY_PUB_SB", "version": "0001", "service_definition": "ZADTPY_PUB_SD", "url": URL}
        ],
    }


def test_unpublished_binding_has_no_urls(fake_sap):
    binding = fixture("service_binding.xml").replace('srvb:published="true"', 'srvb:published="false"')
    fake_sap(servicebinding, FakeResponse(200, binding))
    result = servicebinding.get_service_binding(PARAMS, "ZADTPY_PUB_SB")
    assert result["published"] is False
    assert result["services"][0]["url"] == ""
