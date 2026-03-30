# app/detectors/composite_risk.py
#
# Computes composite_risk_score per (product_id, store_id).
# This is the primary output of M4 that feeds the Decision Engine.
#
# Build Plan Section 3.18:
#   composite_risk_score = weighted combination of individual risk signals
#   Result is clamped to [0.0, 1.0]
#
# Weights from config:
#   RISK_WEIGHT_EXPIRY   = 0.35
#   RISK_WEIGHT_VELOCITY = 0.25
#   RISK_WEIGHT_STOCK    = 0.25
#   RISK_WEIGHT_RETURN   = 0.15
#
# Decision Engine Section 3.5.5 then combines this with news urgency_score:
#   action_priority_score = 0.35 * composite_risk_score
#                         + 0.30 * urgency_score        ← from M3 news pipeline
#                         + 0.20 * expiry_urgency
#                         + 0.15 * return_rate_30d

import pandas as pd
import numpy as np
from inventory_painpoints_service.app.core.config import (
    RISK_WEIGHT_EXPIRY,
    RISK_WEIGHT_VELOCITY,
    RISK_WEIGHT_STOCK,
    RISK_WEIGHT_RETURN,
    STAGNANT_VELOCITY_RATIO,
    ACCELERATING_VELOCITY_RATIO,
)


def compute_composite_risk(
    df: pd.DataFrame,
    masks: dict,
) -> pd.Series:
    """
    Computes a composite_risk_score in [0.0, 1.0] for each product.

    Each component is normalised to 0..1 before weighting:
      - expiry_component   : expiry_risk_score (already 0..1)
      - velocity_component : how far below 1.0 the velocity ratio is
      - stock_component    : how far below reorder_level current stock is
      - return_component   : return_rate_30d (clamped at 1.0)
    """

    # ── Expiry component ─────────────────────────────────────────────────────
    expiry_component = df["expiry_risk_score"].clip(0.0, 1.0)

    # ── Velocity component ───────────────────────────────────────────────────
    # 0.0 = accelerating (velocity >= 1.3), 1.0 = completely stagnant (velocity = 0)
    velocity_component = (
        (ACCELERATING_VELOCITY_RATIO - df["sales_velocity_ratio"])
        / ACCELERATING_VELOCITY_RATIO
    ).clip(0.0, 1.0)

    # ── Stock component ──────────────────────────────────────────────────────
    # 0.0 = well stocked, 1.0 = zero stock
    # Normalised against reorder_level as reference
    def stock_risk(row):
        if row["reorder_level"] <= 0:
            return 0.0
        ratio = row["current_stock"] / row["reorder_level"]
        # ratio >= 2.0 = well stocked (risk 0), ratio = 0 = stockout (risk 1)
        return float(np.clip(1.0 - (ratio / 2.0), 0.0, 1.0))

    stock_component = df.apply(stock_risk, axis=1)

    # ── Return component ─────────────────────────────────────────────────────
    # return_rate_30d already 0..1 (capped at 1.0 just in case)
    return_component = df["return_rate_30d"].clip(0.0, 1.0)

    # ── Weighted sum ─────────────────────────────────────────────────────────
    score = (
        RISK_WEIGHT_EXPIRY   * expiry_component   +
        RISK_WEIGHT_VELOCITY * velocity_component  +
        RISK_WEIGHT_STOCK    * stock_component     +
        RISK_WEIGHT_RETURN   * return_component
    )

    return score.clip(0.0, 1.0).round(4)
