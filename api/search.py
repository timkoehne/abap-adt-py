from http_request import HttpRequestParameters, request
from response_parsing import find_xml_elements_attributes


def search_object(
    http_request_parameters: HttpRequestParameters, query: str, max_results: int = 1
) -> list[dict[str, str]]:

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/repository/informationsystem/search",
        method="GET",
        body="",
        params={"operation": "quickSearch", "query": query, "maxResults": max_results},
    )
    elements = find_xml_elements_attributes(response.text, "adtcore:objectReference")
    return elements
