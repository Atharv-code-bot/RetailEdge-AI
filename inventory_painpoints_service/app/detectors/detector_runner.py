# app/detectors/detector_runner.py
#
# Runs all 5 pain point detectors against the feature matrix.
# Fills the pain_points_triggered and composite_risk_score columns
# in the product_analysis DataFrame.
#
# Build Plan Section 3.17 — 5 pain points:
#   NEAR_EXPIRY, STAGNANT, LOW_STOCK, HIGH_RETURN, SEASONAL_MISMATCH
#
# Pain point priority when multiple fire (Build Plan Section 3.19):
#   NEAR_EXPIRY (1) > HIGH_RETURN (2) > STAGNANT (3) > LOW_STOCK (4) > SEASONAL_MISMATCH (5)
#
# What changed from ChatGPT version:
#   - Fixed import naming crash (was mixing detect_* prefix inconsistently)
#   - Removed DECLINING_SALES and OVERSTOCK as separate detectors (not in build plan)
#   - pain_points_triggered stored as JSON-serialisable list (not separate rows)
#   - composite_risk_score computed here (was missing entirely)
#   - No explanation strings in output

import json
import pandas as pd

from inventory_painpoints_service.app.detectors.near_expiry       import detect_near_expiry
from inventory_painpoints_service.app.detectors.stagnant_sales    import detect_stagnant_sales
from inventory_painpoints_service.app.detectors.low_stock         import detect_low_stock
from inventory_painpoints_service.app.detectors.high_returns      import detect_high_returns
from inventory_painpoints_service.app.detectors.seasonal_mismatch import detect_seasonal_mismatch
from inventory_painpoints_service.app.detectors.composite_risk    import compute_composite_risk


# Maps detector function → pain point label
DETECTORS = [
    (detect_near_expiry,       "NEAR_EXPIRY"),
    (detect_high_returns,      "HIGH_RETURN"),
    (detect_stagnant_sales,    "STAGNANT"),
    (detect_low_stock,         "LOW_STOCK"),
    (detect_seasonal_mismatch, "SEASONAL_MISMATCH"),
]


def run_all_detectors(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs all detectors against the feature matrix.
    Fills pain_points_triggered (JSON list) and composite_risk_score (float).

    Input:  product_analysis DataFrame from feature_assembler (with None placeholders)
    Output: same DataFrame with pain_points_triggered and composite_risk_score filled
    """

    df = features_df.copy()

    # Build a dict of {label: boolean_mask} for all detectors
    masks = {}
    for detector_fn, label in DETECTORS:
        masks[label] = detector_fn(df)

    # Fill pain_points_triggered — list of all labels that fired for each product
    def get_pain_points(idx):
        triggered = [
            label for label, mask in masks.items()
            if mask.iloc[idx]
        ]
        return json.dumps(triggered)   # JSON string for CSV/DB storage

    df["pain_points_triggered"] = [
        get_pain_points(i) for i in range(len(df))
    ]

    # Fill composite_risk_score
    df["composite_risk_score"] = compute_composite_risk(df, masks)

    return df
