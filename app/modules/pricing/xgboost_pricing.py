
#
# Section 3.26 — Normal Pricing Path (XGBoost Regressor)
#
# HOW TO INTEGRATE YOUR EXISTING MODEL:
# ──────────────────────────────────────
# 1. Your trained XGBoost model (PricePredictor class) plugs into
#    XGBoostPricingPath.__init__() as the `model` parameter
# 2. Feature names must match FEATURE_COLS below
# 3. The rest of this file (constraints, PMS, output) stays as-is
#
# Build Plan Section 3.26:
#   Features : current_price, rolling_sales_7d, rolling_sales_30d,
#              stock_to_sales_ratio, seasonality_index, category
#   Output   : optimal_price_normal
#   Constraint: [cost_price * 1.02, base_selling_price * 1.5]
#
# Build Plan Section 3.27 (fairness):
#   PMS = (recommended_price - base_price * 1.3) / base_price
#   If PMS > 0.1 → clip to base * 1.3, flag as fairness-constrained

from pyexpat import features

import numpy as np
from decision_engine.unified_signal import UnifiedSignal

# ── Feature columns expected by XGBoost model ────────────────────────────────
# These match product_analysis.csv column names
# Your existing model must be trained on these same features
FEATURE_COLS = [
    "current_price",          # base_selling_price from products table
    "rolling_sales_7d",       # from product_analysis
    "rolling_sales_30d",      # from product_analysis
    "stock_to_sales_ratio",   # from product_analysis
    "seasonality_index",      # from product_analysis
    "sales_velocity_ratio",   # from product_analysis
    "avg_daily_sales",        # from product_analysis
    "expiry_risk_score",      # from product_analysis
    "return_rate_30d",        # from product_analysis
]

# ── Price constraints (Build Plan Section 3.26) ───────────────────────────────
MIN_MARGIN_FACTOR = 1.02   # never sell below cost + 2%
MAX_PRICE_FACTOR  = 1.50   # never above 1.5x base price

# ── Fairness constraint (Build Plan Section 3.27) ─────────────────────────────
PMS_THRESHOLD     = 0.10   # price manipulation score limit
PMS_PRICE_FACTOR  = 1.30   # clip to 1.3x base if PMS exceeded


