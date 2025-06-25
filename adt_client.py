from typing import Literal
import requests
from requests.auth import HTTPBasicAuth


class AdtClient:
    sap_host: str = ""
    csrf_token: str = "fetch"
    request_number: int = 0

    def __init__(
        self, sap_host: str, username: str, password: str, client: str, language: str
    ):
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.sap_host = sap_host
        self.client = client
        self.language = language

    def _request(self, url: str, params: dict, method: Literal["GET", "POST"] = "GET"):
        config = {
            "params": params,
            "headers": {
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "x-csrf-token": self.csrf_token,
                "X-sap-adt-sessiontype": "stateless",
            },
            "url": url,
        }
        self.request_number += 1
        response = self.session.get(**config)
        response.raise_for_status()
        return response

    def login(self):
        url = f"http://{self.sap_host}/sap/bc/adt/compatibility/graph"

        response = self._request(url, params={})

        csrf_token = response.headers.get("x-csrf-token")
        if csrf_token is not None:
            self.csrf_token = csrf_token
        return response

    def search_object(self, query: str, max_results: int = 1) -> requests.Response:
        url = f"http://{self.sap_host}/sap/bc/adt/repository/informationsystem/search"

        params = {"operation": "quickSearch", "query": query, "maxResults": max_results}
        response = self._request(url, params=params)
        return response

    def get_object_source(
        self, object_uri: str, version: Literal["active", "inactive"] = "active"
    ) -> requests.Response:
        url = f"http://{self.sap_host}{object_uri}"

        params = {}
        if version:
            params["version"] = version

        response = self._request(url, params=params)
        return response
