import pytest

from abap_adt_py.exceptions import ActivationError
from helpers import write_source

TABLE = """@EndUserText.label : 'adt-py activation'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table {name} {{
  key client : abap.clnt not null;
  key id     : abap.numc(8) not null;
{fields}
}}"""


def create_table(client, cleanup, name, fields):
    uri = f"/sap/bc/adt/ddic/tables/{name.lower()}"
    client.create("TABL/DT", name, "$TMP", "adt-py activation")
    cleanup(uri)
    write_source(client, uri, TABLE.format(name=name.lower(), fields=fields))
    return uri


def test_table_that_stays_inactive_raises(client, uid, cleanup):
    """SAP reports activationExecuted="true" although the table stays inactive."""
    name = f"ZADTPY_{uid}_RW"
    uri = create_table(client, cleanup, name, "  hours : abap.dec(5,2);")

    with pytest.raises(ActivationError, match="HOURS is a reserved word"):
        client.activate(name, uri)
    assert name in [o["name"] for o in client.inactive_objects()]


def test_cds_view_that_stays_inactive_raises(client, uid, cleanup):
    table, view = f"ZADTPY_{uid}_GT", f"ZADTPY_{uid}_GV"
    table_uri = create_table(client, cleanup, table, "  work_date : abap.dats;\n  work_hours : abap.dec(5,2);")
    client.activate(table, table_uri)
    uri = f"/sap/bc/adt/ddic/ddl/sources/{view.lower()}"
    client.create("DDLS/DF", view, "$TMP", "adt-py activation")
    cleanup(uri)
    write_source(
        client,
        uri,
        f"""@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'adt-py activation'
define view entity {view} as select from {table.lower()}
{{
  key id,
  key left( work_date, 6 ) as month,
  sum( work_hours ) as total_hours
}}
group by id, left( work_date, 6 )""",
    )

    with pytest.raises(ActivationError, match="left"):
        client.activate(view, uri)


def test_activate_and_delete_objects_together(client, uid, cleanup):
    """A root view with a composition and its child can only be activated together."""
    head, item = f"ZADTPY_{uid}_H", f"ZADTPY_{uid}_I"
    root, child = f"ZADTPY_{uid}_RV", f"ZADTPY_{uid}_CV"
    tables = [
        (head, create_table(client, cleanup, head, "  text : abap.char(10);")),
        (item, create_table(client, cleanup, item, "  pos : abap.numc(4);")),
    ]
    assert client.activate_objects(tables)

    views = {name: f"/sap/bc/adt/ddic/ddl/sources/{name.lower()}" for name in (root, child)}
    for name, uri in views.items():
        client.create("DDLS/DF", name, "$TMP", "adt-py activation")
    try:
        write_source(
            client,
            views[root],
            f"""@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'adt-py root'
define root view entity {root} as select from {head.lower()}
  composition [0..*] of {child} as _Items
{{
  key id,
  _Items
}}""",
        )
        write_source(
            client,
            views[child],
            f"""@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'adt-py child'
define view entity {child} as select from {item.lower()}
  association to parent {root} as _Head on $projection.id = _Head.id
{{
  key id,
  pos,
  _Head
}}""",
        )
        with pytest.raises(ActivationError):
            client.activate(root, views[root])
        assert client.activate_objects(list(views.items()))
    finally:
        # they use each other, so they can only be deleted together
        client.delete_objects(list(views.values()))
