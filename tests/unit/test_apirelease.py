from abap_adt_py.api import apirelease
from helpers import PARAMS, FakeResponse, fixture


def test_not_released_table_names_its_successor(fake_sap):
    calls = fake_sap(apirelease, FakeResponse(200, fixture("apirelease_tcurx.xml")))
    state = apirelease.get_api_release_state(PARAMS, "/sap/bc/adt/ddic/tables/tcurx")

    assert calls[0]["uri"] == "/sap/bc/adt/apireleases/%2Fsap%2Fbc%2Fadt%2Fddic%2Ftables%2Ftcurx"
    assert (state["name"], state["type"], state["uri"]) == ("TCURX", "TABL/DT", "/sap/bc/adt/ddic/tables/tcurx")
    assert state["state"] == "NOT_TO_BE_RELEASED"
    # C1 allows the use in cloud development, but TCURX is not released under it
    assert (state["cloud_development"], state["key_user"]) == (False, False)
    assert state["successors"] == [
        {"name": "I_CURRENCY", "type": "DDLS/DF", "uri": "/sap/bc/adt/ddic/ddl/sources/i_currency"}
    ]
    assert [(c["contract"], c["state"]) for c in state["contracts"]] == [
        ("C0", "NOT_RELEASED"), ("C1", "NOT_TO_BE_RELEASED"), ("C3", "NOT_RELEASED")
    ]
    c1 = state["contracts"][1]
    assert (c1["state_description"], c1["use_in_cloud_development"], c1["successor_concept"]) == (
        "Not to Be Released", True, ""
    )


def test_released_class_in_a_namespace(fake_sap):
    calls = fake_sap(apirelease, FakeResponse(200, fixture("apirelease_namespace_class.xml")))
    state = apirelease.get_api_release_state(PARAMS, "/sap/bc/adt/oo/classes/%2fui2%2fcl_json")

    # the object's own escapes are escaped again
    assert calls[0]["uri"].endswith("%2Fclasses%2F%252fui2%252fcl_json")
    assert (state["name"], state["state"]) == ("/UI2/CL_JSON", "RELEASED")
    assert (state["cloud_development"], state["key_user"]) == (True, False)
    assert state["successors"] == []


def test_released_with_feature_toggle_is_not_usable_in_cloud_development(fake_sap):
    fake_sap(apirelease, FakeResponse(200, fixture("apirelease_function_module.xml")))
    state = apirelease.get_api_release_state(
        PARAMS, "/sap/bc/adt/functions/groups/scun/fmodules/convert_to_foreign_currency"
    )
    assert (state["type"], state["state"], state["cloud_development"]) == (
        "FUGR/FF", "RELEASED_WITH_FEATURE_TOGGLE", False
    )


def test_object_without_contracts():
    state = apirelease.parse_api_release(
        '<ars:apiRelease xmlns:ars="http://www.sap.com/adt/ars"><ars:releasableObject '
        'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:uri="/sap/bc/adt/oo/classes/zcl_x" '
        'adtcore:type="CLAS/OC" adtcore:name="ZCL_X"/></ars:apiRelease>'
    )
    assert (state["state"], state["cloud_development"], state["contracts"]) == ("NOT_RELEASED", False, [])
