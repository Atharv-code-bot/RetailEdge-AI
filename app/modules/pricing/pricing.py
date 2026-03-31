

import pandas as pd
import joblib  # ✅ added
from app.decision_engine.unified_signal import UnifiedSignal
from pricing.xgboost_pricing import XGBoostPricingPath
from pricing.llm_pricing     import LLMPricingPath

# Urgency threshold for LLM path
LLM_URGENCY_THRESHOLD = 0.5


class PricingModule:

    def __init__(self,
                 products_path: str,
                 xgb_model=None,
                 xgb_metrics=None):
        """
        products_path : path to products.csv
        xgb_model     : your trained XGBoost model (optional — uses fallback if None)
        xgb_metrics   : dict with rmse, r2 (optional)
        """

        self.products_df = pd.read_csv(products_path)

        # ✅ ONLY CHANGE: auto-load model if not passed
        if xgb_model is None:
            MODEL_PATH = r"pricing\models\predictify_xgb_model.pkl"
            bundle = joblib.load(MODEL_PATH)
            xgb_model = bundle["model"]
            xgb_metrics = bundle["metrics"]

        self.xgb_path = XGBoostPricingPath(
            model=xgb_model,
            metrics=xgb_metrics
        )

        self.llm_path = LLMPricingPath()

    async def run(self, signal: UnifiedSignal) -> dict:

        product_info = self._get_product_info(signal.product_id)

        # Path selection
        if signal.urgency_score > LLM_URGENCY_THRESHOLD:
            result = self.llm_path.predict(signal, product_info)
        else:
            result = self.xgb_path.predict(signal, product_info)

        # Add product context
        result["product_id"]   = signal.product_id
        result["store_id"]     = signal.store_id
        result["product_name"] = product_info.get("name", f"product_{signal.product_id}")
        result["module"]       = "M6_PRICING"

        return result

    # ── Helpers ───────────────────────────────────────────────

    def _get_product_info(self, product_id: int) -> dict:
        row = self.products_df[self.products_df["id"] == product_id]

        if row.empty:
            return {
                "name": f"product_{product_id}",
                "cost_price": 0,
                "base_selling_price": 0,
                "category": "unknown",
            }

        r = row.iloc[0]

        return {
            "name":               str(r["name"]),
            "cost_price":         float(r["cost_price"]),
            "base_selling_price": float(r["base_selling_price"]),
            "category":           str(r["category"]),
        }
    


# ── ─────────────────────────────────────────────────────────────────────── ──
# SPACE FOR PART B — COMBO MODULE
# ── ─────────────────────────────────────────────────────────────────────── ──
#
# When m6_combo is built, the Decision Engine calls it separately:
#
#   from app.modules.m6_combo.combo import ComboModule
#
#   combo_module = ComboModule(
#       products_path = "...",
#       sales_path    = "...",   # for FP-Growth
#   )
#
#   # In engine.py _call_m6_combo():
#   result = await combo_module.run(signal)
#
# Combo runs in PARALLEL with pricing via asyncio.gather()
# No dependency between pricing result and combo result
# ── ─────────────────────────────────────────────────────────────────────── ──
