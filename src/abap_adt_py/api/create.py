from xml.sax.saxutils import escape, quoteattr

from ..compat_typing import Literal, TypeAlias, Dict, TypedDict, Optional
from ..http_request import HttpRequestParameters, request, with_transport
from ..exceptions import error_from_response
from .lock import lock, unlock


class CreateableTypeDetails(TypedDict):
    path: str
    xml_name: str
    xml_namespace: str


ObjectTypes: TypeAlias = Literal[
    "PROG/P",
    "CLAS/OC",
    "TABL/DT",
    "INTF/OI",
    "PROG/I",
    "FUGR/F",
    "FUGR/FF",
    "MSAG/N",
    "DCLS/DL",
    "DDLS/DF",
    "DDLX/EX",
    "DTEL/DE",
    "TABL/DS",
    "SRVD/SRV",
    "BDEF/BDO",
]

CreateableTypes: TypeAlias = Dict[ObjectTypes, CreateableTypeDetails]
CREATEABLE_TYPES: CreateableTypes = {
    "PROG/P": {
        "path": "/sap/bc/adt/programs/programs",
        "xml_name": "program:abapProgram",
        "xml_namespace": 'xmlns:program="http://www.sap.com/adt/programs/programs"',
    },
    "CLAS/OC": {
        "path": "/sap/bc/adt/oo/classes",
        "xml_name": "class:abapClass",
        "xml_namespace": 'xmlns:class="http://www.sap.com/adt/oo/classes"',
    },
    "TABL/DT": {
        "path": "/sap/bc/adt/ddic/tables",
        "xml_name": "blue:blueSource",
        "xml_namespace": 'xmlns:blue="http://www.sap.com/wbobj/blue"',
    },
    "INTF/OI": {
        "path": "/sap/bc/adt/oo/interfaces",
        "xml_name": "intf:abapInterface",
        "xml_namespace": 'xmlns:intf="http://www.sap.com/adt/oo/interfaces"',
    },
    "PROG/I": {
        "path": "/sap/bc/adt/programs/includes",
        "xml_name": "include:abapInclude",
        "xml_namespace": 'xmlns:include="http://www.sap.com/adt/programs/includes"',
    },
    "FUGR/F": {
        "path": "/sap/bc/adt/functions/groups",
        "xml_name": "group:abapFunctionGroup",
        "xml_namespace": 'xmlns:group="http://www.sap.com/adt/functions/groups"',
    },
    "FUGR/FF": {
        "path": "/sap/bc/adt/functions/groups/{}/fmodules",
        "xml_name": "fmodule:abapFunctionModule",
        "xml_namespace": 'xmlns:fmodule="http://www.sap.com/adt/functions/fmodules"',
    },
    "MSAG/N": {
        "path": "/sap/bc/adt/messageclass",
        "xml_name": "mc:messageClass",
        "xml_namespace": 'xmlns:mc="http://www.sap.com/adt/MessageClass"',
    },
    "DCLS/DL": {
        "path": "/sap/bc/adt/acm/dcl/sources",
        "xml_name": "dcl:dclSource",
        "xml_namespace": 'xmlns:dcl="http://www.sap.com/adt/acm/dclsources"',
    },
    "DDLS/DF": {
        "path": "/sap/bc/adt/ddic/ddl/sources",
        "xml_name": "ddl:ddlSource",
        "xml_namespace": 'xmlns:ddl="http://www.sap.com/adt/ddic/ddlsources"',
    },
    "DDLX/EX": {
        "path": "/sap/bc/adt/ddic/ddlx/sources",
        "xml_name": "ddlx:ddlxSource",
        "xml_namespace": 'xmlns:ddlx="http://www.sap.com/adt/ddic/ddlxsources"',
    },
    "DTEL/DE": {
        "path": "/sap/bc/adt/ddic/dataelements",
        "xml_name": "blue:wbobj",
        "xml_namespace": 'xmlns:blue="http://www.sap.com/wbobj/dictionary/dtel"',
    },
    "TABL/DS": {
        "path": "/sap/bc/adt/ddic/structures",
        "xml_name": "blue:blueSource",
        "xml_namespace": 'xmlns:blue="http://www.sap.com/wbobj/blue"',
    },
    "SRVD/SRV": {
        "path": "/sap/bc/adt/ddic/srvd/sources",
        "xml_name": "srvd:srvdSource",
        "xml_namespace": 'xmlns:srvd="http://www.sap.com/adt/ddic/srvdsources" srvd:srvdSourceType="S"',
    },
    # the name must be the name of the root CDS entity the behavior is defined for
    "BDEF/BDO": {
        "path": "/sap/bc/adt/bo/behaviordefinitions",
        "xml_name": "blue:blueSource",
        "xml_namespace": 'xmlns:blue="http://www.sap.com/wbobj/blue"',
    },
}


