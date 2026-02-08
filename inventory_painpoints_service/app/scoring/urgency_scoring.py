# app/scoring/urgency_scoring.py

import pandas as pd
from app.core.config import URGENCY_WEIGHTS, SEVERITY_MULTIPLIER


def compute_urgency_scores(pain_points_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes urgency score per (product_id, store_id)
    based on detected pain points.
    """

    if pain_points_df.empty:
        return pd.DataFrame()

    df = pain_points_df.copy()

    # Base urgency per issue
    df["base_urgency"] = df["issue_type"].map(URGENCY_WEIGHTS).fillna(0)

    # Severity-adjusted urgency
    df["severity_factor"] = df["severity"].map(SEVERITY_MULTIPLIER).fillna(1.0)
    df["issue_urgency"] = df["base_urgency"] * df["severity_factor"]

    # Aggregate per product-store
    urgency = (
        df.groupby(["product_id", "store_id"])
        .agg(
            urgency_score=("issue_urgency", "sum"),
            issues=("issue_type", lambda x: list(set(x))),
            max_severity=("severity", lambda x: x.iloc[0]),
        )
        .reset_index()
    )

    # Cap urgency score at 100
    urgency["urgency_score"] = urgency["urgency_score"].clip(upper=100)

    return urgency
