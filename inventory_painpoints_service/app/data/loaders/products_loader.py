# app/data/loaders/products_loader.py
#
# Loads products.csv into a clean DataFrame.
# Column contract (from our generator):
#   id, name, category, brand, cost_price, base_selling_price, shelf_life_days
#
# Internal rename: id → product_id  (consistent FK name across all tables)

import pandas as pd

REQUIRED_COLUMNS = {
    "id", "name", "category", "brand",
    "cost_price", "base_selling_price", "shelf_life_days"
}


def load_products(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"[products_loader] Missing columns: {missing}")

    # Rename id → product_id so all tables share the same FK name
    df = df.rename(columns={"id": "product_id"})

    # shelf_life_days is nullable (None = non-perishable)
    df["shelf_life_days"] = pd.to_numeric(df["shelf_life_days"], errors="coerce")

    df["cost_price"]          = pd.to_numeric(df["cost_price"],          errors="coerce")
    df["base_selling_price"]  = pd.to_numeric(df["base_selling_price"],  errors="coerce")

    return df
