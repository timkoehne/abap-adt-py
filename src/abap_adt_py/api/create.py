from ..compat_typing import Literal, TypeAlias, Dict, TypedDict
from ..http_request import HttpRequestParameters, request


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
}


def _build_body(
    description: str, name: str, package: str, owner: str, object_type: ObjectTypes
) -> str:

    if object_type in ["FUGR/FF"]:
        parent_ref = f"""
        <adtcore:containerRef adtcore:name="{owner}" 
            adtcore:type="FUGR/F"
            adtcore:uri="{package}" />"""
    else:
        parent_ref = f"""
        <adtcore:packageRef adtcore:name="{package}"/>
        """

    creatable_object = CREATEABLE_TYPES[object_type]

    return f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <{creatable_object["xml_name"]} {creatable_object["xml_namespace"]}
        xmlns:adtcore="http://www.sap.com/adt/core"
        adtcore:description="{description}"
        adtcore:name="{name}" adtcore:type="{object_type}"
        adtcore:responsible="{owner}" >
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
        params={},
        content_type="application/*",
    )

    if 200 <= response.status_code <= 300:
        return True
    else:
        raise Exception(
            f"{response.status_code} - Failed to create object {name}\n{response.text}"
        )


def create_test_class_include(
    http_request_parameters: HttpRequestParameters, class_name: str, lock_handle: str
) -> bool:

    body = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <class:abapClassInclude xmlns:class="http://www.sap.com/adt/oo/classes"
            xmlns:adtcore="http://www.sap.com/adt/core" adtcore:name="{class_name}" class:includeType="testclasses"/>
        """

    response = request(
        http_request_parameters=http_request_parameters,
        uri=f"/sap/bc/adt/oo/classes/{class_name}/includes",
        method="POST",
        body=body,
        params={"lockHandle": lock_handle},
    )

    if 200 <= response.status_code <= 300:
        return True
    else:
        raise Exception(
            f"{response.status_code} - Failed to create testclass for {class_name}\n{response.text}"
        )
