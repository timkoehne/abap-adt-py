import pytest


def test_run_query(client, uid, cleanup):
    # query a program created by this test, so the result doesn't depend on the system's demo data
    name = f"Z_ADTPY_{uid}_SQL"
    client.create("PROG/P", name, "$TMP", "adt-py query test")
    cleanup(f"/sap/bc/adt/programs/programs/{name.lower()}")

    result = client.run_query(
        f"SELECT obj_name, object, devclass FROM tadir WHERE obj_name = '{name}'"
    )
    assert result["total_rows"] == 1
    assert result["rows"] == [{"OBJ_NAME": name, "OBJECT": "PROG", "DEVCLASS": "$TMP"}]


def test_run_query_limits_rows(client):
    result = client.run_query("SELECT devclass FROM tdevc", max_rows=5)
    assert len(result["rows"]) == 5
    assert result["total_rows"] > 5


def test_run_query_error(client):
    with pytest.raises(Exception, match="ZADTPY_DOES_NOT_EXIST"):
        client.run_query("SELECT * FROM zadtpy_does_not_exist")
