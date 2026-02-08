# app/data/loaders/stores_loader.py

import pandas as pd

REQUIRED_COLUMNS = {
    "Store_ID",
    "Store_Name",
    "Store_City",
    "Store_Location",
    "Store_Open_Date"
}


def load_stores(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in stores.csv: {missing_cols}")

    df = df.rename(columns={
        "Store_ID": "store_id",
        "Store_Name": "store_name",
        "Store_City": "store_city",
        "Store_Location": "store_location",
        "Store_Open_Date": "store_open_date"
    })

    # Parse date
    df["store_open_date"] = pd.to_datetime(df["store_open_date"], errors="coerce")

    return df
