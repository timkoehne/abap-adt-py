from helpers import write_source


def test_domain(client, uid, cleanup):
    name = f"ZADTPY_{uid}_DOMA"
    uri = f"/sap/bc/adt/ddic/domains/{name.lower()}"

    assert client.create_domain(name, "$TMP", "adt-py domain", data_type="char", length=10)
    cleanup(uri)

    stored = client.run_query(
        f"SELECT datatype, leng FROM dd01l WHERE domname = '{name}' AND as4local = 'A'"
    )
    assert stored["rows"] == [{"DATATYPE": "CHAR", "LENG": "000010"}]
    text = client.run_query(f"SELECT ddtext FROM dd01t WHERE domname = '{name}'")
    assert text["rows"] == [{"DDTEXT": "adt-py domain"}]


def test_domain_with_fixed_values(client, uid, cleanup):
    name = f"ZADTPY_{uid}_STAT"
    uri = f"/sap/bc/adt/ddic/domains/{name.lower()}"

    client.create_domain(
        name, "$TMP", "adt-py status", "CHAR", 1,
        fixed_values=[{"low": "N", "text": "New"}, {"low": "R", "text": "Released"}],
    )
    cleanup(uri)
    client.update_domain(
        name,
        lowercase=True,
        fixed_values=[{"low": "N", "text": "New"}, {"low": "C", "text": "Completed"}],
    )

    domain = client.get_domain(name)
    assert domain["lowercase"] is True
    assert domain["fixed_values"] == [
        {"low": "N", "high": "", "text": "New"},
        {"low": "C", "high": "", "text": "Completed"},
    ]
    values = client.run_query(
        f"SELECT domvalue_l FROM dd07l WHERE domname = '{name}' AND as4local = 'A' ORDER BY valpos"
    )
    assert values["rows"] == [{"DOMVALUE_L": "N"}, {"DOMVALUE_L": "C"}]


def test_data_element(client, uid, cleanup):
    domain, name = f"ZADTPY_{uid}_DDOM", f"ZADTPY_{uid}_DTEL"
    client.create_domain(domain, "$TMP", "adt-py domain", "NUMC", 4)
    cleanup(f"/sap/bc/adt/ddic/domains/{domain.lower()}")

    client.create_data_element(
        name, "$TMP", "adt-py data element", domain=domain,
        labels={"short": "Short", "medium": "Medium", "long": "Long label", "heading": "Head"},
    )
    cleanup(f"/sap/bc/adt/ddic/dataelements/{name.lower()}")
    client.update_data_element(name, labels={"short": "Changed"})

    data_element = client.get_data_element(name)
    assert (data_element["type_kind"], data_element["type_name"]) == ("domain", domain)
    assert data_element["labels"] == {
        "short": "Changed", "medium": "Medium", "long": "Long label", "heading": "Head"
    }
    stored = client.run_query(
        f"SELECT domname, as4local FROM dd04l WHERE rollname = '{name}'"
    )
    assert stored["rows"] == [{"DOMNAME": domain, "AS4LOCAL": "A"}]

    client.update_data_element(name, reference_to="STRING", reference_kind="built_in")
    assert client.get_data_element(name)["type_kind"] == "refToPredefinedAbapType"


def test_table_type_of_dictionary_type(client, uid, cleanup):
    name = f"ZADTPY_{uid}_TTYP"
    uri = f"/sap/bc/adt/ddic/tabletypes/{name.lower()}"

    assert client.create_table_type(name, "$TMP", "adt-py table type", row_type="scarr")
    cleanup(uri)
    # SAP leaves a saved table type inactive, so it is activated
    active = client.run_query(f"SELECT as4local FROM dd40l WHERE typename = '{name}'")
    assert active["rows"] == [{"AS4LOCAL": "A"}]

    stored = client.run_query(f"SELECT rowtype FROM dd40l WHERE typename = '{name}'")
    assert stored["rows"] == [{"ROWTYPE": "SCARR"}]
    # SAP ignores the description on creation, so it is saved along with the row type
    text = client.run_query(f"SELECT ddtext FROM dd40t WHERE typename = '{name}'")
    assert text["rows"] == [{"DDTEXT": "adt-py table type"}]


