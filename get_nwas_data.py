import os
import re
import time
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from datetime import date, datetime
from io import StringIO
import pandas as pd
from openpyxl import Workbook
from dotenv import load_dotenv
from pathlib import Path
from selenium.common.exceptions import NoSuchElementException
import sys
from selenium.webdriver.chrome.options import Options


# Constants
JRNY_ID_COLUMN = "jrny id"
PHONE_COLUMN = "phone no"
UNWANTED_TEXT = ">>>>>"
RUN_COLUMN = "run"  # Ensure this matches the column containing cost centers
COLS_TO_DROP = ["age", "mob", "cat", "description", "time", "cost_center"]
UPDATE_COLS_TO_DROP = ["time", "cost_center"]
FILENAME = "xl_data/nwas_logsheet.xlsx"
UPDATE_FILENAME = "xl_data/nwas_logsheet_update.xlsx"
REBOOK_JOBS_FILENAME = "xl_data/rebook_jobs.xlsx"
uk_tz = pytz.timezone("Europe/London")


# Always prefer a .env file NEXT TO the exe (or script when not frozen)
if getattr(sys, "frozen", False):
    app_dir = Path(sys.executable).parent  # folder containing the .exe
else:
    app_dir = Path(__file__).parent  # folder containing the .py

# Try these locations in order
candidate_env_files = [
    app_dir / ".env",  # <— your screenshot location
    Path.cwd() / ".env",  # if launched from elsewhere
]

loaded = False
for p in candidate_env_files:
    if p.exists():
        load_dotenv(p)  # load this file
        loaded = True
        print(f"Loaded environment from: {p}")
        break

if not loaded:
    # Fallback: respect real OS env vars if user set them in Windows
    load_dotenv()  # no path — doesn’t override OS env
    print("No .env file found next to the app; relying on OS environment variables.")

username = os.getenv("NWAS_USERNAME")
password = os.getenv("NWAS_PASSWORD")

if not username or not password:
    print(
        "❌ NWAS_USERNAME or NWAS_PASSWORD not set. Put them in a .env next to the .exe."
    )
    sys.exit(1)


def open_chrome_and_login():
    from selenium.webdriver.chrome.service import Service

    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = Service(log_path=os.devnull)  # ✅ suppress logs
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get("https://ptsed.nwas.nhs.uk/")
    driver.find_element(By.ID, "txtUsername").send_keys(username)
    driver.find_element(By.ID, "txtPassword").send_keys(password)
    driver.find_element(By.ID, "cmdSubmit").click()
    time.sleep(3)

    try:
        driver.get("https://ptsed.nwas.nhs.uk/frmLogsheets.aspx")
        # Try to interact with an element that should only exist if login worked
        date_input = driver.find_element(By.ID, "txtPlanDate")
    except NoSuchElementException:
        driver.quit()
        raise SystemExit(
            "❌ WRONG PASSWORD or expired login — please update your .env file."
        )

    # continue normal flow if successful
    date_input.clear()
    date_input.send_keys(date.today().strftime("%d%m%Y"))
    driver.find_element(By.CSS_SELECTOR, "label[for='chkIncAbort']").click()
    driver.find_element(By.CSS_SELECTOR, "label[for='chkIncCancel']").click()
    driver.find_element(By.ID, "cmdSubmit").click()
    time.sleep(3)

    return driver


def extract_phone_numbers(value):
    text = str(value)

    # Match UK-style numbers with optional spaces
    numbers = re.findall(r"0\d(?:\s?\d){9,10}", text)

    if not numbers:
        return ""

    numbers = [num.replace(" ", "") for num in numbers]

    # Prefer mobile numbers (start with 07)
    mobiles = [num for num in numbers if num.startswith("07")]
    if mobiles:
        return mobiles[0]  # return the first mobile

    # Otherwise return the first valid number
    return numbers[0]


def contains_unwanted_text(row):
    return row.astype(str).str.contains(UNWANTED_TEXT, case=False).any()


def get_today_date():
    return datetime.now(uk_tz).strftime("%Y-%m-%d")


