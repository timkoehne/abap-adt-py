import xml.etree.ElementTree as et

from ..compat_typing import Dict, List, TypedDict
from ..exceptions import QueryError, error_from_response
from ..http_request import HttpRequestParameters, request
from .xml_namespaces import XML_NAMESPACES


class QueryColumn(TypedDict):
    name: str
    # ABAP type code, e.g. C (character), N (numeric text), D (date), P (packed number)
    type: str
    description: str
    key: bool


class QueryResult(TypedDict):
    columns: List[QueryColumn]
    # values are strings as formatted by SAP, e.g. dates as YYYYMMDD
    rows: List[Dict[str, str]]
    # number of rows the query matches, which can be more than were returned
    total_rows: int
    executed_query: str


def _attr(element: et.Element, name: str) -> str:
    return element.get(f"{{{XML_NAMESPACES['dataPreview']}}}{name}", "")


def _parse_query_result(xml_text: str) -> QueryResult:
    root = et.fromstring(xml_text)

    columns: List[QueryColumn] = []
    values: List[List[str]] = []
    for column in root.findall("dataPreview:columns", XML_NAMESPACES):
        metadata = column.find("dataPreview:metadata", XML_NAMESPACES)
        if metadata is None:
            continue
        columns.append(
            {
                "name": _attr(metadata, "name"),
                "type": _attr(metadata, "type"),
                "description": _attr(metadata, "description"),
                "key": _attr(metadata, "keyAttribute") == "true",
            }
        )
        # packed numbers carry a trailing sign position ("422.94 ", "-" if negative)
        values.append(
            [
                (data.text or "").rstrip()
                for data in column.findall(
                    "dataPreview:dataSet/dataPreview:data", XML_NAMESPACES
                )
            ]
        )

    # the response is column oriented, turn it into one dict per row
    names = [column["name"] for column in columns]
    rows = [dict(zip(names, row)) for row in zip(*values)]

    return {
        "columns": columns,
        "rows": rows,
        "total_rows": int(root.findtext("dataPreview:totalRows", "0", XML_NAMESPACES)),
        "executed_query": root.findtext(
            "dataPreview:executedQueryString", "", XML_NAMESPACES
        ),
    }


def run_query(
    http_request_parameters: HttpRequestParameters, query: str, max_rows: int = 100
) -> QueryResult:
    """Run an ABAP SQL SELECT statement and return at most max_rows rows."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/datapreview/freestyle",
        method="POST",
        body=query,
        params={"rowNumber": max_rows},
        content_type="text/plain; charset=utf-8",
        accept="application/vnd.sap.adt.datapreview.table.v1+xml",
    )

    if response.status_code == 200:
        return _parse_query_result(response.text)
    else:
        raise error_from_response(response, "Query failed", QueryError)