def test_table_type_of_built_in_type(client, uid, cleanup):
    name = f"ZADTPY_{uid}_TTYC"
    uri = f"/sap/bc/adt/ddic/tabletypes/{name.lower()}"

    assert client.create_table_type(name, "$TMP", "adt-py table type", data_type="CHAR", length=20)
    cleanup(uri)

    stored = client.run_query(f"SELECT datatype, leng FROM dd40l WHERE typename = '{name}'")
    assert stored["rows"] == [{"DATATYPE": "CHAR", "LENG": "000020"}]


def test_structure(client, uid, cleanup):
    name = f"ZADTPY_{uid}_STRU"
    uri = f"/sap/bc/adt/ddic/structures/{name.lower()}"

    assert client.create("TABL/DS", name, "$TMP", "adt-py structure")
    cleanup(uri)
    write_source(
        client,
        uri,
        f"""@EndUserText.label : 'adt-py structure'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
define structure {name.lower()} {{
  id          : abap.numc(8);
  description : abap.char(40);
}}""",
    )
    assert client.activate(name, uri)


def test_rap_business_object_and_service(client, uid, cleanup):
    """table -> root view entity -> behavior definition -> service definition -> binding"""
    table, view = f"ZADTPY_{uid}_T", f"ZADTPY_{uid}_R"
    service, binding = f"ZADTPY_{uid}_SD", f"ZADTPY_{uid}_SB"
    uris = {
        "table": f"/sap/bc/adt/ddic/tables/{table.lower()}",
        "view": f"/sap/bc/adt/ddic/ddl/sources/{view.lower()}",
        "behavior": f"/sap/bc/adt/bo/behaviordefinitions/{view.lower()}",
        "service": f"/sap/bc/adt/ddic/srvd/sources/{service.lower()}",
        "binding": f"/sap/bc/adt/businessservices/bindings/{binding.lower()}",
    }

    client.create("TABL/DT", table, "$TMP", "adt-py rap table")
    cleanup(uris["table"])
    write_source(
        client,
        uris["table"],
        f"""@EndUserText.label : 'adt-py rap table'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table {table.lower()} {{
  key client  : abap.clnt not null;
  key id      : abap.numc(8) not null;
  description : abap.char(40);
}}""",
    )
    assert client.activate(table, uris["table"])

    client.create("DDLS/DF", view, "$TMP", "adt-py rap view")
    cleanup(uris["view"])
    write_source(
        client,
        uris["view"],
        f"""@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'adt-py rap view'
define root view entity {view} as select from {table.lower()}
{{
  key id,
  description
}}""",
    )
    assert client.activate(view, uris["view"])

    # a behavior definition is named after its root entity
    assert client.create("BDEF/BDO", view, "$TMP", "adt-py rap behavior")
    cleanup(uris["behavior"])
    write_source(
        client,
        uris["behavior"],
        f"""managed;
define behavior for {view}
persistent table {table.lower()}
lock master
{{
  create;
  update;
  delete;
}}""",
    )
    assert client.activate(view, uris["behavior"])

    assert client.create("SRVD/SRV", service, "$TMP", "adt-py rap service")
    cleanup(uris["service"])
    write_source(
        client,
        uris["service"],
        f"""@EndUserText.label: 'adt-py rap service'
define service {service} {{
  expose {view};
}}""",
    )
    assert client.activate(service, uris["service"])

    assert client.create_service_binding(
        binding, "$TMP", "adt-py rap binding", service_definition=service
    )
    cleanup(uris["binding"])
    assert client.activate(binding, uris["binding"])

    [found] = client.search_object(binding, 1)
    assert found["type"] == "SRVB/SVB"
    assert found["description"] == "adt-py rap binding"

    [url] = client.publish_service_binding(binding)
    try:
        assert client.get_service_binding(binding)["published"] is True
        metadata = client.session.get(f"{client.sap_host}{url}$metadata")
        assert metadata.status_code == 200
    finally:
        client.unpublish_service_binding(binding)
    assert client.get_service_binding(binding)["published"] is False
