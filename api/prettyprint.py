import re
from typing import Literal, TypedDict, NotRequired
from http_request import HttpRequestParameters, request


class PrettyPrintSettings(TypedDict):
    indentation: bool
    style: Literal[
        "toLower", "toUpper", "keywordLower", "keywordUpper", "none", "keywordAuto"
    ]
    condense_method_calls: NotRequired[bool]
    default_auto_style: NotRequired[Literal["keywordLower", "keywordUpper"]]
    format_method_calls: NotRequired[bool]
    keep_identifier: NotRequired[bool]


def set_pretty_printer_settings(
    http_request_parameters: HttpRequestParameters, settings: PrettyPrintSettings
):

    condense_method_calls = (
        f"prettyprintersettings:condenseMethodCalls=\"{str(settings['condense_method_calls']).lower()}\""
        if "condense_method_calls" in settings
        else ""
    )
    default_auto_style = (
        f"prettyprintersettings:defaultAutoStyle=\"{settings['default_auto_style']}\""
        if "default_auto_style" in settings
        else ""
    )
    format_method_calls = (
        f"prettyprintersettings:formatMethodCalls=\"{str(settings['format_method_calls']).lower()}\""
        if "format_method_calls" in settings
        else ""
    )
    indentation = (
        f"prettyprintersettings:indentation=\"{str(settings['indentation']).lower()}\""
        if "indentation" in settings
        else ""
    )
    keep_identifier = (
        f"prettyprintersettings:keepIdentifier=\"{str(settings['keep_identifier']).lower()}\""
        if "keep_identifier" in settings
        else ""
    )
    style = (
        f"prettyprintersettings:style=\"{settings['style']}\""
        if "style" in settings
        else ""
    )

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <prettyprintersettings:PrettyPrinterSettings 
    xmlns:prettyprintersettings="http://www.sap.com/adt/prettyprintersettings"
        {condense_method_calls}
        {default_auto_style}
        {format_method_calls}
        {indentation}
        {keep_identifier}
        {style}
        />
        """

    response = request(
        http_request_parameters,
        uri="/sap/bc/adt/abapsource/prettyprinter/settings",
        params={},
        body=body,
        method="PUT",
        content_type="application/xml",
    )
    if response.status_code == 200:
        return True
    else:
        raise Exception(
            f"{response.status_code} Failed to set prettyprint settings\n{response.text}"
        )


def prettyprint(http_request_parameters: HttpRequestParameters, src: str):
    response = request(
        http_request_parameters,
        uri="/sap/bc/adt/abapsource/prettyprinter",
        params={},
        body=src,
        method="POST",
        content_type="text/plain; charset=utf-8",
    )
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(
            f"{response.status_code} Failed to prettyprint\n{response.text}"
        )
