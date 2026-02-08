# app/data/loaders/products_loader.py

import pandas as pd

REQUIRED_COLUMNS = {
    "Product_ID",
    "Product_Name",
    "Product_Category",
    "Product_Cost",
    "Product_Price"
}


def load_products(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Basic schema validation
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in products.csv: {missing_cols}")

    # Normalize column names (snake_case)
    df = df.rename(columns={
        "Product_ID": "product_id",
        "Product_Name": "product_name",
        "Product_Category": "category",
        "Product_Cost": "unit_cost",
        "Product_Price": "base_price"
    })

    return df
