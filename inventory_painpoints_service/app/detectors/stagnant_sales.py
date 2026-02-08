# app/detectors/stagnant_sales.py

import pandas as pd
from app.core.config import STAGNANT_SALES_THRESHOLD


def detect_stagnant_sales(df: pd.DataFrame) -> pd.DataFrame:
    result = df[
        (df["avg_daily_sales"] > 0)
        & (df["avg_daily_sales"] <= STAGNANT_SALES_THRESHOLD)
    ].copy()

    result["issue_type"] = "STAGNANT_SALES"
    result["severity"] = "MEDIUM"
    result["explanation"] = "Sales volume is consistently low"

    return result
