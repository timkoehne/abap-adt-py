from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from .compat_typing import Literal, List, Dict, Optional, Union
from .api.syntax import SyntaxCheckResult, syntax_check
from .api.navigation import (
    CompletionProposal,
    SourceLocation,
    Usage,
    code_completion,
    find_definition,
    where_used,
)
from .api.objectstructure import object_structure
from .api.prettyprint import (
    PrettyPrintSettings,
    prettyprint,
    set_pretty_printer_settings,
)
from .api.create import (
    PackageTypes,
    create,
    create_package,
    create_test_class_include,
)
from .api.activate import activate
from .api.create import ObjectTypes
from .api.delete import delete
from .api.dumps import Dump, DumpSummary, get_dump, list_dumps
from .api.lock import lock, unlock
from .api.login import login
from .api.atc import (
    AtcResult,
    AtcVariant,
    atc_documentation,
    default_check_variant,
    list_check_variants,
    run_atc,
)
from .api.classrun import run_class
from .api.content import get_object_source, set_object_source
from .api.datapreview import QueryResult, run_query
from .api.search import search_object
from .api.transport import (
    TransportInfo,
    TransportRequest,
    create_transport,
    delete_transport,
    list_transports,
    release_transport,
    transport_info,
)
from .api.repository import (
    NodeStructure,
    PackageInfo,
    RepositoryNode,
    node_contents,
    object_package_path,
    package_contents,
)
from .api.unittest import UnitTestAlert, UnittestFlags, run_unit_test
from .http_request import HttpRequestParameters


