# app/modules/m7_xai/xai.py
#
# Module 7 — Explainable AI Layer entry point.
#
# Called by Decision Engine AFTER M5/M6 return their results.
# Wraps every recommendation with a 4-part explanation and saves
# to recommendations CSV (later: PostgreSQL recommendations table).
#
# Build Plan Section 3.30:
#   "Every single recommendation from every module is wrapped in a
#    structured four-part explanation before being logged."
#
# Flow:
#   For each recommendation from M5/M6:
#     1. Build trigger    (what activated it)
#     2. Build evidence   (feature values + SHAP)
#     3. Build reasoning  (why this action, not alternatives)
#     4. Build projection (expected outcome)
#     5. LLM generates one-sentence rationale grounded in SHAP
#     6. Assemble reason_json
#     7. Save to recommendations CSV

import os
import json
import pandas as pd
from datetime import datetime
from typing import List

from app.decision_engine.unified_signal import UnifiedSignal
from app.modules.m7_xai.shap_explainer import SHAPExplainer
from app.modules.m7_xai.reason_builder  import (
    build_trigger, build_evidence, build_reasoning, build_projection
)
from app.modules.m7_xai.llm_narrator    import generate_rationale

OUTPUT_PATH = "pipeline_output/recommendations.csv"


class XAILayer:

    def __init__(self,
                 xgb_model=None,
                 output_path: str = OUTPUT_PATH):
        """
        xgb_model  : trained XGBoost model for SHAP computation
        output_path: where to save recommendations CSV
        """
        self.shap_explainer = SHAPExplainer()
        self.output_path    = output_path

    def explain_and_save(self,
                          signal: UnifiedSignal,
                          recommendations: List[dict],
                          product_name: str = "") -> List[dict]:
        """
        Main entry point.
        Takes raw M5/M6 recommendation dicts and enriches each with:
          - reason_json  (4-part structured explanation)
          - rationale    (one LLM-generated sentence for manager)
          - projected_impact (already from M5/M6, passed through)

        Saves all enriched recommendations to CSV.
        Returns enriched list.
        """

        enriched = []

        for rec in recommendations:
            module      = rec.get("module", "")
            action_type = self._get_action_type(rec)

            # ── Build feature vector for SHAP ─────────────────────────────────
            feature_vector = rec.get("features_used", {})

            # ── Compute SHAP values ───────────────────────────────────────────
            shap_values = []

            if action_type == "PRICING" and rec.get("path") == "XGBOOST":
                shap_values = self.shap_explainer.compute(
                    feature_vector, signal.composite_risk_score
                )

            # ── Build 4-part explanation ──────────────────────────────────────
            trigger    = build_trigger(signal)
            evidence   = build_evidence(signal, shap_values)
            reasoning  = build_reasoning(action_type, rec, signal)
            projection = build_projection(action_type, rec)

            # ── LLM generates one-sentence rationale ─────────────────────────
            rationale = generate_rationale(
                action_type = action_type,
                trigger     = trigger,
                evidence    = evidence,
                reasoning   = reasoning,
                projection  = projection,
                shap_values = shap_values,
            )

            # ── Assemble reason_json (Section 3.33) ───────────────────────────
            reason_json = {
                "trigger":    trigger,
                "evidence":   evidence,
                "reasoning":  reasoning,
                "shap_values":shap_values,
            }

            # ── Build final enriched recommendation ───────────────────────────
            enriched_rec = {
                # Identity
                "product_id":            signal.product_id,
                "store_id":              signal.store_id,
                "product_name":          product_name,
                "created_at":            datetime.now().isoformat(),

                # Decision
                "action_type":           action_type,
                "module":                module,
                "action_priority_score": round(signal.action_priority_score, 4),
                "pain_points_triggered": json.dumps(signal.pain_points),

                # Recommended value (from M5/M6)
                "recommended_value":     json.dumps(
                    rec.get("recommended_value", {})
                ),

                # M7 explanation
                "reason_json":           json.dumps(reason_json),
                "rationale":             rationale,

                # Projected impact (from M5/M6, passed through)
                "projected_impact":      json.dumps(
                    rec.get("projected_impact", {})
                ),

                # Outcome — filled later when manager acts
                "acted_on":              False,
                "outcome_json":          None,
            }
            enriched.append(enriched_rec)

        # ── Save to CSV ───────────────────────────────────────────────────────
        self._save(enriched)

        return enriched
        return enriched

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_action_type(self, rec: dict) -> str:
        """Infer action type from module name."""
        module = rec.get("module", "")
        action = rec.get("action", "")

        if "M5" in module:
            return "LOGISTICS"
        elif "PRICING" in module:
            return "PRICING"
        elif "COMBO" in module:
            return "COMBO"
        elif action:
            return action
        return "UNKNOWN"
    

    def _build_feature_vector(self, signal: UnifiedSignal) -> dict:
        """Builds feature vector from UnifiedSignal for SHAP."""
        return {
            "current_price":        0.0,   # filled by pricing module
            "rolling_sales_7d":     signal.tft_forecast_7d or 0.0,
            "rolling_sales_30d":    (signal.tft_forecast_7d * (30/7))
                                    if signal.tft_forecast_7d else 0.0,
            "stock_to_sales_ratio": (signal.current_stock / signal.tft_forecast_7d)
                                    if signal.tft_forecast_7d and signal.tft_forecast_7d > 0
                                    else 9999.0,
            "seasonality_index":    1.0,
            "sales_velocity_ratio": signal.sales_velocity,
            "avg_daily_sales":      signal.tft_forecast_7d / 7
                                    if signal.tft_forecast_7d else 0.0,
            "expiry_risk_score":    max(0.0, 1.0 - signal.days_to_expiry / 365.0)
                                    if signal.days_to_expiry < 9999 else 0.0,
            "return_rate_30d":      signal.return_rate_30d,
            "category_encoded":     0.0,
        }

    def _save(self, enriched: List[dict]):
        print("\n[XAI] _save() called")

        if not enriched:
            print("[XAI] No enriched data → skipping save")
            return

        print(f"[XAI] Records to save: {len(enriched)}")

        try:
            dir_path = os.path.dirname(self.output_path)
            print(f"[XAI] Target directory: {dir_path}")

            os.makedirs(dir_path, exist_ok=True)
            print("[XAI] Directory ensured/created")

            print(f"[XAI] Full file path: {self.output_path}")

            df_new = pd.DataFrame(enriched)

            if os.path.exists(self.output_path):
                print("[XAI] Existing file found → appending")
                df_existing = pd.read_csv(self.output_path)
                df_out = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                print("[XAI] No existing file → creating new")
                df_out = df_new

            df_out.to_csv(self.output_path, index=False)
            print("[XAI] File saved successfully")

        except Exception as e:
            print(f"[XAI ERROR] Failed to save file: {e}")
