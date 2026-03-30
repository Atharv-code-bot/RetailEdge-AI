# app/data/cleaners/clean_products.py
#
# Fixes from audit:
#   - ChatGPT used 'product_id', 'unit_cost', 'base_price' — all wrong column names
#   - Our loader already renames id → product_id, so that is correct here
#   - Our columns: cost_price, base_selling_price (not unit_cost, base_price)

import pandas as pd
from inventory_painpoints_service.app.data.cleaners.clean_common import drop_null_ids, drop_duplicate_keys


def clean_products(df: pd.DataFrame) -> pd.DataFrame:

    # product_id is mandatory — loader already renamed id → product_id
    df = drop_null_ids(df, ["product_id"])

    df = df.copy()

    # Correct column names from our CSV
    df["cost_price"]         = pd.to_numeric(df["cost_price"],         errors="coerce").fillna(0)
    df["base_selling_price"] = pd.to_numeric(df["base_selling_price"], errors="coerce").fillna(0)

    # shelf_life_days is nullable — None means non-perishable. Keep nulls.
    df["shelf_life_days"] = pd.to_numeric(df["shelf_life_days"], errors="coerce")

    # Remove any product where shelf_life_days is negative (data error)
    df = df[
        df["shelf_life_days"].isna() |
        (df["shelf_life_days"] >= 0)
    ]

    # One row per product
    df = drop_duplicate_keys(df, ["product_id"])

    return df
