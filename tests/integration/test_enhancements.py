from helpers import write_source


def test_badi(client, uid, cleanup, runnable_class):
    interface, spot, badi = f"ZIF_ADTPY_{uid}", f"ZES_ADTPY_{uid}", f"ZBADI_ADTPY_{uid}"
    implementing_class, enhancement = f"ZCL_ADTPY_{uid}_BI", f"ZEI_ADTPY_{uid}"
    interface_uri = f"/sap/bc/adt/oo/interfaces/{interface.lower()}"
    class_uri = f"/sap/bc/adt/oo/classes/{implementing_class.lower()}"

    client.create("INTF/OI", interface, "$TMP", "adt-py badi")
    cleanup(interface_uri)
    write_source(
        client,
        interface_uri,
        f"""INTERFACE {interface.lower()} PUBLIC.
  INTERFACES if_badi_interface.
  METHODS check IMPORTING iv TYPE i CHANGING ct TYPE string_table.
ENDINTERFACE.""",
    )
    client.activate(interface, interface_uri)

    client.create_enhancement_spot(
        spot, "$TMP", "adt-py spot",
        [{"name": badi, "interface": interface, "single_use": False,
          "filters": [{"name": "PLANT", "type": "C", "data_element": "WERKS_D"}]}],
    )
    cleanup(f"/sap/bc/adt/enhancements/enhsxsb/{spot.lower()}")
    [definition] = client.get_enhancement_spot(spot)["badis"]
    assert definition["interface"] == interface
    assert definition["filters"][0]["data_element"] == "WERKS_D"

    client.create("CLAS/OC", implementing_class, "$TMP", "adt-py badi")
    cleanup(class_uri)
    write_source(
        client,
        class_uri,
        f"""CLASS {implementing_class.lower()} DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    INTERFACES if_badi_interface.
    INTERFACES {interface.lower()}.
ENDCLASS.
CLASS {implementing_class.lower()} IMPLEMENTATION.
  METHOD {interface.lower()}~check.
    APPEND |checked {{ iv }}| TO ct.
  ENDMETHOD.
ENDCLASS.""",
    )
    client.activate(implementing_class, class_uri)

    implementation = {"name": f"{badi}_I", "badi": badi, "implementing_class": implementing_class}
    client.create_enhancement_implementation(
        enhancement, "$TMP", "adt-py implementation", spot,
        [{**implementation, "filters": [{"filter": "PLANT", "value": "1000"}]}],
    )
    cleanup(f"/sap/bc/adt/enhancements/enhoxhb/{enhancement.lower()}")
    [read] = client.get_enhancement_implementation(enhancement)["implementations"]
    assert read["filters"] == [[{"filter": "PLANT", "comparator": "=", "value": "1000"}]]

    run = runnable_class(
        "BR",
        f"""    DATA lo TYPE REF TO {badi.lower()}.
    DATA lt TYPE string_table.
    DO 2 TIMES.
      DATA(plant) = COND werks_d( WHEN sy-index = 1 THEN '1000' ELSE '2000' ).
      CLEAR lt.
      GET BADI lo FILTERS plant = plant.
      CALL BADI lo->check EXPORTING iv = sy-index CHANGING ct = lt.
      out->write( |{{ plant }}: {{ lines( lt ) }}| ).
    ENDDO.""",
    )
    assert client.run_class(run).split() == ["1000:", "1", "2000:", "0"]

    client.update_enhancement_implementation(
        enhancement, [{**implementation, "filters": [{"filter": "PLANT", "low": "2000", "high": "2999"}]}]
    )
    assert client.run_class(run).split() == ["1000:", "0", "2000:", "1"]
