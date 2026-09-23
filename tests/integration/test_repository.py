def test_package_tree(client, uid, cleanup):
    package, subpackage = f"$ZADTPY_{uid}", f"$ZADTPY_{uid}_SUB"
    program = f"Z_ADTPY_{uid}_PKG"
    program_uri = f"/sap/bc/adt/programs/programs/{program.lower()}"

    assert client.create_package(package, "adt-py test package", parent="$TMP")
    cleanup(f"/sap/bc/adt/packages/{package.lower()}")
    assert client.create_package(subpackage, "adt-py test subpackage", parent=package)
    cleanup(f"/sap/bc/adt/packages/{subpackage.lower()}")
    assert client.create("PROG/P", program, subpackage, "adt-py program in package")
    cleanup(program_uri)

    top = client.package_contents(package)
    assert [(o["object_type"], o["object_name"]) for o in top] == [
        ("DEVC/K", subpackage)
    ]

    everything = client.package_contents(package, recursive=True)
    [found] = [o for o in everything if o["object_name"] == program]
    assert found["object_type"] == "PROG/P"
    assert found["object_uri"] == program_uri
    assert found["description"] == "adt-py program in package"

    path = [p["name"] for p in client.object_package_path(program_uri)]
    assert path[-2:] == [package, subpackage]


def test_structure_package(client, uid, cleanup):
    package = f"$ZADTPY_{uid}_STR"
    assert client.create_package(package, "adt-py structure package", package_type="structure")
    cleanup(f"/sap/bc/adt/packages/{package.lower()}")
    assert client.package_contents(package) == []


def test_unknown_package_is_empty(client):
    assert client.package_contents("ZADTPY_DOES_NOT_EXIST") == []


def test_node_contents_groups(client):
    structure = client.node_contents("DEVC/K", "SABP_RTTI")
    groups = {n["object_type"]: n["node_id"] for n in structure["nodes"] if not n["object_name"]}
    assert groups.get("DEVC/OC")

    classes = client.node_contents("DEVC/K", "SABP_RTTI", groups["DEVC/OC"])
    names = [n["object_name"] for n in classes["nodes"]]
    assert "CL_ABAP_TYPEDESCR" in names