def _build_body(
    description: str, name: str, package: str, owner: str, object_type: ObjectTypes
) -> str:

    if object_type in ["FUGR/FF"]:
        parent_ref = f"""
        <adtcore:containerRef adtcore:name={quoteattr(owner)} 
            adtcore:type="FUGR/F"
            adtcore:uri={quoteattr(package)} />"""
    else:
        parent_ref = f"""
        <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        """

    creatable_object = CREATEABLE_TYPES[object_type]

    return f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <{creatable_object["xml_name"]} {creatable_object["xml_namespace"]}
        xmlns:adtcore="http://www.sap.com/adt/core"
        adtcore:description={quoteattr(description)}
        adtcore:name={quoteattr(name)} adtcore:type={quoteattr(object_type)}
        adtcore:responsible={quoteattr(owner)} >
    {parent_ref}
    </{creatable_object["xml_name"]}>
    """


def create(
    http_request_parameters: HttpRequestParameters,
    object_type: ObjectTypes,
    name: str,
    parent: str,
    description: str,
    owner: str,
    transport: Optional[str] = None,
) -> bool:

    object_uri = CREATEABLE_TYPES[object_type]["path"]

    # noop for most objects but eg. function modules need their function group in their object uri
    object_uri = object_uri.format(parent)

    body = _build_body(
        description=description,
        name=name,
        package=parent,
        object_type=object_type,
        owner=owner,
    )

    response = request(
        http_request_parameters=http_request_parameters,
        uri=object_uri,
        method="POST",
        body=body,
        params=with_transport({}, transport),
        content_type="application/*",
    )

    if 200 <= response.status_code <= 300:
        return True
    else:
        raise error_from_response(response, f"Failed to create object {name}")


def create_test_class_include(
    http_request_parameters: HttpRequestParameters,
    class_name: str,
    lock_handle: str,
    transport: Optional[str] = None,
) -> bool:

    body = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <class:abapClassInclude xmlns:class="http://www.sap.com/adt/oo/classes"
            xmlns:adtcore="http://www.sap.com/adt/core" adtcore:name={quoteattr(class_name)} class:includeType="testclasses"/>
        """

    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/oo/classes/{class_name}/includes",
        method="POST",
        body=body,
        params=with_transport({"lockHandle": lock_handle}, transport),
    )

    if 200 <= response.status_code <= 300:
        return True
    else:
        raise error_from_response(
            response, f"Failed to create testclass for {class_name}"
        )


PackageTypes: TypeAlias = Literal["development", "structure", "main"]