class AdtClient:
    sap_host: str
    csrf_token: str = "fetch"
    request_number: int = 0
    statefulness: Literal["stateless", "stateful"] = "stateless"

    def __init__(
        self,
        sap_host: str,
        username: str,
        password: str,
        client: str,
        language: str,
        reconnect: bool = True,
    ):
        """reconnect: log in again and retry once when the session has expired.

        This only happens while no object is locked. Locks belong to the session,
        so an expired session while holding a lock raises SessionError instead.
        """
        self.username = username
        self.reconnect = reconnect
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        # merged into the query string of every request made with this session
        self.session.params = {"sap-client": client, "sap-language": language}
        self.sap_host = sap_host
        self.client = client
        self.language = language

    def build_request_parameters(self) -> HttpRequestParameters:
        http_request_parameters: HttpRequestParameters = {
            "host": self.sap_host,
            "csrf_token": self.csrf_token,
            "statefulness": self.statefulness,
            "request_number": self.request_number,
            "session": self.session,
        }
        # a new session can't continue the locks of the old one
        if self.reconnect and self.statefulness == "stateless":
            http_request_parameters["refresh_csrf_token"] = self._refresh_csrf_token
        self.request_number += 1
        return http_request_parameters

    def _refresh_csrf_token(self) -> str:
        self.login()
        return self.csrf_token

    def login(self) -> bool:
        http_request_parameters = self.build_request_parameters()
        self.csrf_token = login(http_request_parameters)
        return True

    def search_object(self, query: str, max_results: int = 1) -> List[Dict[str, str]]:
        http_request_parameters = self.build_request_parameters()
        elements = search_object(http_request_parameters, query, max_results)
        return elements

    def get_object_source(
        self, object_uri: str, version: Literal["active", "inactive"] = "active"
    ) -> str:
        http_request_parameters = self.build_request_parameters()
        response = get_object_source(http_request_parameters, object_uri, version)
        return response

    def activate(self, object_name: str, object_uri: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = activate(http_request_parameters, object_name, object_uri)
        return response

    def lock(self, object_uri: str) -> str:
        # built before switching to stateful, so an expired session can still reconnect
        http_request_parameters = self.build_request_parameters()
        self.statefulness = "stateful"
        http_request_parameters["statefulness"] = "stateful"
        response = lock(http_request_parameters, object_uri)
        return response

    def unlock(self, object_uri: str, lock_handle: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = unlock(http_request_parameters, object_uri, lock_handle)
        self.statefulness = "stateless"
        return response

    def set_object_source(
        self,
        object_uri: str,
        source_code: str,
        lock_handle: str,
        transport: Optional[str] = None,
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = set_object_source(
            http_request_parameters, object_uri, source_code, lock_handle, transport
        )
        return response

    def run_unit_test(
        self, object_uri: str, unit_test_flags: UnittestFlags = UnittestFlags()
    ) -> List[UnitTestAlert]:
        http_request_parameters = self.build_request_parameters()
        response = run_unit_test(http_request_parameters, object_uri, unit_test_flags)
        return response

    def delete(
        self, object_uri: str, lock_handle: str, transport: Optional[str] = None
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = delete(http_request_parameters, object_uri, lock_handle, transport)
        return response

    def create(
        self,
        object_type: ObjectTypes,
        name: str,
        parent: str,
        description: str,
        transport: Optional[str] = None,
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = create(
            http_request_parameters,
            object_type,
            name,
            parent,
            description,
            self.username,
            transport,
        )
        return response

    def create_package(
        self,
        name: str,
        description: str,
        parent: str = "",
        package_type: PackageTypes = "development",
        software_component: Optional[str] = None,
        transport_layer: str = "",
        transport: Optional[str] = None,
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = create_package(
            http_request_parameters,
            name,
            description,
            self.username,
            parent,
            package_type,
            software_component,
            transport_layer,
            transport,
        )
        return response

    def create_test_class_include(
        self, class_name: str, lock_handle: str, transport: Optional[str] = None
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = create_test_class_include(
            http_request_parameters, class_name, lock_handle, transport
        )
        return response

    def prettyprint(self, src: str) -> str:
        http_request_parameters = self.build_request_parameters()
        response = prettyprint(http_request_parameters, src)
        return response

    def prettyprint_settings(self, settings: PrettyPrintSettings) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = set_pretty_printer_settings(http_request_parameters, settings)
        return response

    def syntax_check(
        self,
        object_uri: str,
        include_uri: str,
        src: str,
        version: Literal["active", "inactive"] = "active",
    ) -> List[SyntaxCheckResult]:
        http_request_parameters = self.build_request_parameters()
        response = syntax_check(
            http_request_parameters, object_uri, include_uri, src, version
        )
        return response

    def object_structure(self, object_uri: str):
        http_request_parameters = self.build_request_parameters()
        response = object_structure(http_request_parameters, object_uri)
        return response

    def node_contents(
        self, parent_type: str, parent_name: str, node_key: Optional[str] = None
    ) -> NodeStructure:
        http_request_parameters = self.build_request_parameters()
        response = node_contents(
            http_request_parameters, parent_type, parent_name, node_key
        )
        return response

    def package_contents(
        self, package: str, recursive: bool = False
    ) -> List[RepositoryNode]:
        http_request_parameters = self.build_request_parameters()
        response = package_contents(http_request_parameters, package, recursive)
        return response

    def object_package_path(self, object_uri: str) -> List[PackageInfo]:
        http_request_parameters = self.build_request_parameters()
        response = object_package_path(http_request_parameters, object_uri)
        return response

    def transport_info(
        self, object_uri: str, package: str = "", operation: str = "I"
    ) -> TransportInfo:
        http_request_parameters = self.build_request_parameters()
        response = transport_info(
            http_request_parameters, object_uri, package, operation
        )
        return response

    def create_transport(self, object_uri: str, description: str, package: str) -> str:
        http_request_parameters = self.build_request_parameters()
        response = create_transport(
            http_request_parameters, object_uri, description, package
        )
        return response

    def list_transports(self, user: Optional[str] = None) -> List[TransportRequest]:
        http_request_parameters = self.build_request_parameters()
        response = list_transports(http_request_parameters, user or self.username)
        return response

    def release_transport(self, transport: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = release_transport(http_request_parameters, transport)
        return response

    def delete_transport(self, transport: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = delete_transport(http_request_parameters, transport)
        return response

    def run_query(self, query: str, max_rows: int = 100) -> QueryResult:
        http_request_parameters = self.build_request_parameters()
        response = run_query(http_request_parameters, query, max_rows)
        return response

    def run_class(self, class_name: str) -> str:
        http_request_parameters = self.build_request_parameters()
        response = run_class(http_request_parameters, class_name)
        return response

    def run_atc(
        self,
        object_uris: Union[str, List[str]],
        check_variant: Optional[str] = None,
        max_findings: int = 100,
    ) -> AtcResult:
        http_request_parameters = self.build_request_parameters()
        response = run_atc(
            http_request_parameters, object_uris, check_variant, max_findings
        )
        return response

    def default_check_variant(self) -> str:
        http_request_parameters = self.build_request_parameters()
        response = default_check_variant(http_request_parameters)
        return response

    def list_check_variants(
        self, pattern: str = "*", max_results: int = 100
    ) -> List[AtcVariant]:
        http_request_parameters = self.build_request_parameters()
        response = list_check_variants(http_request_parameters, pattern, max_results)
        return response

    def atc_documentation(self, documentation_uri: str, as_html: bool = False) -> str:
        http_request_parameters = self.build_request_parameters()
        response = atc_documentation(
            http_request_parameters, documentation_uri, as_html
        )
        return response

    def find_definition(
        self, source_uri: str, source: str, line: int, column: int
    ) -> Optional[SourceLocation]:
        http_request_parameters = self.build_request_parameters()
        response = find_definition(
            http_request_parameters, source_uri, source, line, column
        )
        return response

    def where_used(
        self,
        object_uri: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ) -> List[Usage]:
        http_request_parameters = self.build_request_parameters()
        response = where_used(http_request_parameters, object_uri, line, column)
        return response

    def code_completion(
        self, source_uri: str, source: str, line: int, column: int
    ) -> List[CompletionProposal]:
        http_request_parameters = self.build_request_parameters()
        response = code_completion(
            http_request_parameters, source_uri, source, line, column
        )
        return response

    def list_dumps(
        self,
        user: Optional[str] = None,
        runtime_error: Optional[str] = None,
        since: Optional[datetime] = None,
        max_results: int = 50,
    ) -> List[DumpSummary]:
        http_request_parameters = self.build_request_parameters()
        response = list_dumps(
            http_request_parameters, user, runtime_error, since, max_results
        )
        return response

    def get_dump(self, dump_id: str) -> Dump:
        http_request_parameters = self.build_request_parameters()
        response = get_dump(http_request_parameters, dump_id)
        return response
