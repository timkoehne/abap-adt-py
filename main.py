from adt_client import AdtClient


if __name__ == "__main__":
    SAP_HOST = "localhost:50000"
    CLIENT = "001"
    USERNAME = "DEVELOPER"
    PASSWORD = "ABAPtr2022#01"
    client = AdtClient(
        sap_host=SAP_HOST,
        username=USERNAME,
        password=PASSWORD,
        client=CLIENT,
        language="EN",
    )

    # response = client.login()
    response = client.search_object("Z_HUMANEVAL_088")
    print(response.text)
    response = client.get_object_source("/sap/bc/adt/oo/classes/z_humaneval_088")
    print(response.text)
