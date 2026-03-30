# app/decision_engine/routing_rules.py
#
# Section 3.5.6 — Action Type Routing Rules
#
# Determines which action type(s) to trigger for each UnifiedSignal.
# Rules evaluated in order — a product can trigger MULTIPLE action types.
#
# Action types:
#   ACQUIRE   — product found in news but not in DB → procurement signal
#   LOGISTICS — physical movement (forward restock or reverse transfer/markdown)
#   PRICING   — price adjustment (XGBoost normal or LLM urgent)
#   COMBO     — bundle offer generation
#   MONITOR   — no action, just watch
#
# Build Plan Section 3.5.6 routing table implemented exactly.

from typing import List
from decision_engine.app.unified_signal import UnifiedSignal


def determine_action_types(signal: UnifiedSignal) -> List[str]:
    """
    Returns list of action types to trigger for this signal.
    Evaluated in priority order — ACQUIRE short-circuits all others.
    """

    action_types = []

    # ── Rule 1: ACQUIRE — product not in DB, found in news ───────────────────
    # Short-circuits all other rules
    if signal.procurement_flag:
        return ["ACQUIRE"]

    # ── Rule 2: Positive news + accelerating sales ────────────────────────────
    # Forward logistics + possibly pricing
    if (signal.urgency_score > 0.6
            and signal.news_sentiment == "POSITIVE"
            and signal.sales_velocity > 1.0):
        action_types.append("LOGISTICS")        # forward path
        if signal.urgency_score > 0.6:
            action_types.append("PRICING")      # may also adjust price upward

    # ── Rule 3: Negative news ─────────────────────────────────────────────────
    # Reverse logistics + LLM pricing path
    elif (signal.urgency_score > 0.6
            and signal.news_sentiment == "NEGATIVE"):
        action_types.append("LOGISTICS")        # reverse path
        action_types.append("PRICING")          # LLM pricing path fires

    # ── Rule 4: Near expiry or high returns ───────────────────────────────────
    # Reverse logistics + combo to bundle expiring stock
    if ("NEAR_EXPIRY" in signal.pain_points
            or "HIGH_RETURN" in signal.pain_points):
        if "LOGISTICS" not in action_types:
            action_types.append("LOGISTICS")    # reverse path
        if "COMBO" not in action_types:
            action_types.append("COMBO")        # bundle to clear stock

    # ── Rule 5: Low stock + low urgency ──────────────────────────────────────
    # Forward logistics only (moderate priority)
    if ("LOW_STOCK" in signal.pain_points
            and signal.urgency_score < 0.6):
        if "LOGISTICS" not in action_types:
            action_types.append("LOGISTICS")    # forward path, moderate priority

    # ── Rule 6: Stagnant sales + low urgency ─────────────────────────────────
    # Combo to clear + XGBoost pricing
    if ("STAGNANT" in signal.pain_points
            and signal.urgency_score < 0.3):
        if "COMBO" not in action_types:
            action_types.append("COMBO")
        if "PRICING" not in action_types:
            action_types.append("PRICING")      # XGBoost path only

    # ── Rule 7: Seasonal mismatch ─────────────────────────────────────────────
    if "SEASONAL_MISMATCH" in signal.pain_points:
        if "PRICING" not in action_types:
            action_types.append("PRICING")      # XGBoost seasonal adjustment
        # Also trigger logistics if severe
        if signal.composite_risk_score > 0.5:
            if "LOGISTICS" not in action_types:
                action_types.append("LOGISTICS")

    # ── Rule 8: Medium urgency, no pain points → MONITOR ─────────────────────
    if (not action_types
            and 0.3 <= signal.urgency_score <= 0.6
            and not signal.pain_points):
        action_types.append("MONITOR")

    # ── Rule 9: Low urgency, no pain points → no action ──────────────────────
    if (not action_types
            and signal.urgency_score < 0.3
            and not signal.pain_points):
        return []   # skip entirely

    # ── Default: if pain points exist but no rule fired → MONITOR ────────────
    if not action_types and signal.pain_points:
        action_types.append("MONITOR")

    return action_types
