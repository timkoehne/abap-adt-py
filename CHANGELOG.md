# Changelog

## 0.2.0

### Changes that can affect existing code
- Errors are raised as `AdtError` subclasses (`NotFoundError`, `ObjectLockedError`, `ActivationError`, ...) with shorter messages containing SAP's error text. They are still `Exception`s, but code matching the old message texts needs updating. The full SAP response is available as `error.response_text`.
- `run_unit_test` returns each alert's `stack` as a list of dicts instead of an XML element, and adds `test_class` and `test_method`.

### Added
- Repository browsing: `package_contents`, `node_contents`, `object_package_path`
- Packages: `create_package`
- Transports: `transport_info`, `create_transport`, `list_transports`, `release_transport`, `delete_transport`, and a `transport` argument on `create`, `set_object_source` and `delete`
- SQL data preview: `run_query`
- Running classes with console output: `run_class`
- ATC: `run_atc`, `list_check_variants`, `default_check_variant`, `atc_documentation`
- Code navigation: `find_definition`, `where_used`, `code_completion`
- Runtime errors (short dumps): `list_dumps`, `get_dump`
- More object types: structures, service definitions and behavior definitions in `create`; `create_domain`, `create_table_type`, `create_service_binding`
- Expired sessions are reconnected automatically while no object is locked (`AdtClient(reconnect=False)` to disable)

### Fixed
- `client` and `language` passed to `AdtClient` are sent to SAP; before, the system's default client was used
- Special characters such as `&` or `"` in descriptions no longer produce invalid requests
- Locking packages failed with 406
- `syntax_check` failed on messages with a start and end position, and dropped messages in column 0
- `prettyprint_settings` failed with 415
- `activate` crashed on HTTP errors instead of raising them
- Calling `login` a second time failed
- Python 3.7 and 3.8 failed to import the package
- Installing from source on Python 3.7 failed

### Other
- Unit and integration tests, and CI on Python 3.7 to 3.13
- Automated PyPI releases from GitHub releases