def create_package(
    http_request_parameters: HttpRequestParameters,
    name: str,
    description: str,
    owner: str,
    parent: str = "",
    package_type: PackageTypes = "development",
    software_component: Optional[str] = None,
    transport_layer: str = "",
    transport: Optional[str] = None,
) -> bool:

    if software_component is None:
        software_component = "LOCAL" if name.startswith("$") else "HOME"
    record_changes = "false" if software_component == "LOCAL" else "true"

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <pak:package xmlns:pak="http://www.sap.com/adt/packages"
        xmlns:adtcore="http://www.sap.com/adt/core"
        adtcore:description={quoteattr(description)}
        adtcore:name={quoteattr(name)} adtcore:type="DEVC/K"
        adtcore:version="active" adtcore:responsible={quoteattr(owner)}>
        <adtcore:packageRef adtcore:name={quoteattr(name)}/>
        <pak:attributes pak:packageType={quoteattr(package_type)}
            pak:recordChanges="{record_changes}"/>
        <pak:superPackage adtcore:name={quoteattr(parent)}/>
        <pak:applicationComponent/>
        <pak:transport>
            <pak:softwareComponent pak:name={quoteattr(software_component)}/>
            <pak:transportLayer pak:name={quoteattr(transport_layer)}/>
        </pak:transport>
        <pak:translation/>
        <pak:useAccesses/>
        <pak:packageInterfaces/>
        <pak:subPackages/>
    </pak:package>"""

    response = request(
        http_request_parameters=http_request_parameters,
        uri="/sap/bc/adt/packages",
        method="POST",
        body=body,
        params=with_transport({}, transport),
        content_type="application/*",
    )

    if 200 <= response.status_code < 300:
        return True
    else:
        raise error_from_response(response, f"Failed to create package {name}")


def _post_object(
    http_request_parameters: HttpRequestParameters,
    path: str,
    body: str,
    content_type: str,
    name: str,
    transport: Optional[str],
) -> bool:
    response = request(
        http_request_parameters=http_request_parameters,
        uri=path,
        method="POST",
        body=body,
        params=with_transport({}, transport),
        content_type=content_type,
    )
    if 200 <= response.status_code < 300:
        return True
    raise error_from_response(response, f"Failed to create {name}")


def _header(
    name: str, description: str, owner: str, object_type: str, language: str
) -> str:
    # without the language SAP silently drops the description
    return (
        f'xmlns:adtcore="http://www.sap.com/adt/core" adtcore:name={quoteattr(name)} '
        f"adtcore:description={quoteattr(description)} "
        f'adtcore:type="{object_type}" adtcore:responsible={quoteattr(owner)} '
        f"adtcore:language={quoteattr(language.upper())} "
        f"adtcore:masterLanguage={quoteattr(language.upper())}"
    )


def create_domain(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    data_type: str,
    length: int,
    decimals: int = 0,
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    """Create a domain with a built-in data type, e.g. data_type="CHAR", length=10."""

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <doma:domain xmlns:doma="http://www.sap.com/dictionary/domain" {_header(name, description, owner, "DOMA/DD", language)}>
        <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        <doma:content>
            <doma:typeInformation>
                <doma:datatype>{escape(data_type.upper())}</doma:datatype>
                <doma:length>{int(length):06d}</doma:length>
                <doma:decimals>{int(decimals):06d}</doma:decimals>
            </doma:typeInformation>
            <doma:outputInformation>
                <doma:length>{int(length):06d}</doma:length>
                <doma:style>00</doma:style>
                <doma:conversionExit/>
                <doma:signExists>false</doma:signExists>
                <doma:lowercase>false</doma:lowercase>
                <doma:ampmFormat>false</doma:ampmFormat>
            </doma:outputInformation>
            <doma:valueInformation>
                <doma:valueTableRef/>
                <doma:appendExists>false</doma:appendExists>
                <doma:fixValues/>
            </doma:valueInformation>
        </doma:content>
    </doma:domain>"""

    return _post_object(
        http_request_parameters,
        "/sap/bc/adt/ddic/domains",
        body,
        "application/vnd.sap.adt.domains.v2+xml",
        name,
        transport,
    )


