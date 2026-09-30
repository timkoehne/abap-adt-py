# abap-adt-py

[![tests](https://github.com/timkoehne/abap-adt-py/actions/workflows/tests.yml/badge.svg)](https://github.com/timkoehne/abap-adt-py/actions/workflows/tests.yml)

**abap-adt-py** is a Python client library to interact with SAP systems via the ABAP Development Tools (ADT) REST API. It allows you to programmatically manage ABAP artifacts and workflows directly from Python.

## Features

- Authenticate and log in to SAP systems securely
- Create, read, edit, and activate ABAP objects, including dictionary and RAP objects
- Search ABAP repositories and metadata
- Browse packages and the repository tree
- Run ABAP SQL queries (data preview)
- Run classes and capture their console output
- Run ATC checks and read the findings' documentation
- Navigate code: go to definition, where-used list, code completion
- Read runtime errors (short dumps)
- Run ABAP unit tests and retrieve results
- Create, list, and release transport requests
- Seamless integration with Python for automation and scripting

## Installation

Install the package from PyPI:

```bash
pip install abap-adt-py
```

Or install from source:
```bash
git clone https://github.com/timkoehne/abap-adt-py.git
cd abap-adt-py
pip install .
```

# Usage
```python
# Test Report
report_name = "z_test"
report_uri = "/sap/bc/adt/programs/programs/z_test"

# establish connection to SAP system
client = AdtClient(
    sap_host="http://localhost:50000",
    username="DEVELOPER",
    password="<password>",
    client="001",
    language="EN",
)

# login
response = client.login()

# search
results: list = client.search_object(report_name, 50)
print(results)

# create a local package (transportable packages also need transport="<request number>")
client.create_package("$Z_DEMO", "Demo package", parent="$TMP")

# browse a package (subpackages appear as DEVC/K entries)
objects: list = client.package_contents("$TMP")
all_objects: list = client.package_contents("$TMP", recursive=True)

# package hierarchy of an object, top-level package first
packages: list = client.object_package_path(report_uri)

# run an ABAP SQL query, rows come back as dicts keyed by column name
result = client.run_query("SELECT carrid, connid, price FROM sflight", max_rows=10)
print(result["total_rows"], result["rows"])

# run a class implementing IF_OO_ADT_CLASSRUN and get its console output
output: str = client.run_class("ZCL_MY_CLASSRUN")

# run the ABAP Test Cockpit on objects or packages (system default variant unless given)
result = client.run_atc("/sap/bc/adt/packages/z_demo", check_variant="ZABAP_CLOUD_DEVELOPMENT")
for finding in result["findings"]:  # priority 1 = error, 2 = warning, 3 = information
    print(finding["priority"], finding["object_name"], finding["line"], finding["message"])
print(client.atc_documentation(result["findings"][0]["documentation_uri"]))
print(client.list_check_variants("Z*"))

# code navigation (lines start at 1, columns at 0; the source may be unsaved)
source_uri = "/sap/bc/adt/programs/programs/z_demo/source/main"
target = client.find_definition(source_uri, source, line=3, column=18)  # {"uri", "line", "column"} or None
usages = client.where_used("/sap/bc/adt/oo/classes/zcl_demo")  # one entry per usage with its code line
usages = client.where_used("/sap/bc/adt/oo/classes/zcl_demo/source/main", line=3, column=12)  # e.g. one method
proposals = client.code_completion(source_uri, source, line=6, column=17)

# runtime errors (short dumps, as in ST22)
from datetime import datetime, timedelta
for dump in client.list_dumps(user="DEVELOPER", since=datetime.now() - timedelta(days=1)):
    print(dump["datetime"], dump["runtime_error"], dump["program"], dump["short_text"])
dump = client.get_dump(dump["id"])
print(dump["chapters"]["Error analysis"])  # also "What happened?", "Information on where terminated", ...

# create report object
client.create(
    object_type="PROG/P",
    name=report_name,
    description="Test Program",
    parent="$TMP",
)

# more object types: structures (TABL/DS), service definitions (SRVD/SRV) and behavior
# definitions (BDEF/BDO, named after their root CDS entity) are created with create()
# and filled with set_object_source like a class. These are created with their settings
# (dictionary objects are activated right away, pass activate=False to skip that):
client.create_domain(
    "Z_DEMO_STATUS", "$TMP", "Order status", data_type="CHAR", length=1,
    fixed_values=[{"low": "N", "text": "New"}, {"low": "C", "text": "Completed"}],  # intervals: "high"
)
client.update_domain("Z_DEMO_STATUS", fixed_values=[...])  # arguments left out keep their value
print(client.get_domain("Z_DEMO_STATUS"))
client.create_data_element(
    "Z_DEMO_STATUS", "$TMP", "Order status", domain="Z_DEMO_STATUS",  # or data_type/length, reference_to
    labels={"short": "Status", "medium": "Order status", "long": "Order status", "heading": "Status"},
)
client.update_data_element("Z_DEMO_STATUS", labels={"short": "St."}, parameter_id="ZST")
print(client.get_data_element("Z_DEMO_STATUS"))
client.create_table_type("Z_DEMO_TT", "$TMP", "Demo table type", row_type="SCARR")  # or data_type/length
client.create_service_binding("Z_DEMO_SB", "$TMP", "Demo binding", service_definition="Z_DEMO_SD")  # OData V4 UI
client.activate("Z_DEMO_SB", "/sap/bc/adt/businessservices/bindings/z_demo_sb")
urls = client.publish_service_binding("Z_DEMO_SB")  # ["/sap/opu/odata4/sap/z_demo_sb/srvd/..."]
client.unpublish_service_binding("Z_DEMO_SB")

# message classes
client.create_message_class("Z_DEMO", "$TMP", "Demo messages", messages=[{"number": "001", "text": "Bin &1 is blocked"}])
client.set_messages("Z_DEMO", [{"number": "002", "text": "Quantity &1 is invalid", "self_explanatory": False}])
client.delete_messages("Z_DEMO", ["002"])
print(client.get_messages("Z_DEMO"))

# authorization objects (the activities are the allowed values of ACTVT)
client.create_authorization_object("Z_DEMO_AO", "$TMP", "Demo", "AAAB", ["BUKRS", "ACTVT"], ["02", "03"])

# BAdIs: an enhancement spot with a BAdI definition (the interface includes IF_BADI_INTERFACE) ...
client.create_enhancement_spot("Z_DEMO_SPOT", "$TMP", "Demo spot", [
    {"name": "Z_DEMO_BADI", "interface": "ZIF_DEMO_BADI", "single_use": False,
     "filters": [{"name": "PLANT", "type": "C", "data_element": "WERKS_D"}]},
])
print(client.get_enhancement_spot("Z_DEMO_SPOT"))
# ... and an enhancement implementation for it
client.create_enhancement_implementation("Z_DEMO_IMPL", "$TMP", "Demo implementation", "Z_DEMO_SPOT", [
    {"name": "Z_DEMO_BADI_1000", "badi": "Z_DEMO_BADI", "implementing_class": "ZCL_DEMO_BADI",
     "filters": [{"filter": "PLANT", "value": "1000"}]},  # all must match; a list of lists are alternatives
])
print(client.get_enhancement_implementation("Z_DEMO_IMPL"))

# read source code
src: str = client.get_object_source(f"{report_uri}/source/main")
print(src)

# configure pretty printing
pretty_print_settings: PrettyPrintSettings = {"indentation": True, "style": "keywordUpper"}
client.prettyprint_settings(pretty_print_settings)

# pretty print source code
src: str = f"Report {report_name}. Write 'test'."
pretty_src = client.prettyprint(src)

# write source code
lock_handle: str = client.lock(report_uri)
client.set_object_source(f"{report_uri}/source/main", pretty_src, lock_handle)
client.unlock(report_uri, lock_handle)

# activate object, raises ActivationError if it is still inactive afterwards
client.activate(report_name, report_uri)
# objects that depend on each other, e.g. a CDS root view with a composition and its child
client.activate_objects([("Z_ROOT", "/sap/bc/adt/ddic/ddl/sources/z_root"), ("Z_CHILD", "/sap/bc/adt/ddic/ddl/sources/z_child")])
print(client.inactive_objects())

# transportable objects: create a transport request and pass it along
transport: str = client.create_transport("/sap/bc/adt/packages/z_demo", "Demo changes", "Z_DEMO")
client.create_package("Z_DEMO", "Demo package", transport=transport)
client.create("PROG/P", "Z_DEMO_REPORT", "Z_DEMO", "Demo report", transport=transport)
info = client.transport_info("/sap/bc/adt/programs/programs/z_demo_report", "Z_DEMO")  # recording needed? usable requests?
print(client.list_transports())  # modifiable requests with their tasks and objects
client.release_transport(transport)  # releases the tasks first, then the request

# delete object
lock_handle: str = client.lock(report_uri)
client.delete(report_uri, lock_handle)
client.unlock(report_uri, lock_handle)

# delete several objects at once, without locking; needed for objects that use each other
client.delete_objects(["/sap/bc/adt/ddic/ddl/sources/z_root", "/sap/bc/adt/ddic/ddl/sources/z_child"])
```
# Errors
All errors derive from `AdtError` (an `Exception`) and carry `status_code`, `sap_type`, `sap_message` and the raw `response_text`:
```python
from abap_adt_py.exceptions import AdtError, NotFoundError, ObjectLockedError, ActivationError

try:
    handle = client.lock(report_uri)
except ObjectLockedError as error:  # someone else is editing the object
    print(error.sap_message)         # "User DEVELOPER is currently editing Z_TEST"

try:
    client.activate(report_name, report_uri)
except ActivationError as error:
    for message in error.messages:   # type, text, uri (with position), object
        print(message["type"], message["text"])
```
| Error | Raised when |
|---|---|
| `AuthenticationError` | login failed |
| `SessionError` | the session expired while an object was locked, or `reconnect=False` |
| `NotFoundError` | an object, check variant, transport request, ... doesn't exist |
| `ObjectLockedError` | the object is locked by another user or session (a `LockError`) |
| `InvalidLockHandleError` | writing without a valid lock (a `LockError`) |
| `ActivationError` | activation failed, details in `.messages` |
| `TransportError` | a transport request couldn't be created, released, deleted, ... |
| `QueryError` | an SQL query failed |
| `ClassRunError` | a runtime error occurred while running a class |

## Expired sessions
When the session expires (e.g. after SAP's idle timeout), the client logs in again and repeats the request once.
This only happens while no object is locked: locks belong to the session, so an expired session while holding a lock raises `SessionError` instead of silently continuing without the lock.
Pass `reconnect=False` to `AdtClient` to always get the `SessionError`.

# Testing
```bash
pip install -e ".[test]"
pytest
```
The unit tests run offline against responses recorded from a real SAP system (`tests/fixtures`).
The integration tests in `tests/integration` run against a live system and are skipped unless it is configured:
```bash
export ABAP_ADT_HOST=http://localhost:50000 ABAP_ADT_USER=DEVELOPER ABAP_ADT_PASSWORD=...
export ABAP_ADT_CLIENT=001 ABAP_ADT_LANGUAGE=EN  # optional, these are the defaults
pytest -m integration
```
They create objects with unique names in `$TMP` and delete them again. The test run stops after a failed login so a wrong password cannot lock the user.
Tests that create and release transport requests only run with `ABAP_ADT_TEST_TRANSPORTS=1`, because released requests stay in the system.

# Releasing
GitHub Actions runs the offline tests on Python 3.7 to 3.13 for every push and pull request.
To publish a new version to PyPI:
1. Set the new `version` in `pyproject.toml`, commit and push.
2. Create a GitHub release with the tag `v<version>`, e.g. `v0.2.0`.

The publish workflow then runs the tests, checks that the tag matches the version, builds the package and uploads it to PyPI.
