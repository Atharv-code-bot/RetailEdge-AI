# app/features/feature_assembler.py

import pandas as pd


def assemble_features(
    inventory_features_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Produces the final feature table consumed by pain-point detectors.
    One row per (product_id, store_id).
    """

    return inventory_features_df.copy()
