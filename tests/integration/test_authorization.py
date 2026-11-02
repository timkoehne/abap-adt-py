import pytest

from abap_adt_py.exceptions import ActivationError, AdtError
from helpers import write_source


def test_authorization_object(client, uid, cleanup):
    # authorization objects have at most 10 characters
    name = f"ZA{uid}"
    uri = f"/sap/bc/adt/aps/iam/suso/{name.lower()}"

    client.create_authorization_object(
        name, "$TMP", "adt-py authorization", "AAAB", ["KOSTL", "ACTVT"], ["03"]
    )
    cleanup(uri)
    client.update_authorization_object(name, activities=["02", "03"])

    assert client.get_authorization_object(name) == {
        "name": name,
        "description": "adt-py authorization",
        "package": "$TMP",
        "object_class": "AAAB",
        "fields": ["KOSTL", "ACTVT"],
        "activities": ["02", "03"],
    }
    stored = client.run_query(f"SELECT fiel1, fiel2 FROM tobj WHERE objct = '{name}'")
    assert stored["rows"] == [{"FIEL1": "KOSTL", "FIEL2": "ACTVT"}]

    # a CDS access control can use it
    table, view = f"ZADTPY_{uid}_AT", f"ZADTPY_{uid}_AV"
    table_uri = f"/sap/bc/adt/ddic/tables/{table.lower()}"
    view_uri = f"/sap/bc/adt/ddic/ddl/sources/{view.lower()}"
    role_uri = f"/sap/bc/adt/acm/dcl/sources/{view.lower()}"
    client.create("TABL/DT", table, "$TMP", "adt-py authorization")
    cleanup(table_uri)
    write_source(
        client,
        table_uri,
        f"""@EndUserText.label : 'adt-py authorization'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table {table.lower()} {{
  key client : abap.clnt not null;
  key id     : abap.numc(8) not null;
  kostl      : kostl;
}}""",
    )
    client.activate(table, table_uri)
    client.create("DDLS/DF", view, "$TMP", "adt-py authorization")
    cleanup(view_uri)
    write_source(
        client,
        view_uri,
        f"""@AccessControl.authorizationCheck: #CHECK
@EndUserText.label: 'adt-py authorization'
define view entity {view} as select from {table.lower()} {{ key id, kostl }}""",
    )
    client.activate(view, view_uri)
    client.create("DCLS/DL", view, "$TMP", "adt-py authorization")
    cleanup(role_uri)
    def role(authorization_object):
        return f"""@EndUserText.label: 'adt-py authorization'
@MappingRole: true
define role {view} {{
  grant select on {view}
    where ( kostl ) = aspect pfcg_auth( {authorization_object}, KOSTL, ACTVT = '03' );
}}"""

    write_source(client, role_uri, role(name))
    assert client.activate(view, role_uri)

    write_source(client, role_uri, role("ZADTPY_NO"))
    with pytest.raises(ActivationError, match="ZADTPY_NO does not exist"):
        client.activate(view, role_uri)


def test_authorization_field(client, uid, cleanup):
    # authorization fields have at most 10 characters
    field, authorization_object = f"ZF{uid}", f"ZB{uid}"
    field_uri = f"/sap/bc/adt/aps/iam/auth/{field.lower()}"

    client.create_authorization_field(field, "$TMP", "S_CARR_ID", "SCARR")
    cleanup(field_uri)
    assert client.get_authorization_field(field) == {
        "name": field,
        "description": "Airline Code",
        "package": "$TMP",
        "data_element": "S_CARR_ID",
        "check_table": "SCARR",
    }

    with pytest.raises(AdtError, match="Check table ZADTPY_NO does not actively exist"):
        client.update_authorization_field(field, check_table="ZADTPY_NO")
    client.update_authorization_field(field, check_table="")
    assert client.get_authorization_field(field)["check_table"] == ""

    # a failed create leaves nothing behind
    with pytest.raises(AdtError, match="Data element ZADTPY_NO does not exist"):
        client.create_authorization_field(f"ZG{uid}", "$TMP", "ZADTPY_NO")
    assert client.run_query(f"SELECT fieldname FROM authx WHERE fieldname = 'ZG{uid}'")["rows"] == []

    client.create_authorization_object(
        authorization_object, "$TMP", "adt-py authorization", "AAAB", [field, "ACTVT"], ["03"]
    )
    cleanup(f"/sap/bc/adt/aps/iam/suso/{authorization_object.lower()}")
    assert client.get_authorization_object(authorization_object)["fields"] == [field, "ACTVT"]
    with pytest.raises(AdtError, match="still being used"):
        client.delete_objects([field_uri])
