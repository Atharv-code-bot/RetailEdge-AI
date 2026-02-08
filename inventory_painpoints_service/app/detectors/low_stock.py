# app/detectors/low_stock.py

import pandas as pd
from app.core.config import LOW_STOCK_DAYS


def detect_low_stock(df: pd.DataFrame) -> pd.DataFrame:
    result = df[df["days_of_stock"] <= LOW_STOCK_DAYS].copy()

    result["issue_type"] = "LOW_STOCK"
    result["severity"] = "HIGH"
    result["explanation"] = "Inventory likely to run out soon"

    return result