def extract_departure_time(t):
    try:
        # Convert to string and strip whitespace
        t = str(t).strip()

        # Extract the first valid HH:MM pattern (e.g., from '10:30 08:40 R')
        match = re.search(r"\b\d{1,2}:\d{2}\b", t)
        if match:
            time_str = match.group()
            dt = datetime.strptime(f"{get_today_date()} {time_str}", "%Y-%m-%d %H:%M")
            dt = pytz.timezone("Europe/London").localize(dt)
            return dt.isoformat()
    except Exception as e:
        print(f"Failed to parse time '{t}': {e}")
    return None


def close_driver(driver):
    try:
        driver.quit()
        print("✅WebDriver closed.")
    except Exception:
        print("WebDriver closing encountered an issue.")


def check_today_date(existing_data, filename):
    """Delete the Excel file if any date is not today's date."""
    if existing_data:
        first_sheet = list(existing_data.keys())[0]
        first_sheet_df = existing_data[first_sheet]

        if not first_sheet_df.empty and "formatted_time" in first_sheet_df.columns:
            try:
                formatted_dates = pd.to_datetime(
                    first_sheet_df["formatted_time"], errors="coerce"
                ).dt.date.dropna()

                today = date.today()

                if not all(d == today for d in formatted_dates):

                    if os.path.exists(filename):
                        os.remove(filename)
                    wb = Workbook()
                    wb.save(filename)
                    print("✅ Excel file successfully reset.")
                    return True  # File was reset

            except Exception as e:
                print(f"✅ Error checking dates in formatted_time: {e}")
                return False

    return False  # No reset needed


def save_to_excel(data):
    if data is None:
        return None

    try:
        existing_data = {}  # Default to empty
        if os.path.exists(FILENAME):
            with pd.ExcelFile(FILENAME, engine="openpyxl") as xls:
                existing_data = {
                    sheet: pd.read_excel(xls, sheet_name=sheet)
                    for sheet in xls.sheet_names
                }

        # If yesterday's data is found, reset the file before saving
        file_reset = check_today_date(existing_data, FILENAME)

        data["formatted_time"] = data["time"].apply(extract_departure_time)
        data = data[~data.apply(contains_unwanted_text, axis=1)]

        with pd.ExcelWriter(FILENAME, engine="openpyxl", mode="w") as writer:
            for cost_center, group in data.groupby("cost_center"):

                group = group.drop(columns=COLS_TO_DROP, errors="ignore")
                group = group.iloc[1:].reset_index(drop=True)
                group[JRNY_ID_COLUMN] = group[JRNY_ID_COLUMN].astype(str)

                if not file_reset and cost_center in existing_data:
                    old_group = existing_data[cost_center]
                    old_group[JRNY_ID_COLUMN] = old_group[JRNY_ID_COLUMN].astype(str)

                    if "status" not in old_group.columns:
                        old_group["status"] = ""
                    if "status" not in group.columns:
                        group["status"] = ""

                    group = (
                        pd.concat([old_group, group])
                        .sort_values(by="status", ascending=False, na_position="last")
                        .drop_duplicates(
                            subset=["jrny id", "formatted_time"], keep="first"
                        )
                        .reset_index(drop=True)
                    )
                # add status column before saving new excel file
                if "status" not in group.columns:
                    group["status"] = ""

                group["formatted_time"] = group["formatted_time"].str.replace(
                    r"\s*R:00\s*", "", regex=True
                )
                group["formatted_time"] = (
                    group["formatted_time"].astype(str).str.extract(r"^(\S+)")
                )
                group.to_excel(writer, sheet_name=cost_center[:31], index=False)

        print(f"✅ Successfully saved get_nwas_data.xlsx.")
        return data

    except Exception as e:
        print(f"✅ Error saving to Excel: {e}")
        return None


