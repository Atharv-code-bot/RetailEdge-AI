# app/modules/m5_logistics/reverse_logistics.py
#
# Section 3.22 — Reverse Logistics — The 3-Way Decision
#
# Computes scores for three options:
#   TRANSFER  — move to another store (0 with single store)
#   MARKDOWN  — discount to clear stock
#   WAREHOUSE — return to warehouse
#
# Decision = argmax(scores)
# Tie preference: TRANSFER > MARKDOWN > WAREHOUSE
#
# Action masking (from Paper 5):
#   - Warehouse > 90% capacity → WAREHOUSE score forced to 0
#   - No nearby store capacity → TRANSFER score forced to 0

import numpy as np
from decision_engine.app.unified_signal import UnifiedSignal

# ── Warehouse stub constants ──────────────────────────────────────────────────
# Stubbed until warehouse table exists in PostgreSQL
# Build plan: if warehouse > 90% capacity → mask WAREHOUSE score
WAREHOUSE_CAPACITY_USED   = 0.70   # stub: 70% full
WAREHOUSE_CAPACITY_LIMIT  = 0.90   # mask threshold


def compute_reverse_logistics(
    signal: UnifiedSignal,
    product_info: dict,
) -> dict:
    """
    Computes 3-way reverse logistics decision.

    product_info dict needs:
        cost_price, base_selling_price, name

    Returns recommendation dict with:
        action          : "TRANSFER" / "MARKDOWN" / "WAREHOUSE_RETURN"
        scores          : all three scores (for transparency)
        projected_impact: expected outcome
    """

    cost_price  = product_info.get("cost_price",          0)
    base_price  = product_info.get("base_selling_price",  0)
    current_margin = base_price - cost_price

    # ── TRANSFER SCORE (Section 3.22) ─────────────────────────────────────────
    # With single store: TRANSFER score = 0 (no nearby stores)
    # When multi-store added: fill demand_gap and feasibility from transfer matrix
    transfer_score = 0.0
    transfer_reason = "single store — no transfer targets available"

    # ── MARKDOWN SCORE (Section 3.22) ─────────────────────────────────────────
    markdown_score = _compute_markdown_score(signal, cost_price, base_price, current_margin)

    # ── WAREHOUSE RETURN SCORE (Section 3.22) ─────────────────────────────────
    warehouse_score = _compute_warehouse_score(signal, cost_price, base_price)

    # ── Action masking (Paper 5) ──────────────────────────────────────────────
    if WAREHOUSE_CAPACITY_USED >= WAREHOUSE_CAPACITY_LIMIT:
        warehouse_score = 0.0   # warehouse full — mask it

    if transfer_score == 0.0:
        pass   # already masked — no nearby stores

    # ── Decision = argmax ─────────────────────────────────────────────────────
    scores = {
        "TRANSFER":         round(transfer_score,  4),
        "MARKDOWN":         round(markdown_score,  4),
        "WAREHOUSE_RETURN": round(warehouse_score, 4),
    }

    # Tie preference: TRANSFER > MARKDOWN > WAREHOUSE
    best_action = max(scores, key=lambda k: (scores[k], ["TRANSFER","MARKDOWN","WAREHOUSE_RETURN"].index(k) * -1))

    # ── Build recommended value ───────────────────────────────────────────────
    recommended_value = _build_recommended_value(
        best_action, signal, cost_price, base_price
    )

    # ── Projected impact ──────────────────────────────────────────────────────
    projected_impact = _compute_projected_impact(
        best_action, signal, cost_price, base_price, recommended_value
    )

    return {
        "action":            best_action,
        "direction":         "REVERSE",
        "scores":            scores,
        "transfer_reason":   transfer_reason,
        "recommended_value": recommended_value,
        "projected_impact":  projected_impact,
    }


# ── Score calculators ─────────────────────────────────────────────────────────

def _compute_markdown_score(signal, cost_price, base_price, current_margin) -> float:
    """
    MARKDOWN SCORE = price_elasticity * days_to_expiry_factor * current_margin
    Only fires if current_price > cost_price * 1.05 (no selling below cost)
    """

    # Cannot sell below cost + 5% margin
    if base_price <= cost_price * 1.05:
        return 0.0

    if current_margin <= 0:
        return 0.0

    # days_to_expiry_factor (Section 3.22)
    if signal.days_to_expiry >= 14:
        expiry_factor = 1.0
    elif 7 <= signal.days_to_expiry < 14:
        expiry_factor = 1.5
    else:
        expiry_factor = 2.0   # < 7 days — most urgent

    # price_elasticity — use stock_to_sales_ratio as proxy
    # Low ratio = product selling well = elastic (responds to price drops)
    # High ratio = stagnant = less elastic
    # We don't have historical price elasticity data yet — build plan says
    # "compute from delta_quantity / delta_price" — stub as 0.8 for now
    price_elasticity = 0.8   # default from build plan examples

    # Normalise margin to 0..1 scale against base_price
    margin_normalised = current_margin / base_price if base_price > 0 else 0.0

    score = price_elasticity * expiry_factor * margin_normalised
    return float(np.clip(score, 0.0, 5.0))   # allow > 1 since expiry_factor can be 2.0


