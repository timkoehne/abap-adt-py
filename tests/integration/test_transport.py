import os

import pytest

from helpers import delete_object, write_source

pytestmark = [
    pytest.mark.transport,
    pytest.mark.skipif(
        os.environ.get("ABAP_ADT_TEST_TRANSPORTS") != "1",
        reason="creates and releases transport requests; set ABAP_ADT_TEST_TRANSPORTS=1",
    ),
]


def test_transportable_package_lifecycle(client, uid):
    package = f"ZADTPY_{uid}"
    package_uri = f"/sap/bc/adt/packages/{package.lower()}"
    program = f"Z_ADTPY_{uid}_TR"
    program_uri = f"/sap/bc/adt/programs/programs/{program.lower()}"

    transport = client.create_transport(package_uri, "adt-py test", package)
    assert transport
    created = []
    try:
        assert client.create_package(package, "adt-py transport test", transport=transport)
        created.append(package_uri)

        info = client.transport_info(program_uri, package)
        assert info["recording"] is True
        assert transport in [r["number"] for r in info["requests"]]

        assert client.create("PROG/P", program, package, "adt-py", transport=transport)
        created.append(program_uri)
        write_source(client, program_uri, f"REPORT {program.lower()}.", transport)
        assert client.activate(program, program_uri)

        info = client.transport_info(program_uri, package, "U")
        assert info["existing_request_only"] is True
        assert [lock["request"]["number"] for lock in info["locks"]] == [transport]

        [request] = [r for r in client.list_transports() if r["number"] == transport]
        objects = [(o["wbtype"], o["name"]) for t in request["tasks"] for o in t["objects"]]
        assert ("DEVC/K", package) in objects
        assert ("PROG/P", program) in objects
    finally:
        # a package can only be deleted once the deletion of its objects is released
        if program_uri in created:
            delete_object(client, program_uri, transport)
        client.release_transport(transport)
        if package_uri in created:
            cleanup_transport = client.create_transport(
                package_uri, "adt-py test cleanup", package
            )
            delete_object(client, package_uri, cleanup_transport)
            client.release_transport(cleanup_transport)

    assert transport not in [r["number"] for r in client.list_transports()]


def test_delete_empty_transport(client, uid):
    transport = client.create_transport(
        f"/sap/bc/adt/packages/zadtpy_{uid.lower()}_none", "adt-py empty", f"ZADTPY_{uid}_NONE"
    )
    assert transport in [r["number"] for r in client.list_transports()]
    assert client.delete_transport(transport)
    assert transport not in [r["number"] for r in client.list_transports()]
