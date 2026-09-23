"""Integration tests against a live SAP system.

Configure the system with environment variables:
    ABAP_ADT_HOST       e.g. http://172.17.0.4:50000
    ABAP_ADT_USER
    ABAP_ADT_PASSWORD
    ABAP_ADT_CLIENT     default 001
    ABAP_ADT_LANGUAGE   default EN
    ABAP_ADT_TEST_TRANSPORTS=1  also run the transport tests. They create and
        release transport requests, which cannot be deleted afterwards.

Without ABAP_ADT_HOST, ABAP_ADT_USER and ABAP_ADT_PASSWORD all integration tests are skipped.
"""

import os
import pathlib
import uuid

import pytest

from abap_adt_py.adt_client import AdtClient
from helpers import delete_object

HERE = pathlib.Path(__file__).parent


def pytest_collection_modifyitems(items):
    for item in items:
        if HERE in pathlib.Path(item.fspath).parents:
            item.add_marker(pytest.mark.integration)


def _config():
    host = os.environ.get("ABAP_ADT_HOST")
    user = os.environ.get("ABAP_ADT_USER")
    password = os.environ.get("ABAP_ADT_PASSWORD")
    if not (host and user and password):
        pytest.skip("set ABAP_ADT_HOST, ABAP_ADT_USER and ABAP_ADT_PASSWORD")
    return {
        "sap_host": host,
        "username": user,
        "password": password,
        "client": os.environ.get("ABAP_ADT_CLIENT", "001"),
        "language": os.environ.get("ABAP_ADT_LANGUAGE", "EN"),
    }


@pytest.fixture(scope="session")
def config():
    return _config()


@pytest.fixture(scope="session")
def client(config):
    client = AdtClient(**config)
    try:
        client.login()
    except Exception as error:
        # a wrong password must not be retried: every failed login counts towards a user lock
        pytest.exit(f"Login to {config['sap_host']} failed, stopping the test run.\n{error}"[:500])
    return client


@pytest.fixture(scope="session")
def uid():
    """Suffix that keeps the names of this run's objects unique."""
    return uuid.uuid4().hex[:6].upper()


@pytest.fixture
def cleanup(client):
    """Register objects to delete after the test, even if it fails. Deletes in reverse order."""
    objects = []
    yield lambda object_uri, transport=None: objects.append((object_uri, transport))
    for object_uri, transport in reversed(objects):
        try:
            delete_object(client, object_uri, transport)
        except Exception as error:
            if "404" not in str(error)[:10]:
                print(f"cleanup of {object_uri} failed: {str(error)[:200]}")
