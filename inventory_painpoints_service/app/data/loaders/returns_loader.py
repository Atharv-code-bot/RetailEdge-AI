# app/data/loaders/returns_loader.py
#
# Loads returns.csv into a clean DataFrame.
# Column contract (from our generator):
#   id, product_id, store_id, quantity_returned, reason, returned_at
#
# Internal rename: id → return_id, returned_at → return_date

import pandas as pd

REQUIRED_COLUMNS = {
    "id", "product_id", "store_id",
    "quantity_returned", "reason", "returned_at"
}


def load_returns(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"[returns_loader] Missing columns: {missing}")

    df = df.rename(columns={
        "id":          "return_id",
        "returned_at": "return_date",   # normalise to return_date internally
    })

    df["return_date"]       = pd.to_datetime(df["return_date"], errors="coerce")
    df["quantity_returned"] = pd.to_numeric(df["quantity_returned"], errors="coerce")

    return df
