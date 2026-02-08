# app/data/cleaners/clean_sales.py

import pandas as pd
from app.data.cleaners.clean_common import drop_null_ids, enforce_positive_values


def clean_sales(
    sales_df: pd.DataFrame,
    products_df: pd.DataFrame,
    stores_df: pd.DataFrame
) -> pd.DataFrame:

    sales_df = drop_null_ids(
        sales_df,
        ["sale_id", "product_id", "store_id", "sale_date"]
    )

    # Units sold must be positive
    sales_df = enforce_positive_values(sales_df, ["quantity_sold"])
    sales_df = sales_df[sales_df["quantity_sold"] > 0]

    # Referential integrity
    sales_df = sales_df[
        sales_df["product_id"].isin(products_df["product_id"])
    ]

    sales_df = sales_df[
        sales_df["store_id"].isin(stores_df["store_id"])
    ]

    return sales_df
