# app/data/loaders/sales_loader.py

import pandas as pd

REQUIRED_COLUMNS = {
    "Sale_ID",
    "Date",
    "Store_ID",
    "Product_ID",
    "Units"
}


def load_sales(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in sales.csv: {missing_cols}")

    df = df.rename(columns={
        "Sale_ID": "sale_id",
        "Date": "sale_date",
        "Store_ID": "store_id",
        "Product_ID": "product_id",
        "Units": "quantity_sold"
    })

    # Parse date
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")

    return df
