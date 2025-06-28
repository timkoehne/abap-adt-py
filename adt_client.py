from typing import Literal
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as et
from response_parsing import (
    find_xml_element_text,
    find_xml_elements_attributes,
    find_xml_element_attributes,
)


class AdtClient:
    sap_host: str = ""
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

    def _request(
        self,
        url: str,
        params: dict,
        method: Literal["GET", "POST", "PUT"] = "GET",
        body: str = "",
        content_type: str = "application/xml",
    ) -> requests.Response:
        config = {
            "params": params,
            "headers": {
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "x-csrf-token": self.csrf_token,
                "X-sap-adt-sessiontype": self.statefulness,
                "content-type": content_type,
            },
            "url": url,
            "data": body,
        }
        self.request_number += 1

        if method == "POST":
            response = self.session.post(**config)
        elif method == "GET":
            response = self.session.get(**config)
        elif method == "PUT":
            response = self.session.put(**config)
        else:
            raise ValueError(f"Unsupported method: {method}")
        return response

    def login(self) -> bool:
        url = f"http://{self.sap_host}/sap/bc/adt/compatibility/graph"
        response = self._request(url, params={})

        csrf_token = response.headers.get("x-csrf-token")
        if csrf_token is not None:
            self.csrf_token = csrf_token

        if response.status_code == 200:
            return True
        else:
            raise Exception(f"{response.status_code} - Login failed.\n{response.text}")

    def search_object(self, query: str, max_results: int = 1) -> list[dict[str, str]]:
        url = f"http://{self.sap_host}/sap/bc/adt/repository/informationsystem/search"
        params = {"operation": "quickSearch", "query": query, "maxResults": max_results}
        response = self._request(url, params=params)
        elements = find_xml_elements_attributes(
            response.text, "adtcore:objectReference"
        )
        return elements

    def get_object_source(
        self, object_uri: str, version: Literal["active", "inactive"] = "active"
    ) -> str:
        url = f"http://{self.sap_host}{object_uri}"

        params = {}
        if version:
            params["version"] = version

        response = self._request(url, params=params)

        if response.status_code == 200:
            return response.text
        else:
            raise Exception(
                f"{response.status_code} - Failed to get object source.\n{response.text}"
            )

    def activate(self, object_name: str, object_uri: str) -> bool:
        url = f"http://{self.sap_host}/sap/bc/adt/activation"

        params = {"method": "activate", "preauditRequested": "true"}
        body = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
            <adtcore:objectReference adtcore:uri="{object_uri}" adtcore:name="{object_name}"/>
        </adtcore:objectReferences>
        """

        response = self._request(url, params=params, body=body, method="POST")

        properties = find_xml_element_attributes(response.text, "chkl:properties")
        if (
            properties["activationExecuted"] == "true"
            or properties["generationExecuted"] == "true"
        ):
            return True
        else:
            msg_elements = find_xml_elements_attributes(response.text, "msg")
            raise Exception(
                f"{response.status_code} - Activation failed.\n{msg_elements}"
            )

    def lock(self, object_uri: str) -> str:
        self.statefulness = "stateful"
        url = f"http://{self.sap_host}{object_uri}"
        params = {"_action": "LOCK", "accessMode": "MODIFY"}
        response = self._request(url, params=params, method="POST")

        if response.status_code == 200:
            lock_handle = find_xml_element_text(response.text, ".//LOCK_HANDLE")
            return lock_handle
        else:
            raise Exception(
                f"{response.status_code} Failed to lock {object_uri}.\n{response.text}"
            )

    def unlock(self, object_uri: str, lock_handle: str) -> bool:
        url = f"http://{self.sap_host}{object_uri}"
        params = {"_action": "UNLOCK", "lockHandle": lock_handle}
        response = self._request(url, params=params, method="POST")

        if response.status_code == 200:
            self.statefulness = "stateless"
            return True
        else:
            raise Exception(
                f"{response.status_code} Failed to unlock {object_uri}\n{response.text}"
            )

    def set_object_source(
        self, object_uri: str, source_code: str, lock_handle: str
    ) -> bool:
        url = f"http://{self.sap_host}{object_uri}"
        params = {"lockHandle": lock_handle}
        response = self._request(
            url,
            params=params,
            body=source_code,
            method="PUT",
            content_type="text/plain; charset=utf-8",
        )

        if response.status_code == 200:
            return True
        else:
            raise Exception(
                f"{response.status_code} - Failed to set source code for {object_uri}\n{response.text}"
            )
