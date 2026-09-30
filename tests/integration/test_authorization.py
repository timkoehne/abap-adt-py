import pytest

from abap_adt_py.exceptions import ActivationError
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
