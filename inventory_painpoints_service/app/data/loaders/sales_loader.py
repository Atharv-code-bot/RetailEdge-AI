# app/data/loaders/sales_loader.py
#
# Loads sales.csv into a clean DataFrame.
# Column contract (from our generator):
#   id, product_id, store_id, quantity_sold, selling_price, sold_at, channel
#
# Internal rename: id → sale_id, sold_at → sale_date

import pandas as pd

REQUIRED_COLUMNS = {
    "id", "product_id", "store_id",
    "quantity_sold", "selling_price", "sold_at", "channel"
}


def load_sales(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"[sales_loader] Missing columns: {missing}")

    df = df.rename(columns={
        "id":       "sale_id",
        "sold_at":  "sale_date",   # normalise to sale_date internally
    })

    # Parse date — our generator writes ISO format (YYYY-MM-DD)
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")

    df["quantity_sold"]  = pd.to_numeric(df["quantity_sold"],  errors="coerce")
    df["selling_price"]  = pd.to_numeric(df["selling_price"],  errors="coerce")

    return df