def create_table_type(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    row_type: Optional[str] = None,
    data_type: Optional[str] = None,
    length: int = 0,
    decimals: int = 0,
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    """Create a standard table type.

    The rows are either a dictionary type (row_type, e.g. a structure or data element)
    or a built-in type (data_type and length, e.g. "CHAR", 20).
    """

    if (row_type is None) == (data_type is None):
        raise ValueError("pass either row_type or data_type")

    header = _header(name, description, owner, "TTYP/DA", language)
    package_ref = f"<adtcore:packageRef adtcore:name={quoteattr(package)}/>"
    namespace = 'xmlns:ttyp="http://www.sap.com/dictionary/tabletype"'
    content_type = "application/vnd.sap.adt.tabletype.v1+xml"

    # SAP ignores the row type (and the description) when creating a table type,
    # so it is created first and its definition saved afterwards, like in the editor
    _post_object(
        http_request_parameters,
        "/sap/bc/adt/ddic/tabletypes",
        f"""<?xml version="1.0" encoding="UTF-8"?>
        <ttyp:tableType {namespace} {header}>{package_ref}</ttyp:tableType>""",
        content_type,
        name,
        transport,
    )

    kind = "dictionaryType" if row_type else "predefinedAbapType"
    # SAP expects every element, also the built-in type for dictionary types
    definition = f"""<?xml version="1.0" encoding="UTF-8"?>
    <ttyp:tableType {namespace} {header}>
        {package_ref}
        <ttyp:rowType>
            <ttyp:typeKind>{kind}</ttyp:typeKind>
            <ttyp:typeName>{escape((row_type or "").upper())}</ttyp:typeName>
            <ttyp:builtInType>
                <ttyp:dataType>{escape((data_type or "").upper())}</ttyp:dataType>
                <ttyp:length>{int(length):06d}</ttyp:length>
                <ttyp:decimals>{int(decimals):06d}</ttyp:decimals>
            </ttyp:builtInType>
            <ttyp:rangeType/>
        </ttyp:rowType>
        <ttyp:initialRowCount>00000</ttyp:initialRowCount>
        <ttyp:accessType>standard</ttyp:accessType>
        <ttyp:primaryKey>
            <ttyp:definition>standard</ttyp:definition>
            <ttyp:kind>nonUnique</ttyp:kind>
            <ttyp:components/>
            <ttyp:alias/>
        </ttyp:primaryKey>
        <ttyp:secondaryKeys>
            <ttyp:allowed>notSpecified</ttyp:allowed>
        </ttyp:secondaryKeys>
    </ttyp:tableType>"""

    uri = f"/sap/bc/adt/ddic/tabletypes/{name.lower()}"
    # the lock needs a stateful session, which must not be replaced by a reconnect
    stateful: HttpRequestParameters = {
        **http_request_parameters,
        "statefulness": "stateful",
        "refresh_csrf_token": None,
    }
    lock_handle = lock(stateful, uri)
    try:
        response = request(
            http_request_parameters=stateful,
            uri=uri,
            method="PUT",
            body=definition,
            params=with_transport({"lockHandle": lock_handle}, transport),
            content_type=content_type,
        )
        if response.status_code != 200:
            raise error_from_response(response, f"Failed to save table type {name}")
    finally:
        unlock(stateful, uri, lock_handle)
    return True


ServiceBindingCategories: TypeAlias = Literal["ui", "web_api"]


def create_service_binding(
    http_request_parameters: HttpRequestParameters,
    name: str,
    package: str,
    description: str,
    owner: str,
    service_definition: str,
    binding_type: str = "ODATA",
    version: str = "V4",
    category: ServiceBindingCategories = "ui",
    language: str = "EN",
    transport: Optional[str] = None,
) -> bool:
    """Create a service binding, e.g. an OData V4 UI service for a service definition.

    The binding still has to be activated and published to be reachable.
    """

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <srvb:serviceBinding xmlns:srvb="http://www.sap.com/adt/ddic/ServiceBindings" {_header(name, description, owner, "SRVB/SVB", language)}>
        <adtcore:packageRef adtcore:name={quoteattr(package)}/>
        <srvb:services srvb:name={quoteattr(name)}>
            <srvb:content srvb:version="0001">
                <srvb:serviceDefinition adtcore:name={quoteattr(service_definition.upper())}/>
            </srvb:content>
        </srvb:services>
        <srvb:binding srvb:type={quoteattr(binding_type.upper())} srvb:version={quoteattr(version.upper())}
            srvb:category="{"1" if category == "web_api" else "0"}">
            <srvb:implementation adtcore:name=""/>
        </srvb:binding>
    </srvb:serviceBinding>"""

    return _post_object(
        http_request_parameters,
        "/sap/bc/adt/businessservices/bindings",
        body,
        "application/vnd.sap.adt.businessservices.servicebinding.v2+xml",
        name,
        transport,
    )
