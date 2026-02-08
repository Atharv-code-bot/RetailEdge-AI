# app/data/loaders/inventory_loader.py

import pandas as pd

REQUIRED_COLUMNS = {
    "Store_ID",
    "Product_ID",
    "Stock_On_Hand"
}


def load_inventory(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in inventory.csv: {missing_cols}")

    df = df.rename(columns={
        "Store_ID": "store_id",
        "Product_ID": "product_id",
        "Stock_On_Hand": "current_stock"
    })

    return df