def _compute_warehouse_score(signal, cost_price, base_price) -> float:
    """
    WAREHOUSE SCORE = resale_value_ratio * capacity_available * condition_score
    """

    # product_resale_value_ratio = cost_price / base_price
    # (how much of cost we can recover by returning to warehouse)
    if base_price <= 0:
        return 0.0
    resale_value_ratio = cost_price / base_price

    # warehouse_capacity_available = 1 - capacity_used
    capacity_available = 1.0 - WAREHOUSE_CAPACITY_USED

    # product_condition_score (Section 3.22)
    # 1.0 if days_to_expiry > 30, linear decay to 0 at expiry
    if signal.days_to_expiry == 9999:
        condition_score = 1.0   # non-perishable — always in good condition
    elif signal.days_to_expiry > 30:
        condition_score = 1.0
    elif signal.days_to_expiry <= 0:
        condition_score = 0.0   # expired — no value
    else:
        condition_score = signal.days_to_expiry / 30.0   # linear decay

    score = resale_value_ratio * capacity_available * condition_score
    return float(np.clip(score, 0.0, 1.0))


# ── Recommendation builders ───────────────────────────────────────────────────

def _build_recommended_value(action, signal, cost_price, base_price) -> dict:

    if action == "MARKDOWN":
        # Suggest markdown percentage based on urgency
        if signal.days_to_expiry < 7:
            markdown_pct = 30   # aggressive — clear fast
        elif signal.days_to_expiry < 14:
            markdown_pct = 20   # moderate
        else:
            markdown_pct = 10   # light discount

        # Ensure we don't go below cost * 1.02
        min_price        = round(cost_price * 1.02, 2)
        suggested_price  = round(base_price * (1 - markdown_pct / 100), 2)
        suggested_price  = max(suggested_price, min_price)
        actual_markdown  = round((1 - suggested_price / base_price) * 100, 1)

        return {
            "markdown_pct":    actual_markdown,
            "suggested_price": suggested_price,
            "original_price":  base_price,
            "min_price":       min_price,
            "units_to_clear":  signal.current_stock,
        }

    elif action == "TRANSFER":
        return {
            "transfer_to_store":    None,   # filled when multi-store added
            "quantity":             signal.current_stock,
            "transport_cost":       None,
        }

    elif action == "WAREHOUSE_RETURN":
        return {
            "quantity_to_return":   signal.current_stock,
            "estimated_recovery":   round(signal.current_stock * cost_price * 0.7, 2),
            "condition_note":       f"{signal.days_to_expiry} days to expiry",
        }

    return {}


def _compute_projected_impact(action, signal, cost_price, base_price,
                               recommended_value) -> dict:

    if action == "MARKDOWN":
        suggested_price = recommended_value.get("suggested_price", base_price)
        # Estimate sales increase from markdown using price elasticity
        # price_elasticity = -0.8 means 10% price drop → ~8% demand increase
        price_drop_pct   = (base_price - suggested_price) / base_price
        demand_increase  = price_drop_pct * 0.8   # elasticity
        daily_sales_est  = signal.tft_forecast_7d / 7 if signal.tft_forecast_7d > 0 else 1
        new_daily_sales  = daily_sales_est * (1 + demand_increase)
        days_to_clear    = round(signal.current_stock / new_daily_sales) if new_daily_sales > 0 else 999
        revenue_recovery = round(signal.current_stock * suggested_price, 2)
        revenue_if_expired = 0.0

        return {
            "projected_revenue":      revenue_recovery,
            "revenue_if_no_action":   revenue_if_expired,
            "revenue_recovery":       revenue_recovery,
            "days_to_clear":          days_to_clear,
            "confidence":             "MEDIUM",
        }

    elif action == "WAREHOUSE_RETURN":
        recovery = recommended_value.get("estimated_recovery", 0)
        return {
            "projected_revenue":    recovery,
            "revenue_if_no_action": 0.0,
            "revenue_recovery":     recovery,
            "days_to_clear":        1,
            "confidence":           "HIGH",
        }

    elif action == "TRANSFER":
        return {
            "projected_revenue":    round(signal.current_stock * base_price, 2),
            "revenue_if_no_action": 0.0,
            "revenue_recovery":     round(signal.current_stock * base_price, 2),
            "days_to_clear":        None,
            "confidence":           "LOW",   # single store — stub
        }

    return {}
