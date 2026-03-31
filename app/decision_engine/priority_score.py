# app/decision_engine/priority_score.py
#
# Section 3.5.5 — Action Priority Score
#
# Computes action_priority_score for each UnifiedSignal.
# This determines the ORDER in which products are processed —
# highest score = processed first = appears at top of dashboard.
#
# Formula (Build Plan Section 3.5.5):
#   action_priority_score =
#     0.35 * composite_risk_score    ← how dangerous is inventory situation
#   + 0.30 * urgency_score           ← how strong is external news signal
#   + 0.20 * expiry_urgency          ← how close to expiry
#   + 0.15 * return_rate_30d         ← how bad are returns
#
# expiry_urgency = 1.0 - (days_to_expiry / shelf_life_days) clamped 0..1
# For non-perishables: days_to_expiry=9999 → expiry_urgency=0.0

import numpy as np
from decision_engine.unified_signal import UnifiedSignal


def compute_action_priority_score(signal: UnifiedSignal,
                                   shelf_life_days: int = 9999) -> float:
    """
    Computes action_priority_score for a single UnifiedSignal.
    Returns float clamped to [0.0, 1.0].

    shelf_life_days: from products table — needed for expiry_urgency formula.
                     Defaults to 9999 (non-perishable) if not provided.
    """

    # ── expiry_urgency ────────────────────────────────────────────────────────
    # Non-perishables: days_to_expiry=9999, shelf_life=9999 → urgency=0.0
    if signal.days_to_expiry == 9999 or shelf_life_days == 9999:
        expiry_urgency = 0.0
    else:
        raw = 1.0 - (signal.days_to_expiry / shelf_life_days)
        expiry_urgency = float(np.clip(raw, 0.0, 1.0))

    # ── action_priority_score formula (Section 3.5.5) ────────────────────────
    score = (
        0.35 * signal.composite_risk_score
      + 0.30 * signal.urgency_score
      + 0.20 * expiry_urgency
      + 0.15 * signal.return_rate_30d
    )

    return float(np.clip(score, 0.0, 1.0))


def sort_by_priority(signals: list) -> list:
    """
    Sorts UnifiedSignal list by action_priority_score descending.
    Highest priority products processed first.
    """
    return sorted(signals, key=lambda s: s.action_priority_score, reverse=True)
