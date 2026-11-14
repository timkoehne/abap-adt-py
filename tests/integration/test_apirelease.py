def test_released_api(client):
    state = client.get_api_release_state("/sap/bc/adt/oo/classes/cl_abap_context_info")
    assert (state["name"], state["state"], state["cloud_development"]) == ("CL_ABAP_CONTEXT_INFO", "RELEASED", True)


def test_not_released_api_with_successor(client):
    state = client.get_api_release_state("/sap/bc/adt/functions/groups/snr3/fmodules/number_get_next")
    assert state["cloud_development"] is False
    assert [s["name"] for s in state["successors"]] == ["CL_NUMBERRANGE_RUNTIME"]


def test_class_in_a_namespace(client):
    hit = [h for h in client.search_object("/UI2/CL_JSON", 5) if h["name"] == "/UI2/CL_JSON"][0]
    assert client.get_api_release_state(hit["uri"])["cloud_development"] is True