def format_time_string(raw_time):
    if not isinstance(raw_time, str):
        return None
    times = re.findall(r"\b\d{1,2}:\d{2}\b", raw_time)
    if not times:
        return None
    try:
        hour, minute = map(int, times[-1].split(":"))  # grab the last time
        current_date = datetime.now(uk_tz).date()  # <-- always “today”
        dt = datetime.combine(current_date, datetime.min.time()).replace(
            hour=hour, minute=minute
        )
        dt = uk_tz.localize(dt)
        return dt.isoformat()
    except Exception as e:
        print(f"❌ Time parse error for '{raw_time}': {e}")
        return None


def save_update_excel(df):
    df = df.copy()
    if df.empty:
        return False

    df.columns = df.columns.str.strip().str.lower()

    # Drop irrelevant columns
    cols_to_drop = {"age", "mob", "cat", "description"}
    df = df.drop(
        columns=[col for col in cols_to_drop if col in df.columns], errors="ignore"
    )

    # Fill down 'run' column
    df["run"] = df["run"].where(df["run"].str.contains("Run", na=False)).ffill()
    df["formatted_time"] = df["time"].apply(extract_departure_time)

    matched_rows = []

    # Step 1: CANCELLED or ABORTED
    for i in range(len(df) - 1):
        current_row = df.iloc[i]
        next_row = df.iloc[i + 1]
        jrny_id = str(current_row[JRNY_ID_COLUMN])
        next_jrny_id = str(next_row[JRNY_ID_COLUMN]).lower()

        if jrny_id.isdigit():
            if "cancelled" in next_jrny_id:
                row_type = "CANCELLED"
            elif "aborted" in next_jrny_id:
                row_type = "ABORTED"
            else:
                continue

            full_row = current_row.copy()
            full_row["type"] = row_type
            full_row["formatted_time"] = format_time_string(current_row.get("time", ""))
            matched_rows.append(full_row)

    # Step 2: R-times
    for _, row in df.iterrows():
        jrny_id = str(row[JRNY_ID_COLUMN])
        time_val = str(row.get("time", "")).lower()

        if jrny_id.isdigit() and "r" in time_val:
            full_row = row.copy()
            full_row["type"] = "R"
            full_row["formatted_time"] = format_time_string(row.get("time", ""))
            matched_rows.append(full_row)

    df = pd.DataFrame(matched_rows)
    if df.empty or "cost_center" not in df.columns:
        return False

    # Load existing data if the file exists
    existing_data = {}
    if os.path.exists(UPDATE_FILENAME):
        with pd.ExcelFile(UPDATE_FILENAME, engine="openpyxl") as xls:
            existing_data = {
                sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names
            }

    file_reset = check_today_date(existing_data, UPDATE_FILENAME)

    with pd.ExcelWriter(UPDATE_FILENAME, engine="openpyxl", mode="w") as writer:
        for cost_center, group in df.groupby("cost_center"):
            sheet_name = cost_center[:31]

            group = group.drop(columns=UPDATE_COLS_TO_DROP, errors="ignore")
            group[JRNY_ID_COLUMN] = group[JRNY_ID_COLUMN].astype(str)

            if "type" not in group.columns:
                group["type"] = ""

            if not file_reset and sheet_name in existing_data:
                old = existing_data[sheet_name]
                old[JRNY_ID_COLUMN] = old[JRNY_ID_COLUMN].astype(str)

                if "status" not in old.columns:
                    old["status"] = ""

                if "type" not in old.columns and "status" in old.columns:
                    old["type"] = old["status"]
                elif "type" not in old.columns:
                    old["type"] = ""

                group = pd.concat([old, group], ignore_index=True)
            else:
                group["status"] = ""

            group = group.drop_duplicates(
                subset=[JRNY_ID_COLUMN, "formatted_time"], keep="first"
            )

            if "run" in group.columns:
                group["run_num"] = (
                    group["run"].str.extract(r"Run\s*(\d+)").astype(float)
                )
            else:
                group["run_num"] = float("inf")

            group = group.sort_values(
                by=["type", "run_num"], ascending=[False, True], na_position="last"
            ).drop(columns="run_num")

            ordered_cols = [
                col
                for col in [
                    "run",
                    JRNY_ID_COLUMN,
                    "name",
                    "from",
                    "to",
                    "esc",
                    "notes",
                    "phone no",
                    "formatted_time",
                    "type",
                    "status",
                ]
                if col in group.columns
            ]
            group = group[ordered_cols]
            group.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"✅ Successfully saved nwas_logsheet_update.xlsx.")
    return True


