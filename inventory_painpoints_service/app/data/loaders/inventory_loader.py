# app/data/loaders/inventory_loader.py
#
# Loads inventory.csv into a clean DataFrame.
# Column contract (from our generator):
#   id, product_id, store_id, current_stock, reorder_level,
#   expiry_date, last_restocked_at
#
# Internal rename: id → inventory_id

import pandas as pd

REQUIRED_COLUMNS = {
    "id", "product_id", "store_id",
    "current_stock", "reorder_level",
    "expiry_date", "last_restocked_at"
}


def load_inventory(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"[inventory_loader] Missing columns: {missing}")

    df = df.rename(columns={"id": "inventory_id"})

    df["current_stock"]  = pd.to_numeric(df["current_stock"],  errors="coerce")
    df["reorder_level"]  = pd.to_numeric(df["reorder_level"],  errors="coerce")

    # expiry_date is nullable — non-perishables have no expiry
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce")

    df["last_restocked_at"] = pd.to_datetime(df["last_restocked_at"], errors="coerce")

    return df
