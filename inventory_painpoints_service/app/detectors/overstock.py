# app/detectors/overstock.py

import pandas as pd
from app.core.config import OVERSTOCK_DAYS


def detect_overstock(df: pd.DataFrame) -> pd.DataFrame:
    result = df[df["days_of_stock"] >= OVERSTOCK_DAYS].copy()

    result["issue_type"] = "OVERSTOCK"
    result["severity"] = "MEDIUM"
    result["explanation"] = "Excess inventory relative to demand"

    return result
