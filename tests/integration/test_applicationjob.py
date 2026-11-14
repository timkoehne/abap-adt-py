from helpers import write_source

JOB_CLASS = """CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    INTERFACES if_apj_dt_exec_object.
    INTERFACES if_apj_rt_exec_object.
ENDCLASS.

CLASS {name} IMPLEMENTATION.
  METHOD if_apj_dt_exec_object~get_parameters.
    et_parameter_def = VALUE #(
      ( selname = 'P_ID' kind = 'P' datatype = 'C' length = 4 param_text = 'Id' changeable_ind = abap_true )
      ( selname = 'S_DATE' kind = 'S' datatype = 'D' length = 8 param_text = 'Date' changeable_ind = abap_true ) ).
  ENDMETHOD.
  METHOD if_apj_rt_exec_object~execute.
  ENDMETHOD.
ENDCLASS."""


def test_job_catalog_entry_and_template(client, uid, cleanup):
    class_name, catalog, template = f"ZCL_ADTPY_{uid}_JOB", f"ZADTPY_{uid}_JC", f"ZADTPY_{uid}_JT"
    class_uri = f"/sap/bc/adt/oo/classes/{class_name.lower()}"
    cleanup(class_uri)
    client.create("CLAS/OC", class_name, "$TMP", "adt-py job class")
    write_source(client, class_uri, JOB_CLASS.format(name=class_name.lower()))
    client.activate(class_name, class_uri)

    catalog_uri = f"/sap/bc/adt/applicationjob/catalogs/{catalog.lower()}"
    cleanup(catalog_uri)
    client.create_job_catalog_entry(
        catalog, "$TMP", "adt-py catalog entry", class_name,
        parameters=[{"name": "P_ID", "mandatory": True}],
    )
    entry = client.get_job_catalog_entry(catalog)
    assert (entry["class_name"], entry["description"]) == (class_name, "adt-py catalog entry")
    parameters = {p["name"]: p for p in entry["parameters"]}
    # SAP adds the parameter that was left out
    assert set(parameters) == {"P_ID", "S_DATE"}
    assert parameters["P_ID"] == {"name": "P_ID", "mandatory": True}

    template_uri = f"/sap/bc/adt/applicationjob/templates/{template.lower()}"
    cleanup(template_uri)
    client.create_job_template(
        template, "$TMP", "adt-py template", catalog,
        parameters={"P_ID": "A1", "S_DATE": [{"sign": "I", "option": "BT", "low": "20250101", "high": "20251231"}]},
    )
    stored = client.get_job_template(template)
    assert stored["catalog_entry"] == catalog
    assert stored["parameters"]["P_ID"] == "A1"
    assert stored["parameters"]["S_DATE"] == [
        {"sign": "include", "option": "between", "low": "20250101", "high": "20251231"}
    ]

    for uri in (catalog_uri, template_uri):
        client.set_language_version(uri, "cloudDevelopment")
        assert client.get_language_version(uri)["version"] == "cloudDevelopment"


def test_application_log_object(client, uid, cleanup):
    name = f"ZADTPY_{uid}_LOG"
    uri = f"/sap/bc/adt/applicationlog/objects/{name.lower()}"
    cleanup(uri)
    client.create_application_log_object(
        name, "$TMP", "adt-py log", [{"name": "run", "description": "Runs"}, {"name": "CHECK", "description": "Checks"}]
    )
    assert client.get_application_log_object(name) == {
        "name": name,
        "description": "adt-py log",
        # sorted by SAP
        "subobjects": [{"name": "CHECK", "description": "Checks"}, {"name": "RUN", "description": "Runs"}],
    }
    stored = client.run_query(f"SELECT subobject FROM balsub WHERE object = '{name}' ORDER BY subobject")
    assert stored["rows"] == [{"SUBOBJECT": "CHECK"}, {"SUBOBJECT": "RUN"}]
