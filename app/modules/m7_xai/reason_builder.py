# app/modules/m7_xai/reason_builder.py
#
# Section 3.31 — The Four-Part Explanation Structure
#
# Builds structured reason_json for every recommendation.
# This is pure data assembly — no LLM here.
# LLM narrator (llm_narrator.py) converts this to natural language.
#
# The 4 parts:
#   trigger    → what activated this recommendation
#   evidence   → the supporting feature values
#   reasoning  → why this action over alternatives
#   projection → expected outcome

from typing import List
from app.decision_engine.unified_signal import UnifiedSignal


def build_trigger(signal: UnifiedSignal) -> dict:
    """
    Section 3.31 — Trigger component.
    What activated this recommendation.
    Sources: pain points + urgency score + composite risk.
    """
    triggers = []

    # Pain point triggers
    for pp in signal.pain_points:
        if pp == "NEAR_EXPIRY":
            triggers.append({
                "type":  "NEAR_EXPIRY",
                "value": signal.days_to_expiry,
                "desc":  f"{signal.days_to_expiry} days to expiry",
            })
        elif pp == "LOW_STOCK":
            triggers.append({
                "type":  "LOW_STOCK",
                "value": signal.current_stock,
                "desc":  f"stock {signal.current_stock} at/below reorder level {signal.reorder_level}",
            })
        elif pp == "STAGNANT":
            triggers.append({
                "type":  "STAGNANT",
                "value": round(signal.sales_velocity, 3),
                "desc":  f"velocity ratio {signal.sales_velocity:.2f} < 0.7",
            })
        elif pp == "HIGH_RETURN":
            triggers.append({
                "type":  "HIGH_RETURN",
                "value": round(signal.return_rate_30d, 3),
                "desc":  f"return rate {signal.return_rate_30d:.1%} in last 30 days",
            })
        elif pp == "SEASONAL_MISMATCH":
            triggers.append({
                "type":  "SEASONAL_MISMATCH",
                "value": None,
                "desc":  "seasonal demand mismatch detected",
            })

    # External urgency trigger
    if signal.urgency_score > 0.3:
        triggers.append({
            "type":  "NEWS_URGENCY",
            "value": round(signal.urgency_score, 3),
            "desc":  f"news urgency {signal.urgency_score:.2f} ({signal.news_sentiment})",
        })

    return {
        "pain_points":           signal.pain_points,
        "composite_risk_score":  round(signal.composite_risk_score, 4),
        "action_priority_score": round(signal.action_priority_score, 4),
        "triggers":              triggers,
    }


def build_evidence(signal: UnifiedSignal, shap_values: List[dict]) -> dict:
    """
    Section 3.31 — Evidence component.
    The supporting data — feature values that drove the decision.
    Auto-populated from signal fields.
    SHAP values identify which features mattered most.
    """
    return {
        "current_stock":         signal.current_stock,
        "reorder_level":         signal.reorder_level,
        "days_to_expiry":        signal.days_to_expiry,
        "sales_velocity_ratio":  round(signal.sales_velocity, 4),
        "return_rate_30d":       round(signal.return_rate_30d, 4),
        "urgency_score":         round(signal.urgency_score, 4),
        "news_sentiment":        signal.news_sentiment,
        "tft_forecast_7d":       round(signal.tft_forecast_7d, 2)
                                 if signal.tft_forecast_7d else None,
        "top_shap_features":     shap_values,   # from SHAP explainer
    }


def build_reasoning(action_type: str,
                    module_result: dict,
                    signal: UnifiedSignal) -> dict:
    """
    Section 3.31 — Reasoning component.
    Why this specific action was chosen over alternatives.
    Sources: module scoring results.
    """

    if action_type == "LOGISTICS":
        direction = module_result.get("direction", "")
        scores    = module_result.get("scores", {})

        if direction == "REVERSE":
            return {
                "action_chosen":   "MARKDOWN" if "MARKDOWN" in str(module_result.get("action","")) else direction,
                "scores":          scores,
                "why_not_transfer":module_result.get("transfer_reason", "single store"),
                "expiry_factor":   _get_expiry_factor(signal.days_to_expiry),
            }
        else:
            return {
                "action_chosen":      "RESTOCK",
                "restock_quantity":   module_result.get("restock_quantity", 0),
                "demand_forecast_7d": module_result.get("demand_forecast_7d", 0),
                "trigger_reasons":    module_result.get("trigger_reason", []),
            }

    elif action_type == "PRICING":
        return {
            "path_chosen":      module_result.get("path", "XGBOOST"),
            "path_reason":      "urgency > 0.5 → LLM path"
                                if signal.urgency_score > 0.5
                                else "urgency <= 0.5 → XGBoost normal path",
            "price_direction":  module_result.get("price_direction", ""),
            "price_change_pct": module_result.get("price_change_pct", 0),
            "fairness_check":   {
                "pms":             module_result.get("price_manip_score", 0),
                "clipped":         module_result.get("fairness_clipped", False),
            },
        }

    elif action_type == "COMBO":
        return {
            "strategy":           module_result.get("strategy", ""),
            "confidence_level":   module_result.get("confidence_level", "LOW"),
            "support_score":      module_result.get("support_score", 0),
            "fp_growth_note":     "HIGH confidence = customers actually buy these together"
                                  if module_result.get("confidence_level") == "HIGH"
                                  else "LOW confidence = experimental bundle",
        }

    elif action_type == "MONITOR":
        return {
            "reason": "urgency between 0.3-0.6 with no pain points — monitoring only",
        }

    return {}


def build_projection(action_type: str, module_result: dict) -> dict:
    """
    Section 3.31 — Projection component.
    Expected outcome if action is taken.
    Sources: projected_impact from M5/M6.
    """
    projected = module_result.get("projected_impact", {}) or {}

    if action_type == "LOGISTICS":
        return {
            "projected_revenue":      projected.get("projected_revenue", 0),
            "revenue_if_no_action":   projected.get("revenue_if_no_action", 0),
            "revenue_recovery":       projected.get("revenue_recovery", 0),
            "days_to_clear":          projected.get("days_to_clear"),
            "units_to_clear":         module_result.get("recommended_value", {})
                                      .get("units_to_clear"),
            "confidence":             projected.get("confidence", "MEDIUM"),
        }

    elif action_type == "PRICING":
        return {
            "recommended_price":  module_result.get("recommended_price"),
            "original_price":     module_result.get("original_price"),
            "expected_revenue_7d":module_result.get("expected_revenue_7d", 0),
            "price_direction":    module_result.get("price_direction", ""),
        }

    elif action_type == "COMBO":
        projected = module_result.get("projected_impact", {}) or {}
        return {
            "combo_price":        projected.get("combo_price"),
            "projected_revenue":  projected.get("projected_revenue", 0),
            "days_to_clear":      projected.get("days_to_clear"),
            "confidence":         module_result.get("confidence_level", "LOW"),
        }

    return {}


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_expiry_factor(days_to_expiry: int) -> str:
    if days_to_expiry < 7:
        return "2.0 (< 7 days — maximum urgency)"
    elif days_to_expiry < 14:
        return "1.5 (7-13 days — high urgency)"
    else:
        return "1.0 (>= 14 days — normal)"
