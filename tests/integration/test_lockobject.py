from helpers import write_source

TABLE = """@EndUserText.label : 'adt-py lock object'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table {name} {{
{fields}
}}
"""
HEADER_FIELDS = """  key mandt : mandt not null;
  key id : abap.char(4) not null;
  val : abap.int4;"""
ITEM_FIELDS = """  key mandt : mandt not null
    with foreign key {header}
      where mandt = {name}.mandt
        and id = {name}.id;
  key id : abap.char(4) not null;
  key pos : abap.numc(3) not null;"""


def _tables(client, uid, cleanup):
    # table names have at most 16 characters
    header, item = f"ZADT{uid}H", f"ZADT{uid}I"
    for name, fields in ((header, HEADER_FIELDS), (item, ITEM_FIELDS.format(header=header.lower(), name=f"ZADT{uid}I".lower()))):
        uri = f"/sap/bc/adt/ddic/tables/{name.lower()}"
        cleanup(uri)
        client.create("TABL/DT", name, "$TMP", "adt-py lock object")
        write_source(client, uri, TABLE.format(name=name.lower(), fields=fields))
    client.activate_objects([(name, f"/sap/bc/adt/ddic/tables/{name.lower()}") for name in (header, item)])
    return header, item


def test_lock_object(client, uid, cleanup):
    header, item = _tables(client, uid, cleanup)
    name = f"EZADT{uid}"
    uri = f"/sap/bc/adt/ddic/lockobjects/sources/{name.lower()}"
    cleanup(uri)
    client.create_lock_object(name, "$TMP", "adt-py lock object", header)

    lock_object = client.get_lock_object(name)
    assert (lock_object["primary_table"], lock_object["lock_mode"], lock_object["version"]) == (header, "E", "active")
    # the key fields of the primary table
    assert [(p["name"], p["table"], p["field"]) for p in lock_object["parameters"]] == [
        ("MANDT", header, "MANDT"), ("ID", header, "ID")
    ]
    assert lock_object["lock_modules"] == [f"ENQUEUE_{name}", f"DEQUEUE_{name}"]
    generated = client.run_query(f"SELECT funcname FROM tfdir WHERE funcname = 'ENQUEUE_{name}'")
    assert generated["rows"] == [{"FUNCNAME": f"ENQUEUE_{name}"}]

    client.set_language_version(uri, "cloudDevelopment")
    assert client.get_language_version(uri)["version"] == "cloudDevelopment"


def test_lock_object_with_secondary_table(client, uid, cleanup):
    header, item = _tables(client, uid, cleanup)
    name = f"EZADT{uid}2"
    uri = f"/sap/bc/adt/ddic/lockobjects/sources/{name.lower()}"
    cleanup(uri)
    client.create_lock_object(
        name, "$TMP", "adt-py lock object", header, lock_mode="X",
        secondary_tables=[{"table": item, "lock_mode": "S"}],
        parameters=["MANDT", "ID", {"name": "POS", "table": item, "field": "POS"}],
        allow_rfc=True,
    )

    lock_object = client.get_lock_object(name)
    assert lock_object["lock_mode"] == "X"
    assert lock_object["secondary_tables"] == [{"table": item, "lock_mode": "S"}]
    assert [(p["name"], p["table"]) for p in lock_object["parameters"]] == [
        ("MANDT", header), ("ID", header), ("POS", item)
    ]
    assert lock_object["allow_rfc"] is True
