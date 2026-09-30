def test_message_class(client, uid, cleanup, runnable_class):
    name = f"ZADTPY_{uid}"
    uri = f"/sap/bc/adt/messageclass/{name.lower()}"

    client.create_message_class(
        name, "$TMP", "adt-py messages",
        messages=[{"number": "001", "text": "Bin &1 is blocked"}, {"number": "002", "text": "Temp"}],
    )
    cleanup(uri)
    client.set_messages(
        name,
        [{"number": "002", "text": "Quantity &1 is invalid"}, {"number": "003", "text": "Gone", "self_explanatory": False}],
    )
    assert client.get_messages(name)[2]["self_explanatory"] is False
    client.delete_messages(name, ["003"])

    assert [(m["number"], m["text"]) for m in client.get_messages(name)] == [
        ("001", "Bin &1 is blocked"),
        ("002", "Quantity &1 is invalid"),
    ]
    stored = client.run_query(f"SELECT msgnr, text FROM t100 WHERE arbgb = '{name}' AND sprsl = 'E'")
    assert len(stored["rows"]) == 2

    run = runnable_class(
        "MSG", f"    MESSAGE e001({name.lower()}) WITH 'BIN-A' INTO DATA(lv).\n    out->write( lv )."
    )
    assert client.run_class(run).strip() == "Bin BIN-A is blocked"
