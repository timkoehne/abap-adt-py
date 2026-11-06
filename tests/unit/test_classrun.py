import pytest

from abap_adt_py.api import classrun
from abap_adt_py.exceptions import ClassRunError
from helpers import PARAMS, FakeResponse, fixture


def test_run_class_returns_output(fake_sap):
    calls = fake_sap(classrun, FakeResponse(200, fixture("classrun_output.txt")))
    output = classrun.run_class(PARAMS, "zcl_demo")

    assert output == "Hello from DEVELOPER\n42  \n\n"
    call = calls[0]
    assert call["method"] == "POST"
    assert call["uri"] == "/sap/bc/adt/oo/classrun/ZCL_DEMO"
    assert call["accept"] == "text/plain"


@pytest.mark.parametrize(
    "output, reason",
    [
        (" For console output, a class must implement IF_OO_ADT_CLASSRUN  either directly ...",
         "the class is not active or does not implement IF_OO_ADT_CLASSRUN."),
        ("Object ZCL_DEMO of type CLAS does not exist.\n", "the class does not exist."),
    ],
)
def test_run_class_explanation_of_sap_is_an_error(fake_sap, output, reason):
    fake_sap(classrun, FakeResponse(200, output))
    with pytest.raises(ClassRunError) as error:
        classrun.run_class(PARAMS, "ZCL_DEMO")
    assert str(error.value) == f"Running ZCL_DEMO failed: {reason}"


def test_run_class_output_that_only_mentions_the_text_is_kept(fake_sap):
    output = "Checking: For console output, a class must implement IF_OO_ADT_CLASSRUN\n"
    fake_sap(classrun, FakeResponse(200, output))
    assert classrun.run_class(PARAMS, "ZCL_DEMO") == output


def test_run_class_runtime_error(fake_sap):
    fake_sap(classrun, FakeResponse(500, fixture("classrun_runtime_error.html")))
    with pytest.raises(Exception) as error:
        classrun.run_class(PARAMS, "ZCL_DEMO")

    assert str(error.value) == (
        "500 - Running ZCL_DEMO failed: Division by 0 (type I or INT8) "
        "(Message 20260924131739vhcala4hci_A4H_00 DEVELOPER 001)"
    )


def test_run_class_error_without_html(fake_sap):
    fake_sap(classrun, FakeResponse(403, "No authorization"))
    with pytest.raises(Exception, match="403 - Running ZCL_DEMO failed: No authorization"):
        classrun.run_class(PARAMS, "ZCL_DEMO")
