import pytest

from abap_adt_py.api import repository
from helpers import PARAMS, FakeResponse, fixture

PACKAGE = "SABAP_DEMOS_CAR_RENTAL"


def tree(*nodes) -> str:
    """Build a minimal nodestructure response from (type, name, node_id) tuples."""
    items = "".join(
        f"<SEU_ADT_REPOSITORY_OBJ_NODE><OBJECT_TYPE>{type_}</OBJECT_TYPE>"
        f"<OBJECT_NAME>{name}</OBJECT_NAME><NODE_ID>{node_id}</NODE_ID>"
        "</SEU_ADT_REPOSITORY_OBJ_NODE>"
        for type_, name, node_id in nodes
    )
    return (
        '<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0"><asx:values>'
        f"<DATA><TREE_CONTENT>{items}</TREE_CONTENT></DATA></asx:values></asx:abap>"
    )


def test_node_contents(fake_sap):
    calls = fake_sap(repository, FakeResponse(200, fixture("nodestructure_package.xml")))
    structure = repository.node_contents(PARAMS, "DEVC/K", PACKAGE)

    call = calls[0]
    assert call["method"] == "POST"
    assert call["uri"] == "/sap/bc/adt/repository/nodestructure"
    assert call["params"]["parent_type"] == "DEVC/K"
    assert call["params"]["parent_name"] == PACKAGE
    assert call["body"] == ""

    groups = [n for n in structure["nodes"] if not n["object_name"]]
    assert [(n["object_type"], n["node_id"]) for n in groups] == [
        ("DEVC/K", "000002"),
        ("DEVC/P", "000006"),
        ("DEVC/T", "000008"),
        ("DEVC/Q4L", "000010"),
    ]
    assert {"category": "source_library", "label": "Source Code Library"} in structure[
        "categories"
    ]
    assert {
        "object_type": "DEVC/K",
        "category": "",
        "label": "Subpackages",
        "node_id": "000002",
    } in structure["object_types"]


def test_node_contents_with_node_key(fake_sap):
    calls = fake_sap(repository, FakeResponse(200, fixture("nodestructure_group.xml")))
    structure = repository.node_contents(PARAMS, "DEVC/K", PACKAGE, "000006")

    assert "<TV_NODEKEY>000006</TV_NODEKEY>" in calls[0]["body"]
    assert structure["nodes"] == [
        {
            "object_type": "PROG/P",
            "object_name": "DEMO_CR_CALL_CAR_RENTAL",
            "tech_name": "DEMO_CR_CALL_CAR_RENTAL",
            "object_uri": "/sap/bc/adt/programs/programs/demo_cr_call_car_rental",
            "object_vit_uri": "/sap/bc/adt/vit/wb/object_type/progp/object_name/DEMO_CR_CALL_CAR_RENTAL",
            "expandable": True,
            "node_id": "",
            "description": "Call Car Rental Example",
        }
    ]


def test_node_contents_unknown_parent_is_empty(fake_sap):
    # SAP answers unknown packages and node keys with an empty 200 response
    fake_sap(repository, FakeResponse(200, ""))
    assert repository.node_contents(PARAMS, "DEVC/K", "ZDOES_NOT_EXIST") == {
        "nodes": [],
        "categories": [],
        "object_types": [],
    }


def test_node_contents_failure_raises(fake_sap):
    fake_sap(repository, FakeResponse(500, "error"))
    with pytest.raises(Exception, match="500"):
        repository.node_contents(PARAMS, "DEVC/K", PACKAGE)


def test_package_contents_expands_groups(fake_sap):
    group = FakeResponse(200, fixture("nodestructure_group.xml"))
    calls = fake_sap(
        repository,
        FakeResponse(200, fixture("nodestructure_package.xml")),
        group,
        group,
        group,
    )
    objects = repository.package_contents(PARAMS, PACKAGE)

    # every group but the subpackages is expanded by its node key
    expanded = [call["body"] for call in calls[1:]]
    assert len(expanded) == 3
    for node_id in ("000006", "000008", "000010"):
        assert any(f"<TV_NODEKEY>{node_id}</TV_NODEKEY>" in body for body in expanded)

    names = [(o["object_type"], o["object_name"]) for o in objects]
    assert ("DEVC/K", "SABAP_DEMOS_CAR_RENTAL_TYPES") in names
    assert ("TRAN/T", "DEMO_CR_CAR_RENTAL") in names
    # listed inline and in its group, but returned once
    assert names.count(("PROG/P", "DEMO_CR_CALL_CAR_RENTAL")) == 1
    assert all(o["object_name"] for o in objects)


def test_package_contents_recursive(fake_sap):
    calls = fake_sap(
        repository,
        FakeResponse(200, tree(("DEVC/K", "", "000001"), ("DEVC/K", "ZSUB", ""), ("PROG/P", "Z_TOP", ""))),
        FakeResponse(200, tree(("PROG/P", "Z_NESTED", ""))),
    )
    objects = repository.package_contents(PARAMS, "ZTOP", recursive=True)

    assert calls[1]["params"]["parent_name"] == "ZSUB"
    assert [o["object_name"] for o in objects] == ["ZSUB", "Z_TOP", "Z_NESTED"]


def test_object_package_path(fake_sap):
    calls = fake_sap(
        repository, FakeResponse(200, fixture("objectproperties_package.xml"))
    )
    path = repository.object_package_path(
        PARAMS, "/sap/bc/adt/oo/classes/cl_abap_typedescr"
    )

    assert calls[0]["params"] == {
        "uri": "/sap/bc/adt/oo/classes/cl_abap_typedescr",
        "facet": "package",
    }
    assert [p["name"] for p in path] == ["BASIS", "SABP_MAIN", "SABP_RTTI"]
    assert path[0] == {
        "name": "BASIS",
        "description": "BASIS Structure Package",
        "uri": "/sap/bc/adt/packages/basis",
    }


def test_object_package_path_failure_raises(fake_sap):
    fake_sap(repository, FakeResponse(404, "not found"))
    with pytest.raises(Exception, match="404"):
        repository.object_package_path(PARAMS, "/sap/bc/adt/oo/classes/zcl_missing")
