import pytest

from abap_adt_py.api import datapreview
from helpers import PARAMS, FakeResponse, fixture

QUERY = "SELECT carrid, connid, fldate, price, currency FROM sflight"


def test_run_query(fake_sap):
    calls = fake_sap(datapreview, FakeResponse(200, fixture("datapreview_sflight.xml")))
    result = datapreview.run_query(PARAMS, QUERY, 3)

    call = calls[0]
    assert call["method"] == "POST"
    assert call["uri"] == "/sap/bc/adt/datapreview/freestyle"
    assert call["body"] == QUERY
    assert call["params"] == {"rowNumber": 3}
    assert call["content_type"].startswith("text/plain")

    assert result["total_rows"] == 94
    assert result["executed_query"].startswith("SELECT CARRID, CONNID")
    assert [c["name"] for c in result["columns"]] == [
        "CARRID",
        "CONNID",
        "FLDATE",
        "PRICE",
        "CURRENCY",
    ]
    assert result["columns"][3] == {
        "name": "PRICE",
        "type": "P",
        "description": "PRICE",
        "key": False,
    }
    assert len(result["rows"]) == 3
    # the packed number's trailing sign position is stripped
    assert result["rows"][0] == {
        "CARRID": "AA",
        "CONNID": "0017",
        "FLDATE": "20161115",
        "PRICE": "422.94",
        "CURRENCY": "USD",
    }


def test_run_query_without_rows(fake_sap):
    empty = """<dataPreview:tableData xmlns:dataPreview="http://www.sap.com/adt/dataPreview">
        <dataPreview:totalRows>0</dataPreview:totalRows>
        <dataPreview:columns>
            <dataPreview:metadata dataPreview:name="CARRID" dataPreview:type="C"/>
            <dataPreview:dataSet/>
        </dataPreview:columns>
    </dataPreview:tableData>"""
    fake_sap(datapreview, FakeResponse(200, empty))
    result = datapreview.run_query(PARAMS, "SELECT carrid FROM scarr WHERE carrid = 'XX'")

    assert result["rows"] == []
    assert result["total_rows"] == 0
    assert [c["name"] for c in result["columns"]] == ["CARRID"]


def test_run_query_reports_sap_error_message(fake_sap):
    fake_sap(datapreview, FakeResponse(400, fixture("datapreview_error.xml")))
    with pytest.raises(Exception) as error:
        datapreview.run_query(PARAMS, "SELECT * FROM does_not_exist")
    assert str(error.value) == "400 - Query failed: Cannot find 'DOES_NOT_EXIST'"


def test_run_query_error_without_xml(fake_sap):
    fake_sap(datapreview, FakeResponse(500, "Internal Server Error"))
    with pytest.raises(Exception, match="500 - Query failed: Internal Server Error"):
        datapreview.run_query(PARAMS, QUERY)
