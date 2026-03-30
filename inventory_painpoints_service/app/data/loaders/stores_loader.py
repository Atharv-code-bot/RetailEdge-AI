# app/data/loaders/stores_loader.py
#
# Loads stores.csv into a clean DataFrame.
# Column contract (from our generator):
#   id, name, location_city, location_lat, location_lng, store_type, capacity_units
#
# Internal rename: id → store_id

import pandas as pd

REQUIRED_COLUMNS = {
    "id", "name", "location_city",
    "location_lat", "location_lng",
    "store_type", "capacity_units"
}


def load_stores(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"[stores_loader] Missing columns: {missing}")

    df = df.rename(columns={"id": "store_id"})

    df["location_lat"]   = pd.to_numeric(df["location_lat"],   errors="coerce")
    df["location_lng"]   = pd.to_numeric(df["location_lng"],   errors="coerce")
    df["capacity_units"] = pd.to_numeric(df["capacity_units"], errors="coerce")

    return df
