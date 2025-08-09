from abap_adt_py.adt_client import AdtClient
from abap_adt_py.api.prettyprint import PrettyPrintSettings


if __name__ == "__main__":

    # test report
    report_name = "z_test"
    report_uri = "/sap/bc/adt/programs/programs/z_test"

    # establish connection to SAP system
    client = AdtClient(
        sap_host="http://localhost:50000",
        username="DEVELOPER",
        password="ABAPtr2022#01",
        client="001",
        language="EN",
    )

    # login
    client.login()
    
    # search
    results: list = client.search_object(report_name, 50)
    print(results)

    # create report object
    client.create(
        object_type="PROG/P",
        name=report_name,
        description="Test Program",
        parent="$TMP",
    )

    # read source code
    src: str = client.get_object_source(f"{report_uri}/source/main")
    print(src)

    # configure pretty printing
    pretty_print_settings: PrettyPrintSettings = {"indentation": True, "style": "keywordUpper"}
    client.prettyprint_settings(pretty_print_settings)
    
    # pretty print source code
    src: str = f"Report {report_name}. Write 'test'."
    pretty_src = client.prettyprint(src)

    # write source code
    lock_handle: str = client.lock(report_uri)
    client.set_object_source(f"{report_uri}/source/main", pretty_src, lock_handle)
    client.unlock(report_uri, lock_handle)

    # activate object
    client.activate(report_name, report_uri)

    # delete object
    lock_handle: str = client.lock(report_uri)
    client.delete(report_uri, lock_handle)
    client.unlock(report_uri, lock_handle)
