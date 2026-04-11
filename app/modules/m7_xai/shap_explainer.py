# app/modules/m7_xai/shap_explainer.py
#
# Section 3.32 — SHAP Integration
#
# Computes SHAP values for XGBoost pricing decisions.
# Extracts top 3 features + their contribution direction.
# These values are passed to the LLM narrator to ground
# the natural language rationale in actual model attribution.
#
# Build Plan Section 3.32:
#   "The LLM receives SHAP values as part of its prompt.
#    This grounds the LLM output in actual model attribution —
#    preventing hallucinated reasons."
#
# Build Plan Section 3.34 (performance note):
#   "Compute SHAP only for recommendations above confidence threshold.
#    Use cached background dataset for TreeExplainer."

import numpy as np
from typing import List, Optional
from app.core.config import PRICING_MODEL_PATH
import shap
import joblib

# SHAP computation threshold — only compute for high enough risk products
SHAP_MIN_RISK_SCORE = 0.2

# Feature names matching xgboost_pricing.py FEATURE_COLS
FEATURE_NAMES = [
    "current_price",
    "rolling_sales_7d",
    "rolling_sales_30d",
    "stock_to_sales_ratio",
    "seasonality_index",
    "sales_velocity_ratio",
    "avg_daily_sales",
    "expiry_risk_score",
    "return_rate_30d",
    "category_encoded",
]


class SHAPExplainer:

    def __init__(self,):
        """
        model: trained XGBoost model.
               If None, SHAP computation is skipped.
        """
        self.model = None
        self._init_explainer()

    

    def _init_explainer(self):
        print("\n[SHAP INIT] Initializing SHAP Explainer...")

        if self.model is None:
            try:
                print(f"[SHAP INIT] Loading model from: {PRICING_MODEL_PATH}")
                self.model = joblib.load(PRICING_MODEL_PATH)

                # ✅ FIX: extract actual model if dict
                if isinstance(self.model, dict):
                    print("[SHAP INIT] Model is dict → extracting 'model' key")
                    self.model = self.model.get("model")

                print("[SHAP INIT] Model loaded successfully")
                print(f"[SHAP INIT] Model type: {type(self.model)}")

            except Exception as e:
                print(f"[SHAP INIT ERROR] Model load failed: {e}")
                return
        else:
            print("[SHAP INIT] Model already provided externally")

        try:
            print("[SHAP INIT] Creating TreeExplainer...")
            self.explainer = shap.TreeExplainer(self.model)
            print("[SHAP INIT] TreeExplainer created successfully")
        except Exception as e:
            print(f"[SHAP INIT ERROR] TreeExplainer init failed: {e}")
            self.explainer = None

    def compute(self, feature_vector: dict,
                composite_risk_score: float) -> List[dict]:

            print("\n[SHAP] compute() called")

            # Skip SHAP for low-risk products
            print(f"[SHAP] composite_risk_score: {composite_risk_score}")
            if composite_risk_score < SHAP_MIN_RISK_SCORE:
                print("[SHAP] Skipping SHAP → low risk")
                return []

            if self.explainer is None:
                print("[SHAP] Explainer is None → using fallback")
                return self._fallback_importance(feature_vector)

            try:
                print("[SHAP] Building feature array...")
                if not feature_vector:
                    return []

                feature_array = np.array(
                    [feature_vector.get(f, 0.0) for f in FEATURE_NAMES]
                ).reshape(1, -1)
                print(f"[SHAP] Feature array: {feature_array}")

                print("[SHAP] Running SHAP TreeExplainer...")
                shap_values = self.explainer.shap_values(feature_array)[0]

                print(f"[SHAP] Raw shap values: {shap_values}")

                # Get top 3 by absolute SHAP value
                top_indices = np.argsort(np.abs(shap_values))[::-1][:3]
                print(f"[SHAP] Top feature indices: {top_indices}")

                result = []
                for idx in top_indices:
                    val = float(shap_values[idx])
                    print(f"[SHAP] Feature: {FEATURE_NAMES[idx]} | Value: {val}")

                    result.append({
                        "feature":    FEATURE_NAMES[idx],
                        "shap_value": round(val, 4),
                        "direction":  "+" if val > 0 else "-",
                        "raw_value":  round(
                            float(feature_vector.get(FEATURE_NAMES[idx], 0.0)), 4
                        ),
                    })

                print(f"[SHAP] Final SHAP result: {result}")
                return result

            except Exception as e:
                print(f"[SHAP ERROR] {e} → using fallback")
                return self._fallback_importance(feature_vector)


    def _fallback_importance(self, feature_vector: dict) -> List[dict]:
            print("\n[SHAP] Fallback importance used")

            importance = []

            expiry = feature_vector.get("expiry_risk_score", 0.0)
            if expiry > 0.0:
                print(f"[SHAP Fallback] expiry_risk_score: {expiry}")
                importance.append({
                    "feature":    "expiry_risk_score",
                    "shap_value": round(expiry * 0.35, 4),
                    "direction":  "+",
                    "raw_value":  round(expiry, 4),
                })

            velocity = feature_vector.get("sales_velocity_ratio", 1.0)
            if velocity < 0.8:
                print(f"[SHAP Fallback] sales_velocity_ratio: {velocity}")
                importance.append({
                    "feature":    "sales_velocity_ratio",
                    "shap_value": round((1.0 - velocity) * 0.25, 4),
                    "direction":  "-",
                    "raw_value":  round(velocity, 4),
                })

            ratio = feature_vector.get("stock_to_sales_ratio", 5.0)
            if ratio < 2.0:
                print(f"[SHAP Fallback] stock_to_sales_ratio: {ratio}")
                importance.append({
                    "feature":    "stock_to_sales_ratio",
                    "shap_value": round((2.0 - ratio) * 0.25, 4),
                    "direction":  "-",
                    "raw_value":  round(ratio, 4),
                })

            ret = feature_vector.get("return_rate_30d", 0.0)
            if ret > 0.05:
                print(f"[SHAP Fallback] return_rate_30d: {ret}")
                importance.append({
                    "feature":    "return_rate_30d",
                    "shap_value": round(ret * 0.15, 4),
                    "direction":  "+",
                    "raw_value":  round(ret, 4),
                })

            result = sorted(importance, key=lambda x: abs(x["shap_value"]),
                        reverse=True)[:3]

            print(f"[SHAP] Fallback result: {result}")
            return result