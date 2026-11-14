import pytest

from abap_adt_py.api import create, delete, languageversion, lock
from abap_adt_py.exceptions import AdtError
from helpers import PARAMS, FakeResponse, fixture

CLASS = "/sap/bc/adt/oo/classes/zcl_adtlv_a"
CLASS_TYPE = {"content-type": "application/vnd.sap.adt.oo.classes.v4+xml; charset=utf-8"}


def test_get_language_version(fake_sap):
    calls = fake_sap(
        languageversion,
        FakeResponse(200, fixture("class_metadata_cloud.xml"), CLASS_TYPE),
        FakeResponse(200, fixture("language_versions.xml")),
    )
    assert languageversion.get_language_version(PARAMS, CLASS) == {
        "name": "ZCL_ADTLV_A",
        "type": "CLAS/OC",
        "uri": CLASS,
        "version": "cloudDevelopment",
        "allowed": ["keyUser", "cloudDevelopment", "standard"],
    }
    assert calls[1]["params"] == {"uri": CLASS}


def test_object_without_a_version(fake_sap):
    fake_sap(
        languageversion,
        FakeResponse(200, '<mc:messageClass xmlns:mc="http://www.sap.com/adt/MessageClass" '
                          'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:name="ZMC" adtcore:type="MSAG/N"/>'),
    )
    version = languageversion.get_language_version(PARAMS, "/sap/bc/adt/messageclass/zmc")
    assert (version["version"], version["allowed"]) == ("", [])


def test_set_language_version_saves_the_metadata_and_activates(fake_sap, monkeypatch):
    fake_sap(languageversion, FakeResponse(200, fixture("class_metadata_cloud.xml"), CLASS_TYPE))
    fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    puts = fake_sap(create, FakeResponse(200))
    activations = []
    monkeypatch.setattr(languageversion, "activate_objects", lambda params, objects: activations.append(objects) or True)

    languageversion.set_language_version(PARAMS, CLASS, "X", transport="A4HK900001")

    put = puts[0]
    assert (put["method"], put["uri"]) == ("PUT", CLASS)
    assert put["content_type"] == "application/vnd.sap.adt.oo.classes.v4+xml"
    assert put["params"]["corrNr"] == "A4HK900001"
    assert 'adtcore:abapLanguageVersion="standard"' in put["body"]
    assert "cloudDevelopment" not in put["body"]
    assert activations == [[("ZCL_ADTLV_A", CLASS)]]


@pytest.mark.parametrize("value, expected", [("5", "cloudDevelopment"), ("", "standard"), ("keyuser", "keyUser")])
def test_version_aliases(value, expected):
    assert languageversion.language_version(value) == expected


def test_unknown_version():
    with pytest.raises(ValueError, match="unknown ABAP language version"):
        languageversion.language_version("cloud development")


def test_create_sets_the_version_afterwards(fake_sap, monkeypatch):
    posts = fake_sap(create, FakeResponse(201))
    switched = []
    monkeypatch.setattr(
        languageversion, "set_language_version",
        lambda params, uri, version, transport, activate: switched.append((uri, version, activate)),
    )
    create.create(PARAMS, "INTF/OI", "ZIF_ADT", "$TMP", "desc", "DEVELOPER", language_version="5")

    assert posts[0]["uri"] == "/sap/bc/adt/oo/interfaces"
    # SAP refuses an interface with the version in the request that creates it
    assert "abapLanguageVersion" not in posts[0]["body"]
    assert switched == [("/sap/bc/adt/oo/interfaces/zif_adt", "cloudDevelopment", False)]


def test_create_deletes_an_object_that_refuses_the_version(fake_sap, monkeypatch):
    fake_sap(create, FakeResponse(201))
    deletions = fake_sap(delete, FakeResponse(200, fixture("deletion_success.xml")))

    def refuse(*args, **kwargs):
        raise AdtError("500 - Failed to save ZREPORT: ABAP language version 5 is not allowed in this software component")

    monkeypatch.setattr(languageversion, "set_language_version", refuse)
    with pytest.raises(AdtError, match="not allowed"):
        create.create(PARAMS, "PROG/P", "ZREPORT", "$TMP", "desc", "DEVELOPER", language_version="cloudDevelopment")
    assert "/sap/bc/adt/programs/programs/zreport" in deletions[0]["body"]


def test_create_refuses_a_version_for_function_modules():
    with pytest.raises(ValueError, match="no ABAP language version"):
        create.create(PARAMS, "FUGR/FF", "Z_FM", "ZGROUP", "desc", "DEVELOPER", language_version="5")
