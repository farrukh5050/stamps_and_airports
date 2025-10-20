import requests
from ghost_session import GhostSession
import pandas as pd


def get_data_from_excel():
    # 1) Build a mapping: title -> data_key
    data_key_map = (
        pd.read_csv(
            "drivers.csv",
            usecols=["title", "data_key"],
            dtype={"title": str, "data_key": str},
        )
        .assign(title=lambda d: d["title"].str.strip())
        .set_index("title")["data_key"]  # <- Series: index=title, values=data_key
    )

    # 2) Load stamps with Callsign as the index
    stamps_df = pd.read_excel(
        "wk2.xlsm",
        sheet_name="RESULT",
        usecols=["Callsign", "Stamps"],
        dtype={"Callsign": str, "Stamps": float},
    )
    stamps_df.columns = stamps_df.columns.str.strip().str.lower()
    stamps_df = stamps_df.set_index(stamps_df["callsign"].str.strip()).drop(
        columns="callsign"
    )

    # 3) Load stamps with Callsign as the index
    stamps_df = pd.read_excel(
        "wk2.xlsm",
        sheet_name="RESULT",
        usecols=["Callsign", "Stamps"],
        dtype={"Callsign": str, "Stamps": float},
    )
    stamps_df.columns = stamps_df.columns.str.strip().str.lower()
    stamps_df = stamps_df.set_index(stamps_df["callsign"].str.strip()).drop(
        columns="callsign"
    )

    # 3) Map callsign (index) -> data_key
    stamps_df["data_key"] = stamps_df.index.map(data_key_map.get)
    # 4) drop NaN data_key rows
    stamps_df = stamps_df.dropna(subset=["data_key"])

    stamps_df = stamps_df.reset_index()[["callsign", "data_key", "stamps"]]

    return stamps_df


def post_stamps(
    base_url, auth_token, data_key, description, transactionTemplate, stamps_amount
):
    url = f"{base_url}/api/ghost/v1/accounts/driveraccounts/{data_key}/adjustment"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "authentication-token": auth_token,
    }
    payload = {
        "adjustmentReason": "",
        "amount": stamps_amount,
        "applyNow": False,
        "description": description,
        "editMode": False,
        "isCredit": False,
        "sendAsEmail": False,
        "transactionTemplateDescription": transactionTemplate,
        "transactionTemplateId": 5,
        "type": "Debit",
    }
    response = requests.put(url, json=payload, headers=headers)
    response.raise_for_status()


if __name__ == "__main__":
    session = GhostSession()
    auth_token = session.get_token()
    url = session.get_base_url()

    # Map stamps to driver data_keys
    stamps_df = get_data_from_excel()
    print(stamps_df[:10])

    # for _, row in stamps_df.iterrows():
    #     print("Posting to driver", row["callsign"], "stamps amount £", row["stamps"])
    #     post_stamps(
    #         base_url=url,
    #         auth_token=auth_token,
    #         data_key=row["data_key"],
    #         description="STAMPS",
    #         transactionTemplate="STAMP",
    #         stamps_amount=row["stamps"],
    #     )
