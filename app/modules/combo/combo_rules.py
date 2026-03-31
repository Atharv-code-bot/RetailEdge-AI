# app/modules/m6_combo/combo_rules.py
#
# Rule-based combo strategies for D-Mart FMCG products.
#
# What changed from existing code:
#   - CROSS_SELL_MAP: was phone/laptop/camera → now D-Mart categories
#   - detect_product_category: was checking "iphone/galaxy" → now checks
#     D-Mart category names from products.csv
#   - cross_sell_strategy: was checking demand_momentum_score →
#     now uses signal.sales_velocity and signal.pain_points
#   - premium_upsell_strategy: was checking price_recommendation
#     (wrong dependency on M6 pricing output) → now uses urgency + sentiment
#   - inventory_clearance_strategy: was using arbitrary pressure scores →
#     now uses NEAR_EXPIRY / STAGNANT pain points directly

from typing import List, Dict
from app.decision_engine.unified_signal import UnifiedSignal

# ── D-Mart FMCG cross-sell map ────────────────────────────────────────────────
# category → commonly bought together categories
CROSS_SELL_MAP = {
    "Frozens & Dairy":           ["Bread & Bakery", "Groceries (Kirana)"],
    "Bread & Bakery":            ["Frozens & Dairy", "Beverages"],
    "Beverages":                 ["Biscuits, Cookies & Wafers", "Snacks & Farsan"],
    "Biscuits, Cookies & Wafers":["Beverages", "Chocolate"],
    "Chocolate":                 ["Biscuits, Cookies & Wafers", "Beverages"],
    "Masala & Spices":           ["Groceries (Kirana)", "Edible Oil & Ghee"],
    "Edible Oil & Ghee":         ["Groceries (Kirana)", "Masala & Spices"],
    "Groceries (Kirana)":        ["Masala & Spices", "Edible Oil & Ghee"],
    "Detergents":                ["Cleaning Accessories", "Household"],
    "Cleaning Accessories":      ["Detergents", "Household"],
    "Personal Care":             ["Oral Care", "Hair Care"],
    "Hair Care":                 ["Personal Care", "Skin Care"],
    "Oral Care":                 ["Personal Care"],
    "Ready To Eat & Cook":       ["Beverages", "Groceries (Kirana)"],
    "Snacks & Farsan":           ["Beverages", "Chocolate"],
    "Health Supplements":        ["Groceries (Kirana)", "Beverages"],
    "Dry Fruits":                ["Groceries (Kirana)", "Health Supplements"],
    "Fresh Produce":             ["Groceries (Kirana)", "Masala & Spices"],
}

# ── Upsell map (premium version of same category) ────────────────────────────
UPSELL_MAP = {
    "Detergents":                ["Cleaning Accessories"],
    "Beverages":                 ["Health Supplements"],
    "Biscuits, Cookies & Wafers":["Dry Fruits"],
    "Groceries (Kirana)":        ["Dry Fruits"],
    "Personal Care":             ["Skin Care"],
    "Cleaning Accessories":      ["Household"],
}


def detect_product_category(product_name: str, products_df=None) -> str:
    """
    Returns category for a product name.
    Looks up from products_df if available, else rule-based keyword match.

    Changed from existing: was checking for 'phone/iphone/galaxy' —
    now checks D-Mart product names and categories.
    """
    if products_df is not None:
        match = products_df[
            products_df["name"].str.lower() == product_name.lower()
        ]
        if not match.empty:
            return match.iloc[0]["category"]

    # Keyword fallback
    name = product_name.lower()
    if any(w in name for w in ["shampoo","soap","cream","oil hair"]):
        return "Hair Care"
    if any(w in name for w in ["toothpaste","brush","paste"]):
        return "Oral Care"
    if any(w in name for w in ["dahi","paneer","butter","cheese","milk","curd"]):
        return "Frozens & Dairy"
    if any(w in name for w in ["biscuit","cookie","wafer","bourbon","parle"]):
        return "Biscuits, Cookies & Wafers"
    if any(w in name for w in ["dal","rice","atta","wheat","sugar","salt","poha"]):
        return "Groceries (Kirana)"
    if any(w in name for w in ["masala","spice","chilli","turmeric"]):
        return "Masala & Spices"
    if any(w in name for w in ["detergent","surf","ariel","rin","wheel","vim"]):
        return "Detergents"
    if any(w in name for w in ["tea","coffee","juice","water","cola","pepsi"]):
        return "Beverages"
    if any(w in name for w in ["maggi","noodle","soup","instant"]):
        return "Ready To Eat & Cook"

    return None


def cross_sell_strategy(
    signal: UnifiedSignal,
    product_category: str,
) -> List[Dict]:
    """
    Suggests complementary category products.

    Changed from existing:
      - Was checking demand_momentum_score > 60 (wrong field)
      - Now checks sales_velocity > 0.7 (product is still selling)
      - Uses D-Mart category map instead of phone/laptop/camera
    """
    bundles = []

    # Only cross-sell if product is still actively selling
    if signal.sales_velocity < 0.5:
        return bundles

    if product_category and product_category in CROSS_SELL_MAP:
        partner_categories = CROSS_SELL_MAP[product_category]
        bundles.append({
            "bundle_categories": partner_categories,
            "strategy":          "cross_sell",
            "trigger":           f"velocity={signal.sales_velocity:.2f} — active product, cross-sell opportunity",
        })

    return bundles


def premium_upsell_strategy(
    signal: UnifiedSignal,
    product_category: str,
) -> List[Dict]:
    """
    Suggests premium upgrade bundles.

    Changed from existing:
      - Was checking price_recommendation['price_direction'] (wrong dependency)
      - Now uses urgency_score + news_sentiment (available in UnifiedSignal)
    """
    bundles = []

    # Upsell when positive external signal — customer is in buying mood
    if (signal.urgency_score > 0.3
            and signal.news_sentiment == "POSITIVE"
            and product_category in UPSELL_MAP):

        bundles.append({
            "bundle_categories": UPSELL_MAP[product_category],
            "strategy":          "premium_upsell",
            "trigger":           f"positive news signal (urgency={signal.urgency_score:.2f})",
        })

    return bundles


def inventory_clearance_strategy(
    signal: UnifiedSignal,
    product_name: str,
    product_category: str,
) -> List[Dict]:
    """
    Bundles slow/expiring product with a high-demand partner to clear stock.

    Changed from existing:
      - Was checking inventory_pressure > 75 and demand < 40 (wrong fields)
      - Now uses pain_points directly from UnifiedSignal
      - Domain fixed: D-Mart FMCG, not electronics
    """
    bundles = []

    # Trigger on NEAR_EXPIRY or STAGNANT — need to clear stock fast
    needs_clearance = (
        "NEAR_EXPIRY" in signal.pain_points or
        "STAGNANT"    in signal.pain_points or
        "HIGH_RETURN" in signal.pain_points
    )

    if not needs_clearance:
        return bundles

    # Find high-demand partner categories for this product
    partner_categories = CROSS_SELL_MAP.get(product_category, [])

    if partner_categories:
        bundles.append({
            "bundle_categories": partner_categories,
            "strategy":          "inventory_clearance",
            "trigger":           f"pain_points={signal.pain_points}, days_to_expiry={signal.days_to_expiry}",
            "urgency":           "HIGH" if signal.days_to_expiry < 7 else "MEDIUM",
        })

    return bundles
