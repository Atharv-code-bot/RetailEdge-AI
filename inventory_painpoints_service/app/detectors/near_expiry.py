# app/detectors/near_expiry.py
#
# Detects products approaching expiry.
#
# Build Plan Section 3.17:
#   Trigger: expiry_risk_score >= 0.8  (last 20% of shelf life)
#            AND current_stock > 0     (no point flagging if already out of stock)
#
# What changed from ChatGPT version:
#   - Was: days_to_expiry <= 7  (fixed days — wrong for long shelf-life products)
#   - Now: expiry_risk_score >= NEAR_EXPIRY_RISK_SCORE (0.8)
#     Example: biscuits (90d shelf) → triggers at 18 days left
#              atta (365d shelf)    → triggers at 73 days left
#              dairy (7d shelf)     → triggers at 1.4 days left

import pandas as pd
from inventory_painpoints_service.app.core.config import NEAR_EXPIRY_RISK_SCORE


def detect_near_expiry(df: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean Series — True where NEAR_EXPIRY pain point fires.
    """
    if "expiry_risk_score" not in df.columns:
        return pd.Series(False, index=df.index)

    return (
        (df["expiry_risk_score"] >= NEAR_EXPIRY_RISK_SCORE) &
        (df["current_stock"] > 0)
    )
