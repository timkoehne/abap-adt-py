import json

from abap_adt_py.api import create, lock, numberrange
from helpers import PARAMS, FakeResponse, fixture


def test_create_number_range_object(fake_sap):
    lock_calls = fake_sap(lock, FakeResponse(200, fixture("lock.xml")), FakeResponse(200))
    calls = fake_sap(create, FakeResponse(201), FakeResponse(200))

    numberrange.create_number_range_object(
        PARAMS, "zadtpy_nr", "$TMP", "numbers", "DEVELOPER", "num10", activate=False
    )

    post, put = calls
    assert (post["method"], post["uri"]) == ("POST", "/sap/bc/adt/numberranges/objects")
    assert 'adtcore:type="NROB/NRO"' in post["body"]
    # the attributes are the JSON source, saved under a lock on the object
    assert (put["method"], put["uri"]) == ("PUT", "/sap/bc/adt/numberranges/objects/zadtpy_nr/source/main")
    source = json.loads(put["body"])
    assert source["interval"]["numberLengthDomain"] == "NUM10"
    assert source["configuration"] == {"buffering": "none", "bufferedNumbers": 0}
    assert [c["uri"] for c in lock_calls] == ["/sap/bc/adt/numberranges/objects/zadtpy_nr"] * 2
