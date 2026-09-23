# abap-adt-py

**abap-adt-py** is a Python client library to interact with SAP systems via the ABAP Development Tools (ADT) REST API. It allows you to programmatically manage ABAP artifacts and workflows directly from Python.

## Features

- Authenticate and log in to SAP systems securely
- Create, read, edit, and activate ABAP objects
- Search ABAP repositories and metadata
- Browse packages and the repository tree
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
git clone https://github.com/yourusername/abap-adt-py.git
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
    password="ABAPtr2022#01",
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

# create report object
client.create(
    object_type="PROG/P",
    name=report_name,
    description="Test Program",
    parent="$TMP",
)

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

# activate object
client.activate(report_name, report_uri)

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
```
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
