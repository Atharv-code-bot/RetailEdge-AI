# app/detectors/seasonal_mismatch.py

import pandas as pd
from app.core.config import SEASONAL_DROP_PCT


def detect_seasonal_mismatch(df: pd.DataFrame) -> pd.DataFrame:
    result = df[df["sales_change_pct"] <= SEASONAL_DROP_PCT].copy()

    result["issue_type"] = "SEASONAL_MISMATCH"
    result["severity"] = "MEDIUM"
    result["explanation"] = "Demand dropped sharply in current season"

    return result
