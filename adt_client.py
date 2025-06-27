from typing import Literal
import requests
from requests.auth import HTTPBasicAuth


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
    ):
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

    def activate(self, object_name: str, object_uri: str):
        url = f"http://{self.sap_host}/sap/bc/adt/activation"

        params = {"method": "activate", "preauditRequested": "true"}
        body = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
            <adtcore:objectReference adtcore:uri="{object_uri}" adtcore:name="{object_name}"/>
        </adtcore:objectReferences>
        """

        res = self._request(url, params=params, body=body, method="POST")

        # successful activation
        # <?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="http://www.sap.com/abapxml/checklist"><chkl:properties checkExecuted="true" activationExecuted="true" generationExecuted="true"/></chkl:messages>

        # was already activated, no changes
        # <?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="http://www.sap.com/abapxml/checklist"><chkl:properties checkExecuted="false" activationExecuted="false" generationExecuted="true"/></chkl:messages>

        # could not activate due to errors
        # <?xml version="1.0" encoding="utf-8"?><chkl:messages xmlns:chkl="http://www.sap.com/abapxml/checklist"><chkl:properties checkExecuted="true" activationExecuted="false" generationExecuted="false"/><msg objDescr="Class Z_HUMANEVAL_088, Method SORT_ARRAY" type="E" line="1" href="/sap/bc/adt/oo/classes/z_humaneval_088/source/main#start=18,29" forceSupported="true"><shortText><txt>The field "IV_ARRA[" is unknown, but there is a field with the similar name "IV_ARRAY[".</txt></shortText><atom:link href="art.syntax:GWR" rel="http://www.sap.com/adt/categories/quickfixes" xmlns:atom="http://www.w3.org/2005/Atom"/></msg></chkl:messages>

        return res

    def lock(self, object_uri: str):
        self.statefulness = "stateful"
        url = f"http://{self.sap_host}{object_uri}"
        params = {"_action": "LOCK", "accessMode": "MODIFY"}
        res = self._request(url, params=params, method="POST")
        return res

    def unlock(self, object_uri: str, lock_handle: str):
        url = f"http://{self.sap_host}{object_uri}"
        params = {"_action": "UNLOCK", "lockHandle": lock_handle}
        res = self._request(url, params=params, method="POST")
        self.statefulness = "stateless"
        return res

    def set_object_source(self, object_uri: str, source_code: str, lock_handle: str):
        url = f"http://{self.sap_host}{object_uri}"
        params = {"lockHandle": lock_handle}
        res = self._request(
            url,
            params=params,
            body=source_code,
            method="PUT",
            content_type="text/plain; charset=utf-8",
        )
        return res
