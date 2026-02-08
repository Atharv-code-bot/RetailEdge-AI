# app/data/cleaners/clean_stores.py

import pandas as pd
from app.data.cleaners.clean_common import drop_null_ids


def clean_stores(df: pd.DataFrame) -> pd.DataFrame:
    df = drop_null_ids(df, ["store_id"])

    # Remove duplicate stores
    df = df.drop_duplicates(subset=["store_id"])

    # Drop rows with invalid open dates
    df = df.dropna(subset=["store_open_date"])

    return df
