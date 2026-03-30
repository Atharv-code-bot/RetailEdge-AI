# app/data/cleaners/clean_stores.py
#
# Fixes from audit:
#   - ChatGPT used 'store_id' column check — correct after loader rename
#   - ChatGPT dropped on 'created_at' — our stores CSV does NOT have this column
#   - Our columns: store_id, name, location_city, location_lat, location_lng,
#                  store_type, capacity_units

import pandas as pd
from inventory_painpoints_service.app.data.cleaners.clean_common import drop_null_ids, drop_duplicate_keys


def clean_stores(df: pd.DataFrame) -> pd.DataFrame:

    # store_id mandatory — loader already renamed id → store_id
    df = drop_null_ids(df, ["store_id", "location_city"])

    df = df.copy()

    df["location_lat"]   = pd.to_numeric(df["location_lat"],   errors="coerce")
    df["location_lng"]   = pd.to_numeric(df["location_lng"],   errors="coerce")
    df["capacity_units"] = pd.to_numeric(df["capacity_units"], errors="coerce")

    # store_type must be physical or online
    valid_types = {"physical", "online"}
    invalid = ~df["store_type"].isin(valid_types)
    if invalid.any():
        print(f"  [clean_stores] dropping {invalid.sum()} rows with invalid store_type")
        df = df[~invalid]

    # One row per store
    df = drop_duplicate_keys(df, ["store_id"])

    return df
