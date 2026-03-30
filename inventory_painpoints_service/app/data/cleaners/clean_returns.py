# app/data/cleaners/clean_returns.py
#
# Fixes from audit:
#   - ChatGPT had no returns cleaner — this is new
#   - Our loader already renamed returned_at → return_date
#   - quantity_returned must be > 0

import pandas as pd
from inventory_painpoints_service.app.data.cleaners.clean_common import (
    drop_null_ids,
    enforce_positive_values,
)


def clean_returns(
    returns_df: pd.DataFrame,
    products_df: pd.DataFrame,
    stores_df: pd.DataFrame,
) -> pd.DataFrame:

    # loader already renamed: returned_at → return_date, id → return_id
    returns_df = drop_null_ids(
        returns_df,
        ["return_id", "product_id", "store_id", "return_date"]
    )

    returns_df = enforce_positive_values(returns_df, ["quantity_returned"])
    returns_df = returns_df[returns_df["quantity_returned"] > 0]

    # Referential integrity
    valid_products = set(products_df["product_id"])
    valid_stores   = set(stores_df["store_id"])

    before = len(returns_df)
    returns_df = returns_df[returns_df["product_id"].isin(valid_products)]
    returns_df = returns_df[returns_df["store_id"].isin(valid_stores)]
    dropped = before - len(returns_df)
    if dropped > 0:
        print(f"  [clean_returns] dropped {dropped} rows failing referential integrity")

    return returns_df
