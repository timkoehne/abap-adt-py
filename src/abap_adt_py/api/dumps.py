"""Runtime errors (short dumps), as shown in transaction ST22."""

import re
import textwrap
import xml.etree.ElementTree as et
from datetime import datetime, timezone

from ..compat_typing import Dict, List, Optional, TypedDict
from ..exceptions import error_from_response
from ..http_request import HttpRequestParameters, request
from .xml_namespaces import XML_NAMESPACES


class DumpSummary(TypedDict):
    # pass to get_dump to read the whole dump
    id: str
    # e.g. COMPUTE_INT_ZERODIVIDE
    runtime_error: str
    # the terminated program, e.g. ZCL_DEMO======================CP for a class
    program: str
    user: str
    # when the error occurred, in UTC
    datetime: datetime
    # e.g. "Division by 0 (type I or INT8)"
    short_text: str


class Dump(DumpSummary):
    # e.g. CX_SY_ZERODIVIDE, "" if the error wasn't caused by an exception
    exception: str
    # the dump's chapters by title in ST22 order, e.g. "What happened?", "Error analysis",
    # "Information on where terminated", "Active Calls/Events", "Selected Variables"
    chapters: Dict[str, str]
    # the complete dump as text
    text: str


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _parse_feed(xml_text: str) -> List[DumpSummary]:
    atom = XML_NAMESPACES["atom"]
    dumps: List[DumpSummary] = []
    for entry in et.fromstring(xml_text).iterfind("atom:entry", XML_NAMESPACES):
        categories = {
            category.get("label"): category.get("term", "")
            for category in entry.iterfind("atom:category", XML_NAMESPACES)
        }
        dump_id = ""
        for link in entry.iterfind("atom:link", XML_NAMESPACES):
            if link.get("rel") == "self":
                # adt://A4H/sap/bc/adt/runtime/dump/... -> /sap/bc/adt/runtime/dump/...
                dump_id = re.sub(r"^adt://[^/]+", "", link.get("href", ""))
        dumps.append(
            {
                "id": dump_id,
                "runtime_error": categories.get("ABAP runtime error", ""),
                "program": categories.get("Terminated ABAP program", ""),
                "user": entry.findtext(f"{{{atom}}}author/{{{atom}}}name", ""),
                "datetime": _parse_time(entry.findtext(f"{{{atom}}}published", "")),
                "short_text": entry.findtext(f"{{{atom}}}title", "").strip(),
            }
        )
    return dumps


def list_dumps(
    http_request_parameters: HttpRequestParameters,
    user: Optional[str] = None,
    runtime_error: Optional[str] = None,
    since: Optional[datetime] = None,
    max_results: int = 50,
) -> List[DumpSummary]:
    """List runtime errors, newest first.

    since: only errors after this time. A datetime without time zone is taken as local time.
    """

    conditions = []
    if user:
        conditions.append(f"equals( user, {user.upper()} )")
    if runtime_error:
        conditions.append(f"equals( runtimeError, {runtime_error.upper()} )")
    if since:
        utc = since.astimezone(timezone.utc)
        conditions.append(f"greater( datetime, {utc.strftime('%Y%m%d%H%M%S')} )")

    params = {"$top": max_results}
    if conditions:
        # the feed only accepts conditions inside and( ... ), even a single one
        params["$query"] = f"and( {', '.join(conditions)} )"

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/runtime/dumps",
        method="GET",
        body="",
        params=params,
        accept="application/atom+xml;type=feed",
    )
    if response.status_code != 200:
        raise error_from_response(response, "Failed to list runtime errors")
    return _parse_feed(response.text)


def _parse_chapters(lines: List[str], headings: List[tuple]) -> Dict[str, str]:
    """Cut the formatted dump into chapters, from the (line, title) headings SAP reports."""
    chapters: Dict[str, str] = {}
    for line_number, title in sorted(headings):
        # a chapter is a box: "|Title", then "|content" lines until the closing dashes
        content = []
        for line in lines[line_number:]:
            if line.startswith("---"):
                break
            content.append(line.rstrip().rstrip("|").rstrip()[1:])
        chapters[title] = textwrap.dedent("\n".join(content)).strip("\n")
    return chapters


def get_dump(http_request_parameters: HttpRequestParameters, dump_id: str) -> Dump:
    """Read a runtime error, dump_id as returned by list_dumps."""

    response = request(
        http_request_parameters=http_request_parameters,
        uri=dump_id,
        method="GET",
        body="",
        params={},
        accept="application/vnd.sap.adt.runtime.dump.v1+xml",
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read runtime error {dump_id}")
    root = et.fromstring(response.text)

    formatted = request(
        http_request_parameters=http_request_parameters,
        uri=f"{dump_id}/formatted",
        method="GET",
        body="",
        params={},
        accept="text/plain",
    )
    if formatted.status_code != 200:
        raise error_from_response(formatted, f"Failed to read runtime error {dump_id}")
    # SAP pads every line to the same width
    lines = [line.rstrip() for line in formatted.text.split("\n")]

    headings = [
        (int(chapter.get("line", "0")), chapter.get("title", ""))
        for chapter in root.iterfind("dump:chapters/dump:chapter", XML_NAMESPACES)
    ]
    chapters = _parse_chapters(
        lines, [(line, title) for line, title in headings if 0 < line <= len(lines)]
    )

    return {
        "id": dump_id,
        "runtime_error": root.get("error", ""),
        "exception": root.get("exception", ""),
        "program": root.get("terminatedProgram", ""),
        "user": root.get("author", ""),
        "datetime": _parse_time(root.get("datetime", "")),
        "short_text": chapters.get("Short Text", ""),
        "chapters": chapters,
        "text": "\n".join(lines).strip("\n"),
    }
