# app/decision_engine/engine.py
#
# Decision Engine — runs per product on manager query.
#
# Flow (Section 3.5.8):
#   1. Fetch product row from product_analysis.csv (DB later)
#   2. Fetch external signal from Reddit module (live)
#   3. Build UnifiedSignal (combine both)
#   4. Compute action_priority_score
#   5. Route → action_types
#   6. Resolve conflicts
#   7. Dispatch M5 / M6 / M7 in PARALLEL (independent of each other)
#   8. Return all results
#
# M5 / M6 / M7 are stubbed — replace stub functions when modules are built.
# Each module returns independently — no module waits for another.

import os
import json
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

from decision_engine.unified_signal    import UnifiedSignal, build_unified_signal
from decision_engine.priority_score    import compute_action_priority_score
from decision_engine.routing_rules     import determine_action_types
from decision_engine.conflict_resolver import resolve_conflicts
from app.modules.logistics import logistics
from external_signal_service.main import reddit_trend as fetch_external_signal


# ─────────────────────────────────────────────────────────────────────────────
# EXTERNAL SIGNAL ADAPTER
# Calls Reddit module and converts output to urgency_score + news_sentiment.
# Replace the stub with real HTTP call when Reddit module is connected.
# ─────────────────────────────────────────────────────────────────────────────

# def fetch_external_signal(product_name: str) -> dict:
#     """
#     Fetches urgency_score and news_sentiment for a product.

#     Currently stubbed — returns neutral signal.
#     When Reddit module is connected:
#         import requests
#         response = requests.post("http://localhost:8001/reddit-trend", json={
#             "product_name": product_name,
#             "days_window": 7,
#             "subreddits": ["india", "indianfood", "IndianStockMarket"]
#         })
#         signals = response.json()["external_signals"]
#         return _convert_reddit_signals(signals)
#     """

#     # ── STUB ──────────────────────────────────────────────────────────────────
#     return {
#         "urgency_score":   0.0,
#         "news_sentiment":  "NEUTRAL",
#     }


# def _convert_reddit_signals(signals: dict) -> dict:
#     """
#     Converts Reddit module output → Decision Engine format.
#     Build Plan Section 3.12 urgency formula:
#       urgency = abs(sentiment) × mention_frequency_weight × confidence
#     """
#     avg_sentiment    = signals.get("average_sentiment", 0.0)
#     mention_volume   = signals.get("mention_volume", 0)
#     confidence_score = signals.get("confidence_score", 0.0)

#     # Sentiment direction
#     if avg_sentiment > 0.05:
#         news_sentiment = "POSITIVE"
#     elif avg_sentiment < -0.05:
#         news_sentiment = "NEGATIVE"
#     else:
#         news_sentiment = "NEUTRAL"

#     # Urgency score formula
#     mention_weight = min(mention_volume / 10, 1.0)
#     urgency_score  = abs(avg_sentiment) * mention_weight * confidence_score
#     urgency_score  = float(np.clip(urgency_score, 0.0, 1.0))

#     return {
#         "urgency_score":  urgency_score,
#         "news_sentiment": news_sentiment,
#     }




# ─────────────────────────────────────────────────────────────────────────────
# MODULE STUBS
# Replace each stub with the real module call when M5 / M6 are built.
# Each function receives a UnifiedSignal and returns a result dict.
# They run in PARALLEL — none waits for another.
# ─────────────────────────────────────────────────────────────────────────────

async def _call_m5_logistics(signal: UnifiedSignal, needs_reverse: bool) -> dict:
    """
    M5 — Logistics Intelligence (Section 3.20 - 3.24)
    Calls real LogisticsModule.run()
    """
    if logistics is None:
        return {"module": "M5_LOGISTICS", "error": "M5 not initialised"}
    result = await logistics.run(signal, needs_reverse=needs_reverse)
    result["module"] = "M5_LOGISTICS"
    return result

async def _call_m6_pricing(signal: UnifiedSignal,
                              m6_pricing_instance=None) -> dict:
    """
    M6 — Dynamic Pricing (Section 3.25 - 3.27)
    Calls real PricingModule.run()
    """
    if m6_pricing_instance is None:
        return {"module": "M6_PRICING", "error": "M6 not initialised"}
    result = await m6_pricing_instance.run(signal)
    return result


async def _call_m6_combo(signal: UnifiedSignal,
                          m6_combo_instance=None) -> dict:
    """M6 — Combo Offer Generator. Calls real ComboModule.run()"""
    if m6_combo_instance is None:
        return {"module": "M6_COMBO", "error": "M6 combo not initialised"}
    result = await m6_combo_instance.run(signal)
    return result


