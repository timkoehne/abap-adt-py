from typing import Literal
import requests
from requests.auth import HTTPBasicAuth

from api.activation import activate
from api.locking import lock, unlock
from api.login import login
from api.objectcontent import get_object_source, set_object_source
from api.search import search_object
from http_request import HttpRequestParameters


class AdtClient:
    sap_host: str
    csrf_token: str = "fetch"
    request_number: int = 0
    statefulness: Literal["stateless", "stateful"] = "stateless"

    def __init__(
        self, sap_host: str, username: str, password: str, client: str, language: str
    ):
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
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

    def search_object(self, query: str, max_results: int = 1) -> list[dict[str, str]]:
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