def test_number_range_object(client, uid, cleanup):
    # number range objects have at most 10 characters
    name = f"ZN{uid}"
    client.create_number_range_object(name, "$TMP", "adt-py numbers", "NUM10")
    cleanup(f"/sap/bc/adt/numberranges/objects/{name.lower()}")

    stored = client.run_query(f"SELECT domlen, buffer FROM tnro WHERE object = '{name}'")
    assert stored["rows"] == [{"DOMLEN": "NUM10", "BUFFER": ""}]
