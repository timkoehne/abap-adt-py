import pytest


def test_run_class(client, runnable_class):
    name = runnable_class("RUN", "    out->write( |Hello from { sy-uname }| ).\n    out->write( 42 ).")
    output = client.run_class(name)
    # numbers are padded with trailing blanks in the console output
    lines = [line.rstrip() for line in output.splitlines()]
    assert lines[:2] == [f"Hello from {client.username}", "42"]


def test_run_class_runtime_error(client, runnable_class):
    name = runnable_class("ERR", "    DATA(zero) = 0.\n    out->write( 1 / zero ).")
    with pytest.raises(Exception, match="500 - Running .* failed: Division by 0"):
        client.run_class(name)


def test_run_missing_class_returns_explanation(client):
    # SAP reports this as normal output, not as an error
    output = client.run_class("ZCL_ADTPY_DOES_NOT_EXIST")
    assert "ZCL_ADTPY_DOES_NOT_EXIST" in output
