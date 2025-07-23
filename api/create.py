from typing import Dict, Literal, TypeAlias, TypedDict
from http_request import HttpRequestParameters, request


class CreateableTypeDetails(TypedDict):
    path: str
    xml_name: str
    xml_namespace: str


ObjectTypes: TypeAlias = Literal["PROG/P", "CLAS/OC"]
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
}


def _build_body(
    description: str, name: str, package: str, owner: str, object_type: ObjectTypes
) -> str:

    creatable_object = CREATEABLE_TYPES[object_type]

    return f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <{creatable_object["xml_name"]} {creatable_object["xml_namespace"]}
        xmlns:adtcore="http://www.sap.com/adt/core"
        adtcore:description="{description}"
        adtcore:name="{name}" adtcore:type="{object_type}"
        adtcore:responsible="{owner}" >
    <adtcore:packageRef adtcore:name="{package}"/>
    </{creatable_object["xml_name"]}>
    """


def create(
    http_request_parameters: HttpRequestParameters,
    object_type: ObjectTypes,
    name: str,
    package: str,
    description: str,
    owner: str,
) -> bool:

    body = _build_body(
        description=description,
        name=name,
        package=package,
        object_type=object_type,
        owner=owner,
    )

    response = request(
        http_request_parameters=http_request_parameters,
        uri=CREATEABLE_TYPES[object_type]["path"],
        method="POST",
        body=body,
        params={},
    )

    if response.status_code == 200:
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

    if response.status_code == 201:
        return True
    else:
        raise Exception(
            f"{response.status_code} - Failed to create testclass for {class_name}\n{response.text}"
        )
