import requests
from ghost_session import GhostSession
import pandas as pd


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
    # 404 error means driver not found - skipping
    if response.status_code == 404:
        print(f"Driver with data_key {data_key} not found. Skipping.")
        return
    response.raise_for_status()


def get_data_from_excel():
    # 1) Build a mapping: title -> data_key
    data_key_map = (
        pd.read_csv(
            "drivers.csv",
            usecols=["title", "data_key"],
            dtype={"title": str, "data_key": int},
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


def get_stamps_airports():
    # Build a clean title -> data_key map (as strings)
    data_key_map = (
        pd.read_csv("drivers.csv", usecols=["title", "data_key"], dtype=str)
        .assign(
            title=lambda d: d["title"].str.strip(),
            data_key=lambda d: d["data_key"]
            .str.strip()
            .str.replace(".0", "", regex=False),
        )
        .set_index("title")["data_key"]
    )

    # Load the RESULT sheet
    df = pd.read_excel("wk2.xlsm", sheet_name="RESULT")

    # Split into stamps / airports blocks
    df_stamps = df.iloc[:, 0:3].copy()  # ['Callsign','Count','Stamps']
    df_airports = df.iloc[:, 4:7].copy()  # ['Callsign.1','Count.1','Airports']

    # Normalize join keys (use the callsign text itself, not the index)
    df_stamps["Driver"] = (
        df_stamps["Callsign"]
        .apply(
            lambda x: (
                str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)
            )
        )
        .str.strip()
    )

    df_airports["Driver"] = (
        df_airports["Callsign.1"]
        .apply(
            lambda x: (
                str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)
            )
        )
        .str.strip()
    )

    # Drop rows without values to post
    df_stamps = df_stamps.dropna(subset=["Driver", "Stamps"])
    df_airports = df_airports.dropna(subset=["Driver", "Airports"])

    # Map Driver -> data_key
    df_stamps["data_key"] = df_stamps["Driver"].map(data_key_map)
    df_airports["data_key"] = df_airports["Driver"].map(data_key_map)

    # (Optional) sanity prints
    print("Unmatched STAMPS:", df_stamps["data_key"].isna().sum())
    print("Unmatched AIRPORTS:", df_airports["data_key"].isna().sum())

    # Save with clear column order
    # df_stamps.to_excel(
    #     "stamps_output.xlsx",
    #     index=False,
    #     columns=["Callsign", "data_key", "Count", "Stamps"],
    # )
    # df_airports.to_excel(
    #     "airports_output.xlsx",
    #     index=False,
    #     columns=["Callsign.1", "data_key", "Count.1", "Airports"],
    # )

    return df_stamps, df_airports


if __name__ == "__main__":
    session = GhostSession()
    auth_token = session.get_token()
    url = session.get_base_url()

    # Map stamps to driver data_keys
    df_stamps, df_airports = get_stamps_airports()

    for _, row in df_stamps.iterrows():
        print("Posting to driver", row["Callsign"], "stamps amount £", row["Stamps"])
        post_stamps(
            base_url=url,
            auth_token=auth_token,
            data_key=row["data_key"],
            description="STAMPS",
            transactionTemplate="STAMP",
            stamps_amount=row["Stamps"],
        )

    for _, row in df_airports.iterrows():
        print(
            "Posting to driver", row["Callsign.1"], "Airport amount £", row["Airports"]
        )
        post_stamps(
            base_url=url,
            auth_token=auth_token,
            data_key=row["data_key"],
            description="AIRPORTS",
            transactionTemplate="AIRPORTS",
            stamps_amount=row["Airports"],
        )
