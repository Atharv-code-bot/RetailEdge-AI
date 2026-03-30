# app/data/cleaners/clean_inventory.py
#
# Inventory has one row per (product, store) pair.
# expiry_date is nullable — non-perishables have no expiry.
# reorder_level comes from the DB/CSV — we never recompute it here.

import pandas as pd
from inventory_painpoints_service.app.data.cleaners.clean_common import (
    drop_null_ids,
    enforce_positive_values,
    drop_duplicate_keys,
)


def clean_inventory(
    inventory_df: pd.DataFrame,
    products_df: pd.DataFrame,
    stores_df: pd.DataFrame,
) -> pd.DataFrame:

    inventory_df = drop_null_ids(
        inventory_df,
        ["inventory_id", "product_id", "store_id"]
    )

    # Stock values must be >= 0
    inventory_df = enforce_positive_values(
        inventory_df,
        ["current_stock", "reorder_level"]
    )

    # Referential integrity
    valid_products = set(products_df["product_id"])
    valid_stores   = set(stores_df["store_id"])

    before = len(inventory_df)
    inventory_df = inventory_df[inventory_df["product_id"].isin(valid_products)]
    inventory_df = inventory_df[inventory_df["store_id"].isin(valid_stores)]
    dropped = before - len(inventory_df)
    if dropped > 0:
        print(f"  [clean_inventory] dropped {dropped} rows failing referential integrity")

    # One inventory row per (product, store)
    inventory_df = drop_duplicate_keys(inventory_df, ["product_id", "store_id"])

    return inventory_df
