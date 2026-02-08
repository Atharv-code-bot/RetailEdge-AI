# app/detectors/declining_sales.py

import pandas as pd
from app.core.config import DECLINING_SALES_PCT


def detect_declining_sales(df: pd.DataFrame) -> pd.DataFrame:
    result = df[df["sales_change_pct"] <= DECLINING_SALES_PCT].copy()

    result["issue_type"] = "DECLINING_SALES"
    result["severity"] = "HIGH"
    result["explanation"] = (
        "Sales dropped significantly compared to previous period"
    )

    return result
