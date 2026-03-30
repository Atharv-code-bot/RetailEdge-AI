# app/data/cleaners/clean_sales.py
#
# Fixes from audit:
#   - ChatGPT checked products_df["product_id"] correctly BUT
#     also checked stores_df["store_id"] — both now correct after loader renames
#   - ChatGPT dropped on "sale_date" — now correct after loader renames sold_at → sale_date
#   - Referential integrity checks now use correct column names

import pandas as pd
from inventory_painpoints_service.app.data.cleaners.clean_common import (
    drop_null_ids,
    enforce_positive_values,
    drop_duplicate_keys,
)


def clean_sales(
    sales_df: pd.DataFrame,
    products_df: pd.DataFrame,
    stores_df: pd.DataFrame,
) -> pd.DataFrame:

    # Required fields — loader already renamed id→sale_id, sold_at→sale_date
    sales_df = drop_null_ids(
        sales_df,
        ["sale_id", "product_id", "store_id", "sale_date"]
    )

    # Quantity and price must be positive
    sales_df = enforce_positive_values(sales_df, ["quantity_sold", "selling_price"])
    sales_df = sales_df[sales_df["quantity_sold"] > 0]

    # Referential integrity — only keep sales for known products and stores
    valid_products = set(products_df["product_id"])
    valid_stores   = set(stores_df["store_id"])

    before = len(sales_df)
    sales_df = sales_df[sales_df["product_id"].isin(valid_products)]
    sales_df = sales_df[sales_df["store_id"].isin(valid_stores)]
    dropped = before - len(sales_df)
    if dropped > 0:
        print(f"  [clean_sales] dropped {dropped} rows failing referential integrity")

    # No duplicate sale records for same product+store+date
    # (our generator writes one row per product per store per day — this is a safety check)
    sales_df = drop_duplicate_keys(sales_df, ["product_id", "store_id", "sale_date"])

    return sales_df
