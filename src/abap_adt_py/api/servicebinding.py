"""Publishing OData service bindings."""

import xml.etree.ElementTree as et
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from ..compat_typing import List, TypedDict
from ..exceptions import AdtError, error_from_response
from ..http_request import HttpRequestParameters, request

ADTCORE = "{http://www.sap.com/adt/core}"
SRVB = "{http://www.sap.com/adt/ddic/ServiceBindings}"
BINDING_CONTENT_TYPE = "application/vnd.sap.adt.businessservices.servicebinding.v2+xml"
DETAILS_CONTENT_TYPES = {
    "odatav2": "application/vnd.sap.adt.businessservices.odatav2.v3+xml",
    "odatav4": "application/vnd.sap.adt.businessservices.odatav4.v2+xml",
}


class ServiceBindingService(TypedDict):
    name: str
    version: str
    service_definition: str
    # e.g. /sap/opu/odata4/sap/zui_travel_o4/srvd/sap/ztravel/0001/, "" if not published
    url: str


class ServiceBinding(TypedDict):
    name: str
    description: str
    package: str
    # e.g. ODATA
    binding_type: str
    # e.g. V4
    binding_version: str
    # ui or web_api
    category: str
    published: bool
    services: List[ServiceBindingService]


def _binding_uri(name: str) -> str:
    return f"/sap/bc/adt/businessservices/bindings/{quote(name.lower(), safe='')}"


def _read_binding(http_request_parameters: HttpRequestParameters, name: str) -> et.Element:
    response = request(
        http_request_parameters,
        uri=_binding_uri(name),
        method="GET",
        body="",
        params={},
        accept=BINDING_CONTENT_TYPE,
    )
    if response.status_code != 200:
        raise error_from_response(response, f"Failed to read service binding {name}")
    return et.fromstring(response.text)


def _odata_path(binding: et.Element) -> str:
    element = binding.find(f"{SRVB}binding")
    binding_type = element.get(f"{SRVB}type", "") if element is not None else ""
    version = element.get(f"{SRVB}version", "") if element is not None else ""
    path = f"{binding_type}{version}".lower()
    if path not in DETAILS_CONTENT_TYPES:
        raise AdtError(
            f"Publishing {binding_type} {version} service bindings is not supported, "
            "only OData V2 and V4"
        )
    return path


def _services(binding: et.Element):
    """(service name, version, service definition) of each service of the binding."""
    for services in binding.iter(f"{SRVB}services"):
        for content in services.iter(f"{SRVB}content"):
            definition = content.find(f"{SRVB}serviceDefinition")
            yield (
                services.get(f"{SRVB}name", ""),
                content.get(f"{SRVB}version", ""),
                definition.get(f"{ADTCORE}name", "") if definition is not None else "",
            )


def _service_url(
    http_request_parameters: HttpRequestParameters,
    odata_path: str,
    binding_name: str,
    service: str,
    version: str,
    service_definition: str,
) -> str:
    response = request(
        http_request_parameters,
        # SAP only finds the published service with the name in upper case
        uri=f"/sap/bc/adt/businessservices/{odata_path}/{quote(binding_name.upper(), safe='')}",
        method="GET",
        body="",
        params={
            "servicename": service,
            "serviceversion": version,
            "srvdname": service_definition,
        },
        accept=DETAILS_CONTENT_TYPES[odata_path],
    )
    if response.status_code != 200:
        raise error_from_response(
            response, f"Failed to read the service details of {binding_name}"
        )
    for element in et.fromstring(response.text).iter():
        url = element.get(f"{{http://www.sap.com/categories/{odata_path}}}serviceUrl")
        if url:
            return url
    return ""


def get_service_binding(
    http_request_parameters: HttpRequestParameters, name: str
) -> ServiceBinding:
    """Read a service binding, with the URLs of its services if it is published."""
    binding = _read_binding(http_request_parameters, name)
    published = binding.get(f"{SRVB}published") == "true"
    element = binding.find(f"{SRVB}binding")
    package = binding.find(f"{ADTCORE}packageRef")

    services: List[ServiceBindingService] = []
    for service, version, service_definition in _services(binding):
        url = ""
        if published:
            url = _service_url(
                http_request_parameters,
                _odata_path(binding),
                name,
                service,
                version,
                service_definition,
            )
        services.append(
            {
                "name": service,
                "version": version,
                "service_definition": service_definition,
                "url": url,
            }
        )
    return {
        "name": binding.get(f"{ADTCORE}name", ""),
        "description": binding.get(f"{ADTCORE}description", ""),
        "package": package.get(f"{ADTCORE}name", "") if package is not None else "",
        "binding_type": element.get(f"{SRVB}type", "") if element is not None else "",
        "binding_version": element.get(f"{SRVB}version", "") if element is not None else "",
        "category": "web_api"
        if element is not None and element.get(f"{SRVB}category") == "1"
        else "ui",
        "published": published,
        "services": services,
    }


def _publish_job(
    http_request_parameters: HttpRequestParameters, name: str, action: str
) -> et.Element:
    """Run a publishjobs or unpublishjobs request for every service of the binding."""
    binding = _read_binding(http_request_parameters, name)
    odata_path = _odata_path(binding)
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
        <adtcore:objectReference adtcore:type="SRVB/SVB" adtcore:name={quoteattr(name.upper())}/>
    </adtcore:objectReferences>"""

    for service, version, _ in _services(binding):
        response = request(
            http_request_parameters,
            uri=f"/sap/bc/adt/businessservices/{odata_path}/{action}",
            method="POST",
            body=body,
            params={"servicename": service, "serviceversion": version},
            accept="application/xml, application/vnd.sap.as+xml",
        )
        what = "publish" if action == "publishjobs" else "unpublish"
        if response.status_code != 200:
            raise error_from_response(response, f"Failed to {what} {name}")
        # SAP reports failures with status 200 and severity ERROR
        status = et.fromstring(response.text).find(".//DATA")
        if status is not None and status.findtext("SEVERITY", "") not in ("OK", "INFO", "WARNING", ""):
            message = "; ".join(
                text.strip()
                for text in (status.findtext("SHORT_TEXT", ""), status.findtext("LONG_TEXT", ""))
                if text and text.strip()
            )
            raise AdtError(
                f"{response.status_code} - Failed to {what} {name}: {message}",
                status_code=response.status_code,
                sap_message=message,
                response_text=response.text,
            )
    return binding


def publish_service_binding(
    http_request_parameters: HttpRequestParameters, name: str
) -> List[str]:
    """Publish an activated OData V2 or V4 service binding locally.

    Returns the service URLs, e.g. ["/sap/opu/odata4/sap/zui_travel/srvd/sap/ztravel/0001/"]
    """
    binding = _publish_job(http_request_parameters, name, "publishjobs")
    odata_path = _odata_path(binding)
    return [
        _service_url(
            http_request_parameters, odata_path, name, service, version, service_definition
        )
        for service, version, service_definition in _services(binding)
    ]


def unpublish_service_binding(
    http_request_parameters: HttpRequestParameters, name: str
) -> bool:
    _publish_job(http_request_parameters, name, "unpublishjobs")
    return True
