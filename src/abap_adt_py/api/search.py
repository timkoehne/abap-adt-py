from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from ..response_parsing import find_xml_elements_attributes
from ..compat_typing import List, Dict


def search_object(
    http_request_parameters: HttpRequestParameters, query: str, max_results: int = 1
) -> List[Dict[str, str]]:

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/informationsystem/search",
        method="GET",
        body="",
        params={"operation": "quickSearch", "query": query, "maxResults": max_results},
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to search for {query}")
    elements = find_xml_elements_attributes(response.text, "adtcore:objectReference")
    return elements