async def _write_monitor_record(signal: UnifiedSignal) -> dict:
    """MONITOR — no module call, just log."""
    return {
        "module":            "MONITOR",
        "recommended_value": {
            "reason": "urgency between 0.3-0.6, no pain points — watch only"
        },
        "projected_impact":  None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DECISION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class DecisionEngine:

    def __init__(self, product_analysis_path: str, products_path: str):
        self.product_analysis_path = product_analysis_path
        self.products_path         = products_path

    async def run_for_product(self, product_id: int) -> dict:
        """
        Main entry point — called per manager query.

        1. Fetch product row from product_analysis.csv
        2. Fetch external signal (Reddit — stubbed)
        3. Build UnifiedSignal
        4. Compute action_priority_score
        5. Route → action_types
        6. Resolve conflicts
        7. Dispatch M5/M6/M7 in PARALLEL
        8. Return all results
        """

        start = datetime.now()

        # ── Step 1: Fetch product row ─────────────────────────────────────────
        product_row, product_name, shelf_life = self._fetch_product_row(product_id)

        if product_row is None:
            return {
                "error": f"product_id {product_id} not found in product_analysis"
            }

        # ── Step 2: Fetch external signal (Reddit module) ────────────────────
        external = fetch_external_signal(product_name)

        # ── Step 3: Build UnifiedSignal ───────────────────────────────────────
        signal = build_unified_signal(
            row            = product_row,
            urgency_score  = external["urgency_score"],
            news_sentiment = external["news_sentiment"],
        )

        # ── Step 4: Compute action_priority_score ─────────────────────────────
        signal.action_priority_score = compute_action_priority_score(
            signal, shelf_life_days=shelf_life
        )

        # ── Step 5: Route ─────────────────────────────────────────────────────
        action_types = determine_action_types(signal)

        if not action_types:
            return self._build_response(
                product_id     = product_id,
                product_name   = product_name,
                signal         = signal,
                action_types   = [],
                module_results = [],
                conflicts      = {},
                elapsed        = (datetime.now() - start).total_seconds(),
                skipped        = True,
            )

        # ── Step 6: Resolve conflicts ─────────────────────────────────────────
        resolution   = resolve_conflicts(signal, action_types)
        action_types = resolution["action_types"]

        # ── Step 7: Dispatch M5/M6/M7 in PARALLEL ────────────────────────────
        # Each module runs independently — none waits for another
        tasks = []
        for action_type in action_types:
            if action_type == "LOGISTICS":
                tasks.append(_call_m5_logistics(signal, resolution["needs_reverse"]))
            elif action_type == "PRICING":
                tasks.append(_call_m6_pricing(signal))
            elif action_type == "COMBO":
                tasks.append(_call_m6_combo(signal))
            elif action_type == "MONITOR":
                tasks.append(_write_monitor_record(signal))

        # Run all tasks concurrently — asyncio.gather fires them all at once
        module_results = await asyncio.gather(*tasks)

        # ── Step 8: Return results ────────────────────────────────────────────
        elapsed = (datetime.now() - start).total_seconds()
        return self._build_response(
            product_id     = product_id,
            product_name   = product_name,
            signal         = signal,
            action_types   = action_types,
            module_results = list(module_results),
            conflicts      = resolution,
            elapsed        = elapsed,
            skipped        = False,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_product_row(self, product_id: int):
        """
        Fetches one product row from product_analysis.csv.
        Also gets product_name and shelf_life_days from products.csv.
        Later: replace with PostgreSQL SELECT.
        """
        analysis_df = pd.read_csv(self.product_analysis_path)
        products_df = pd.read_csv(self.products_path)

        row = analysis_df[analysis_df["product_id"] == product_id]
        if row.empty:
            return None, None, 9999

        row_dict = row.iloc[0].to_dict()

        # Get product name and shelf life
        prod = products_df[products_df["id"] == product_id]
        if prod.empty:
            return row_dict, f"product_{product_id}", 9999

        product_name = prod.iloc[0]["name"]
        shelf_life   = prod.iloc[0]["shelf_life_days"]
        shelf_life   = int(shelf_life) if shelf_life == shelf_life else 9999

        return row_dict, product_name, shelf_life

    def _build_response(self, product_id, product_name, signal,
                        action_types, module_results, conflicts,
                        elapsed, skipped) -> dict:
        """Builds the final API response."""
        return {
            "product_id":            product_id,
            "product_name":          product_name,
            "store_id":              signal.store_id,
            "run_at":                datetime.now().isoformat(),
            "elapsed_ms":            round(elapsed * 1000, 1),

            # Signal inputs
            "composite_risk_score":  round(signal.composite_risk_score, 4),
            "action_priority_score": round(signal.action_priority_score, 4),
            "pain_points":           signal.pain_points,
            "urgency_score":         round(signal.urgency_score, 4),
            "news_sentiment":        signal.news_sentiment,
            "days_to_expiry":        signal.days_to_expiry,
            "current_stock":         signal.current_stock,
            "sales_velocity_ratio":  round(signal.sales_velocity, 4),
            "return_rate_30d":       round(signal.return_rate_30d, 4),

            # Decision
            "skipped":               skipped,
            "action_types":          action_types,
            "conflicts_resolved":    conflicts.get("conflicts_resolved", 0),
            "conflict_log":          conflicts.get("conflict_log", []),

            # Module outputs (M5/M6/M7 — stubbed, real values when modules built)
            "recommendations":       list(module_results),
        }