def clean_table(df):
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    try:
        df = df[
            ~df["jrny id"]
            .fillna("")
            .astype(str)
            .str.contains(r"(?i)^\s*[^a-z0-9]*notes?[^a-z0-9]*$|^\s*last\s*updated\b")
        ]
        # Remove only "Ack" from the RUN_COLUMN
        df.loc[:, RUN_COLUMN] = df[RUN_COLUMN].replace(
            r"(?i)^ack$", "", regex=True
        )  # remove "Ack"
        df.loc[:, RUN_COLUMN] = df[RUN_COLUMN].replace(
            r"^\s*$", pd.NA, regex=True
        )  # convert empty to NaN

        df.loc[:, PHONE_COLUMN] = (
            df[JRNY_ID_COLUMN].apply(extract_phone_numbers).shift(-1)
        )

        df.loc[:, RUN_COLUMN] = df[RUN_COLUMN].ffill(axis=0)
        df = df.dropna(subset=[JRNY_ID_COLUMN], how="all").reset_index(drop=True)

        df["to"] = (
            df["to"]
            .str.replace(r",\s*,", ", ", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        df["from"] = (
            df["from"]
            .str.replace(r",\s*,", ", ", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        df.loc[:, "cost_center"] = (
            df[JRNY_ID_COLUMN].str.extract(r"(STC[A-Z0-9]+)", expand=False).ffill()
        )

        return df

    except Exception as e:
        print("Failed to extract table:")
        return None


def handle_rebook(df):
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()

    # --- Clean rows and RUN column safely ---
    try:
        df = df[
            ~df.apply(
                lambda row: (
                    row.astype(str).str.contains("NOTE", case=False).any()
                    or row.astype(str).str.contains("Last Updated:", case=False).any()
                ),
                axis=1,
            )
        ]
        # Remove only "Ack" from RUN_COLUMN, then blank -> NaN
        df.loc[:, RUN_COLUMN] = df[RUN_COLUMN].replace(r"(?i)^ack$", "", regex=True)
        df.loc[:, RUN_COLUMN] = df[RUN_COLUMN].replace(r"^\s*$", pd.NA, regex=True)
    except Exception as e:
        print(f"Error cleaning data: {e}")
        return

    # --- Normalise IDs and run grouping ---
    df["jrny id"] = df["jrny id"].astype(str).str.strip()
    df[RUN_COLUMN] = (
        df[RUN_COLUMN].where(df[RUN_COLUMN].str.contains("Run", na=False)).ffill()
    )
    df["cost_center"] = (
        df["jrny id"].str.extract(r"(STC[A-Z0-9]+)", expand=False).ffill()
    )

    final_rows = []

    # --- Group by cost center and run ---
    for cost_center, sheet_df in df.groupby("cost_center"):
        for run_id, group in sheet_df.groupby(RUN_COLUMN):
            group = group.reset_index(drop=True)

            current_journey_id = None
            journey_status = {}
            journey_row_indices = {}

            for i, row in group.iterrows():
                jrny_id_match = re.match(r"^\d{8}$", str(row["jrny id"]).strip())
                if jrny_id_match:
                    current_journey_id = row["jrny id"]
                    journey_status[current_journey_id] = "valid"
                    journey_row_indices[current_journey_id] = i
                else:
                    if current_journey_id and any(
                        re.search(r"\b(cancelled|aborted)\b", str(val), re.IGNORECASE)
                        for val in row.values
                    ):
                        journey_status[current_journey_id] = "cancelled"

            valid_journeys = []
            cancelled_journeys = [
                j_id for j_id, status in journey_status.items() if status == "cancelled"
            ]

            if cancelled_journeys:
                for j_id, i in journey_row_indices.items():
                    if journey_status[j_id] == "valid":
                        row = group.loc[i].to_dict()
                        # Try get phone number from the next row
                        if i + 1 < len(group):
                            next_row = group.loc[i + 1]
                            phone_match = extract_phone_numbers(
                                " ".join(next_row.values.astype(str))
                            )
                            row["phone no"] = phone_match
                        else:
                            row["phone no"] = ""
                        raw_time = row.get("time", "")
                        row["formatted_time"] = format_time_string(raw_time)
                        valid_journeys.append(row)

            if valid_journeys:
                final_rows.extend(valid_journeys)

    result_df = pd.DataFrame(final_rows)

    # Drop unused columns if present
    columns_to_drop = ["age", "mob", "cat", "time", "description"]
    result_df = result_df.drop(
        columns=[col for col in columns_to_drop if col in result_df.columns]
    )

    if result_df.empty:
        print("No valid journeys matched the rebooking criteria.")
        return

    os.makedirs("xl_data", exist_ok=True)

    # Ensure status column
    if "status" not in result_df.columns:
        result_df["status"] = ""

    # --- Step 1: Load existing file and decide whether to reset ---
    existing_data = {}
    file_reset = False
    if os.path.exists(REBOOK_JOBS_FILENAME):
        with pd.ExcelFile(REBOOK_JOBS_FILENAME, engine="openpyxl") as xls:
            existing_data = {
                sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names
            }
        file_reset = check_today_date(existing_data, REBOOK_JOBS_FILENAME)

    # --- Step 2: Save each cost center to its own sheet WITHOUT overwriting existing data ---
    merged_sheets = {}

    # --- Step 3: Carry over existing sheets unless we need to reset
    if not file_reset and existing_data:
        for sheet_name, old in existing_data.items():
            # Normalise for safety
            if "status" not in old.columns:
                old["status"] = ""
            if JRNY_ID_COLUMN not in old.columns:
                old[JRNY_ID_COLUMN] = ""
            old[JRNY_ID_COLUMN] = old[JRNY_ID_COLUMN].astype(str)
            merged_sheets[sheet_name] = old

    # --- Step 3b: Merge new rows into their respective cost_center sheets
    for cost_center, group_df in result_df.groupby("cost_center"):
        sheet_name = (str(cost_center) if pd.notna(cost_center) else "Unknown")[
            :31
        ]  # Excel limit 31
        # Ensure 'status' is last column
        cols = [col for col in group_df.columns if col != "status"] + ["status"]
        group_df = group_df[cols]
        group_df[JRNY_ID_COLUMN] = group_df[JRNY_ID_COLUMN].astype(str)

        if sheet_name in merged_sheets:
            combined = pd.concat(
                [merged_sheets[sheet_name], group_df], ignore_index=True, sort=False
            )
        else:
            combined = group_df

        combined = combined.drop_duplicates(
            subset=[JRNY_ID_COLUMN], keep="first"
        ).reset_index(drop=True)
        # Keep 'status' as last column
        cols = [col for col in combined.columns if col != "status"] + ["status"]
        merged_sheets[sheet_name] = combined[cols]

    # --- Step 3c: Write ALL sheets once
    with pd.ExcelWriter(REBOOK_JOBS_FILENAME, engine="openpyxl", mode="w") as writer:
        for sheet_name, out_df in merged_sheets.items():
            # Re-ensure column order per sheet
            cols = [col for col in out_df.columns if col != "status"] + ["status"]
            out_df = out_df[cols]
            out_df.to_excel(writer, index=False, sheet_name=sheet_name)

    print(f"✅ Saved rebookable journeys by cost center to {REBOOK_JOBS_FILENAME}.")


def main():
    driver = open_chrome_and_login()

    try:
        html_content = driver.find_element(By.ID, "divLogsheetHTML").get_attribute(
            "outerHTML"
        )
        tables = pd.read_html(StringIO(str(html_content)), flavor="lxml")
        df = tables[0].dropna(how="all")
        clean_data = clean_table(df)
        save_to_excel(clean_data)
        save_update_excel(clean_data)
        handle_rebook(clean_data)
    except ValueError:
        print("✅ No tables found.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        close_driver(driver)


if __name__ == "__main__":
    main()
