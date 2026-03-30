# app/core/config.py
#
# All threshold values for M2 (Feature Engineering) and M4 (Pain Point Detection).
# Every value here traces directly to Build Plan Section 3.6 or Section 3.17.
# DO NOT change these without updating the corresponding section reference.
#
# What was removed from ChatGPT version:
#   - DECLINING_SALES_PCT     → not a separate pain point. Covered by STAGNANT.
#   - SEASONAL_DROP_PCT       → wrong metric. Seasonal uses seasonality_index, not change_pct.
#   - URGENCY_WEIGHTS dict    → overrides Decision Engine formula. Removed.
#   - SEVERITY_MULTIPLIER     → Decision Engine reads float scores, not severity strings.
#   - OVERSTOCK_DAYS          → not a standalone pain point. Internal threshold only.


# ─────────────────────────────────────────────────────────────
# STAGNANT / DECREASING SALES  (Build Plan Section 3.17)
# ─────────────────────────────────────────────────────────────

# sales_velocity_ratio = rolling_7d / rolling_30d * (30/7)
# Below this → product is stagnant or declining
STAGNANT_VELOCITY_RATIO = 0.7          # Build Plan: "ratio < 0.7: stagnant"

# Accelerating sales threshold (used for forward logistics trigger)
ACCELERATING_VELOCITY_RATIO = 1.3      # Build Plan: "ratio > 1.3: accelerating"

# Minimum rolling_30d units to qualify — filters out new/very slow products
# so we don't flag something that sold 1 unit in 30 days as "stagnant"
STAGNANT_MIN_MONTHLY_UNITS = 10        # Build Plan Section 3.17: "rolling_30d > 10 units"


# ─────────────────────────────────────────────────────────────
# NEAR EXPIRY  (Build Plan Section 3.17)
# ─────────────────────────────────────────────────────────────

# expiry_risk_score = 1.0 - (days_to_expiry / shelf_life_days), clamped 0..1
# At 0.8: last 20% of shelf life remaining
# Examples: dairy (7d shelf) → triggers at 1.4d left
#           biscuits (90d)   → triggers at 18d left
#           atta (365d)      → triggers at 73d left
NEAR_EXPIRY_RISK_SCORE = 0.8           # Build Plan Section 3.6: "Score of 0.8+ triggers near-expiry"


# ─────────────────────────────────────────────────────────────
# LOW STOCK  (Build Plan Section 3.17)
# ─────────────────────────────────────────────────────────────

# Primary trigger: current_stock <= reorder_level (from inventory table)
# Secondary trigger: days_of_stock fallback for products with no reorder level set
LOW_STOCK_DAYS = 3                     # days of stock remaining before stockout


# ─────────────────────────────────────────────────────────────
# HIGH RETURN RATE  (Build Plan Section 3.17)
# ─────────────────────────────────────────────────────────────

# Two conditions BOTH must be true (AND logic):
#   1. return_rate_30d > HIGH_RETURN_RATE_THRESHOLD
#   2. return_rate_30d > category_avg_return_rate * RETURN_RATE_CATEGORY_MULTIPLIER
HIGH_RETURN_RATE_THRESHOLD    = 0.15   # Build Plan Section 3.17: "> 0.15 is high"
RETURN_RATE_CATEGORY_MULT     = 1.5    # Build Plan Section 3.17: "> category_avg * 1.5"


# ─────────────────────────────────────────────────────────────
# SEASONAL MISMATCH  (Build Plan Section 3.17)
# ─────────────────────────────────────────────────────────────

# seasonality_index = historical same-period-last-year avg / overall_avg
# > 1.4 = demand spike incoming but stock not ready → forward logistics needed
# < 0.7 = off-season but overstocked → reverse logistics / markdown needed
SEASONAL_HIGH_INDEX = 1.4              # Build Plan Section 3.17: "seasonality_index > 1.4"
SEASONAL_LOW_INDEX  = 0.7              # Build Plan Section 3.17: "seasonality_index < 0.7"

# Understock check for high-season: current_stock < rolling_30d * this multiplier
SEASONAL_UNDERSTOCK_MULT = 1.2         # Build Plan Section 3.17: "stock < rolling_30d * 1.2"

# Overstock check for low-season
SEASONAL_OVERSTOCK_RATIO = 6.0         # Build Plan Section 3.17: "stock_to_sales_ratio > 6"


# ─────────────────────────────────────────────────────────────
# STOCK RATIOS  (Build Plan Section 3.6)
# ─────────────────────────────────────────────────────────────

# stock_to_sales_ratio = current_stock / rolling_sales_7d
OVERSTOCK_RATIO   = 8.0                # Build Plan Section 3.6: "Ratio > 8 suggests overstocking"
STOCKOUT_RATIO    = 1.5                # Build Plan Section 3.6: "Ratio < 1.5 suggests near stockout"


# ─────────────────────────────────────────────────────────────
# COMPOSITE RISK SCORE WEIGHTS  (Build Plan Section 3.18)
# ─────────────────────────────────────────────────────────────
# composite_risk_score is computed in M4 (pain point detection).
# These weights combine individual risk signals into one 0..1 score
# that the Decision Engine reads as composite_risk_score.
#
# Note: action_priority_score (Decision Engine Section 3.5.5) is a
# SEPARATE formula that combines composite_risk_score WITH news urgency.
# These weights are only for the M2/M4 composite_risk_score.

RISK_WEIGHT_EXPIRY   = 0.35            # expiry_risk_score contribution
RISK_WEIGHT_VELOCITY = 0.25            # stagnant velocity contribution
RISK_WEIGHT_STOCK    = 0.25            # stock level contribution
RISK_WEIGHT_RETURN   = 0.15            # return rate contribution


# ─────────────────────────────────────────────────────────────
# PAIN POINT PRIORITY ORDER  (Build Plan Section 3.19)
# ─────────────────────────────────────────────────────────────
# When a product has multiple pain points, this order determines
# which one is surfaced first in the dashboard.
# Lower number = higher priority.

PAIN_POINT_PRIORITY = {
    "NEAR_EXPIRY":        1,
    "HIGH_RETURN":        2,
    "STAGNANT":           3,
    "LOW_STOCK":          4,
    "SEASONAL_MISMATCH":  5,
}


# ─────────────────────────────────────────────────────────────
# DATA REFERENCE DATE  (important for historical CSV data)
# ─────────────────────────────────────────────────────────────
# When running on CSV data (not live DB), use this as "today"
# instead of pd.Timestamp.now() — our data ends on this date.
DATA_END_DATE = "2026-02-28"