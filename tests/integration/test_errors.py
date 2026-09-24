import pytest

from abap_adt_py.adt_client import AdtClient
from abap_adt_py.exceptions import (
    ActivationError,
    InvalidLockHandleError,
    NotFoundError,
    ObjectLockedError,
    QueryError,
    SessionError,
)
from helpers import locked, write_source


@pytest.fixture
def program(client, uid, cleanup):
    name = f"Z_ADTPY_{uid}_ERR"
    uri = f"/sap/bc/adt/programs/programs/{name.lower()}"
    client.create("PROG/P", name, "$TMP", "adt-py error test")
    cleanup(uri)
    return {"name": name, "uri": uri}


def test_missing_object(client):
    with pytest.raises(NotFoundError) as error:
        client.lock("/sap/bc/adt/programs/programs/z_adtpy_does_not_exist")
    assert "does not exist" in error.value.sap_message
    client.statefulness = "stateless"


def test_object_locked_by_another_session(client, config, program):
    other = AdtClient(**config)
    other.login()
    with locked(client, program["uri"]):
        with pytest.raises(ObjectLockedError) as error:
            other.lock(program["uri"])
    assert error.value.status_code == 403
    assert program["name"] in error.value.sap_message


def test_write_without_lock(client, program):
    with pytest.raises(InvalidLockHandleError):
        client.set_object_source(program["uri"] + "/source/main", "REPORT x.", "NOT_A_HANDLE")


def test_activation_error(client, program):
    write_source(client, program["uri"], f"REPORT {program['name'].lower()}.\nWRITE undefined_variable.")
    with pytest.raises(ActivationError) as error:
        client.activate(program["name"], program["uri"])
    assert "UNDEFINED_VARIABLE" in str(error.value)
    [message] = [m for m in error.value.messages if m["type"] == "E"]
    assert "#start=2," in message["uri"]


def test_expired_session(config):
    client = AdtClient(**config)
    client.login()
    client.csrf_token = "expired"
    with pytest.raises(SessionError):
        client.create("PROG/P", "Z_ADTPY_NEVER_CREATED", "$TMP", "x")


def test_query_error(client):
    with pytest.raises(QueryError, match="ZADTPY_DOES_NOT_EXIST"):
        client.run_query("SELECT * FROM zadtpy_does_not_exist")
