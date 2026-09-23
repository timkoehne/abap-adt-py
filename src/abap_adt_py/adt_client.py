import requests
from requests.auth import HTTPBasicAuth

from .compat_typing import Literal, List, Dict, Optional
from .api.syntax import SyntaxCheckResult, syntax_check
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
from .api.lock import lock, unlock
from .api.login import login
from .api.content import get_object_source, set_object_source
from .api.search import search_object
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
        self, sap_host: str, username: str, password: str, client: str, language: str
    ):
        self.username = username
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
        self.request_number += 1
        return http_request_parameters

    def login(self) -> bool:
        http_request_parameters = self.build_request_parameters()
        csrf_token = login(http_request_parameters)
        if csrf_token:
            self.csrf_token = csrf_token
            return True
        else:
            raise Exception("Login failed.")

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
        self.statefulness = "stateful"
        http_request_parameters = self.build_request_parameters()
        response = lock(http_request_parameters, object_uri)
        return response

    def unlock(self, object_uri: str, lock_handle: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = unlock(http_request_parameters, object_uri, lock_handle)
        self.statefulness = "stateless"
        return response

    def set_object_source(
        self, object_uri: str, source_code: str, lock_handle: str
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = set_object_source(
            http_request_parameters, object_uri, source_code, lock_handle
        )
        return response

    def run_unit_test(
        self, object_uri: str, unit_test_flags: UnittestFlags = UnittestFlags()
    ) -> List[UnitTestAlert]:
        http_request_parameters = self.build_request_parameters()
        response = run_unit_test(http_request_parameters, object_uri, unit_test_flags)
        return response

    def delete(self, object_uri: str, lock_handle: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = delete(http_request_parameters, object_uri, lock_handle)
        return response

    def create(
        self, object_type: ObjectTypes, name: str, parent: str, description: str
    ) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = create(
            http_request_parameters,
            object_type,
            name,
            parent,
            description,
            self.username,
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

    def create_test_class_include(self, class_name: str, lock_handle: str) -> bool:
        http_request_parameters = self.build_request_parameters()
        response = create_test_class_include(
            http_request_parameters, class_name, lock_handle
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
