# app/data/cleaners/clean_inventory.py

import pandas as pd
from app.data.cleaners.clean_common import drop_null_ids, enforce_positive_values


def clean_inventory(
    inventory_df: pd.DataFrame,
    products_df: pd.DataFrame,
    stores_df: pd.DataFrame
) -> pd.DataFrame:

    inventory_df = drop_null_ids(
        inventory_df,
        ["product_id", "store_id"]
    )

    inventory_df = enforce_positive_values(
        inventory_df,
        ["current_stock"]
    )

    # Referential integrity
    inventory_df = inventory_df[
        inventory_df["product_id"].isin(products_df["product_id"])
    ]

    inventory_df = inventory_df[
        inventory_df["store_id"].isin(stores_df["store_id"])
    ]

    # One inventory row per store-product
    inventory_df = inventory_df.drop_duplicates(
        subset=["store_id", "product_id"]
    )

    return inventory_df
