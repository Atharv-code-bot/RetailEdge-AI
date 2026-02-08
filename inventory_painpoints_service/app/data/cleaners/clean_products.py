# app/data/cleaners/clean_products.py

import pandas as pd
from app.data.cleaners.clean_common import drop_null_ids


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    df = drop_null_ids(df, ["product_id"])

    # Convert cost & price to numeric but DO NOT drop rows
    df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce")
    df["base_price"] = pd.to_numeric(df["base_price"], errors="coerce")

    # Fill missing values conservatively
    df["unit_cost"] = df["unit_cost"].fillna(0)
    df["base_price"] = df["base_price"].fillna(0)

    df = df.drop_duplicates(subset=["product_id"])

    return df