class XGBoostPricingPath:
    """
    Normal pricing path — XGBoost Regressor.

    HOW TO PLUG IN YOUR EXISTING MODEL:
    ──────────────────────────────────── 

    model, metrics = load_model("path/to/model.pkl")
    xgb_path = XGBoostPricingPath(model=model, metrics=metrics)

    The model must implement: model.predict(feature_array) → [price]
    The model must expose  : model.feature_importances_  (for explain)
    """
    

    def __init__(self, model=None, metrics=None):
        # ── Plug your existing model here ─────────────────────────────────────
        # model   : trained XGBoost model (sklearn-compatible)
        # metrics : dict with "rmse" and "r2" keys
        self.model   = model
        self.metrics = metrics or {"rmse": None, "r2": None}

    def predict(self, signal: UnifiedSignal, product_info: dict) -> dict:
        """
        Predicts optimal price using XGBoost.

        product_info needs:
            cost_price, base_selling_price, name, category
        """

        cost_price  = product_info.get("cost_price",          0)
        base_price  = product_info.get("base_selling_price",  0)
        category    = product_info.get("category",            "unknown")

        # ── Build feature vector ──────────────────────────────────────────────
        features = self._build_features(signal, base_price, category)

        # ── Get price prediction ──────────────────────────────────────────────
        if self.model is not None:
            feature_vector = [features[col] for col in FEATURE_COLS]
            predicted_raw = self.model.predict([feature_vector])[0]
        else:
            predicted_raw = self._rule_based_fallback(signal, base_price)

        # ── Apply build plan constraints ──────────────────────────────────────
        recommended_price = self._apply_constraints(
            predicted_raw, cost_price, base_price, signal
        )

        # ── Price Manipulation Score (fairness) ───────────────────────────────
        pms, fairness_clipped = self._compute_pms(recommended_price, base_price)
        if fairness_clipped:
            recommended_price = round(base_price * PMS_PRICE_FACTOR, 2)

        # ── Direction ─────────────────────────────────────────────────────────
        direction = self._get_direction(recommended_price, base_price)

        # ── Price change % ────────────────────────────────────────────────────
        price_change_pct = round(
            (recommended_price - base_price) / base_price * 100, 2
        )

        # ── Expected revenue ──────────────────────────────────────────────────
        demand_7d = signal.tft_forecast_7d or 0.0
        expected_revenue = round(recommended_price * demand_7d, 2)

        # ── Feature importance explanation ────────────────────────────────────

        return {
            "path":               "XGBOOST",
            "recommended_price":  recommended_price,
            "original_price":     base_price,
            "price_direction":    direction,
            "price_change_pct":   price_change_pct,
            "expected_revenue_7d":expected_revenue,
            "price_manip_score":  round(pms, 4),
            "fairness_clipped":   fairness_clipped,
            "model_metrics":      self.metrics,
            "features_used":      features,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_features(self, signal: UnifiedSignal,
                        base_price: float, category: str) -> dict:
        """Builds feature dict matching FEATURE_COLS."""
        return {
            "current_price":        base_price,
            "rolling_sales_7d":     signal.tft_forecast_7d or 0.0,
            "rolling_sales_30d":    signal.tft_forecast_7d * (30/7) if signal.tft_forecast_7d else 0.0,
            "stock_to_sales_ratio": (signal.current_stock / signal.tft_forecast_7d
                                     if signal.tft_forecast_7d > 0 else 9999.0),
            "seasonality_index":    1.0,   # from product_analysis if available
            "sales_velocity_ratio": signal.sales_velocity,
            "avg_daily_sales":      signal.tft_forecast_7d / 7 if signal.tft_forecast_7d else 0.0,
            "expiry_risk_score":    1.0 - (signal.days_to_expiry / 365.0)
                                    if signal.days_to_expiry < 9999 else 0.0,
            "return_rate_30d":      signal.return_rate_30d,
        }

    def _rule_based_fallback(self, signal: UnifiedSignal,
                             base_price: float) -> float:
        """
        Rule-based price suggestion when no XGBoost model is loaded.
        Used until your model is integrated.
        Mirrors the logic your PricePredictor would produce.
        """
        adjustment = 0.0

        # Velocity-based adjustment
        if signal.sales_velocity > 1.3:
            adjustment += 0.05    # accelerating — slight increase
        elif signal.sales_velocity < 0.7:
            adjustment -= 0.08    # stagnant — slight decrease

        # Stock pressure
        if signal.current_stock <= signal.reorder_level:
            adjustment += 0.03    # low stock — minor increase
        elif signal.current_stock > signal.reorder_level * 3:
            adjustment -= 0.05    # overstock — push sales

        # Expiry pressure
        if signal.days_to_expiry < 7:
            adjustment -= 0.20    # urgent clearance
        elif signal.days_to_expiry < 14:
            adjustment -= 0.10    # moderate clearance

        # Return rate pressure
        if signal.return_rate_30d > 0.10:
            adjustment -= 0.05    # quality issue — lower price

        return round(base_price * (1 + adjustment), 2)

    def _apply_constraints(self, predicted: float,
                           cost_price: float, base_price: float,
                           signal: UnifiedSignal) -> float:
        """
        Build Plan Section 3.26 constraints:
          min: cost_price * 1.02
          max: base_selling_price * 1.5

        Also applies logistics-aware constraints
        (from your existing PricePredictor.apply_constraints):
          MARKDOWN context  → never raise above base_price
          LOW_STOCK context → never drop below base_price
        """
        min_price = round(cost_price * MIN_MARGIN_FACTOR, 2)
        max_price = round(base_price * MAX_PRICE_FACTOR,  2)

        constrained = float(np.clip(predicted, min_price, max_price))

        # Logistics-aware constraints (from your existing code)
        if "NEAR_EXPIRY" in signal.pain_points or "HIGH_RETURN" in signal.pain_points:
            constrained = min(constrained, base_price)   # never raise during clearance

        if "LOW_STOCK" in signal.pain_points:
            constrained = max(constrained, base_price)   # never drop during shortage

        return round(constrained, 2)

    def _compute_pms(self, recommended_price: float,
                     base_price: float) -> tuple:
        """
        Price Manipulation Score (Build Plan Section 3.27).
        PMS > 0.1 → clip and flag.
        """
        if base_price <= 0:
            return 0.0, False

        pms = (recommended_price - base_price * PMS_PRICE_FACTOR) / base_price
        fairness_clipped = pms > PMS_THRESHOLD

        return float(pms), fairness_clipped

    def _get_direction(self, recommended: float, base: float) -> str:
        if recommended > base * 1.02:
            return "INCREASE"
        elif recommended < base * 0.98:
            return "DECREASE"
        return "STABLE"

    def _get_logistics_context(self, signal: UnifiedSignal) -> str:
        """Maps pain points to logistics_decision string your PricePredictor uses."""
        if "NEAR_EXPIRY" in signal.pain_points:
            return "MARKDOWN"
        if "LOW_STOCK" in signal.pain_points:
            return "URGENT_RESTOCK"
        return "STABLE"

    # Feature importance explanation moved to Module 7 (XAI layer)
