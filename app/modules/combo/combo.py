# app/modules/m6_combo/combo.py
#
# M6 — Combo Offer Generator entry point.
# Called by Decision Engine: await m6_combo.run(signal)
#
# Build Plan Section 3.28 flow:
#   1. Rule-based bundles (cross_sell, upsell, clearance)
#   2. LLM generates combo name + discount + rationale (Gemini)
#   3. FP-Growth validates co-purchase frequency
#   4. Rank by confidence + urgency
#   5. Return top combo with projected_impact

import os
import pandas as pd
from typing import List
from app.decision_engine.unified_signal import UnifiedSignal
from app.modules.combo.combo_rules  import (
    detect_product_category,
    cross_sell_strategy,
    premium_upsell_strategy,
    inventory_clearance_strategy,
)
from app.modules.combo.llm_combo    import generate_llm_combo
from app.modules.combo.combo_ranker import rank_bundles
from app.modules.combo.fp_growth    import (
    load_itemsets,
    get_confidence_level,
    find_frequent_partners,
)


class ComboModule:

    def __init__(self,
                 products_path: str,
                 itemsets_cache_path: str = "pipeline_output/fp_growth_itemsets.json"):
        """
        products_path       : path to products.csv
        itemsets_cache_path : path to FP-Growth output cache (from nightly pipeline)
        """
        self.products_df   = pd.read_csv(products_path)
        self.itemsets      = load_itemsets(itemsets_cache_path)
        self.inventory_catalog = list(self.products_df["name"].values)

        if self.itemsets:
            print(f"  [combo] FP-Growth itemsets loaded: {len(self.itemsets)} itemsets")
        else:
            print("  [combo] No FP-Growth cache found — confidence will default to LOW")

    async def run(self, signal: UnifiedSignal) -> dict:
        """
        Main entry point called by Decision Engine.
        Returns best combo recommendation with confidence level.
        """

        product_info = self._get_product_info(signal.product_id)
        product_name = product_info.get("name", f"product_{signal.product_id}")
        product_category = product_info.get("category", "Groceries (Kirana)")

        # ── Step 1: Rule-based bundles ────────────────────────────────────────
        bundles = []
        bundles.extend(cross_sell_strategy(signal, product_category))
        bundles.extend(premium_upsell_strategy(signal, product_category))
        bundles.extend(inventory_clearance_strategy(signal, product_name, product_category))

        # ── Step 2: LLM generates combo for best bundle ───────────────────────
        # Use clearance strategy as primary if available, else first bundle
        primary_bundle = next(
            (b for b in bundles if b.get("strategy") == "inventory_clearance"),
            bundles[0] if bundles else None
        )

        llm_result = None
        if primary_bundle:
            partner_categories = primary_bundle.get("bundle_categories", [])
            llm_result = generate_llm_combo(
                signal            = signal,
                product_name      = product_name,
                product_category  = product_category,
                partner_categories= partner_categories,
            )

        # ── Step 3: Find actual partner products ──────────────────────────────
        # From FP-Growth or category lookup
        partner_products = self._find_partner_products(
            signal.product_id,
            product_category,
            primary_bundle,
        )

        # ── Step 4: FP-Growth validation ──────────────────────────────────────
        all_product_ids = [signal.product_id] + [p["product_id"] for p in partner_products]
        confidence_level, support_score = get_confidence_level(
            all_product_ids, self.itemsets
        )

        # ── Step 5: Build final combo bundle ─────────────────────────────────
        combo_bundle = {
            "strategy":          primary_bundle.get("strategy", "cross_sell") if primary_bundle else "cross_sell",
            "confidence_level":  confidence_level,
            "support_score":     round(support_score, 4),
            "combo_name":        llm_result["combo_name"] if llm_result else "Value Bundle",
            "discount_pct":      llm_result["discount_pct"] if llm_result else 10,
            "rationale":         llm_result["rationale"] if llm_result else "",
            "products_included": [signal.product_id] + [p["product_id"] for p in partner_products],
            "product_names":     [product_name] + [p["name"] for p in partner_products],
            "partner_categories":primary_bundle.get("bundle_categories", []) if primary_bundle else [],
        }

        # ── Step 6: Rank (single bundle here, but supports multiple) ─────────
        ranked = rank_bundles([combo_bundle], signal)
        top_combo = ranked[0] if ranked else combo_bundle

        # ── Step 7: Projected impact ──────────────────────────────────────────
        projected_impact = self._compute_projected_impact(
            signal, product_info, top_combo
        )

        return {
            "module":            "M6_COMBO",
            "product_id":        signal.product_id,
            "store_id":          signal.store_id,
            "product_name":      product_name,
            "combo_name":        top_combo["combo_name"],
            "discount_pct":      top_combo["discount_pct"],
            "products_included": top_combo["products_included"],
            "product_names":     top_combo["product_names"],
            "confidence_level":  top_combo["confidence_level"],
            "support_score":     top_combo["support_score"],
            "rationale":         top_combo.get("rationale", ""),
            "strategy":          top_combo["strategy"],
            "projected_impact":  projected_impact,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_product_info(self, product_id: int) -> dict:
        row = self.products_df[self.products_df["id"] == product_id]
        if row.empty:
            return {"name": f"product_{product_id}", "category": "Groceries (Kirana)",
                    "cost_price": 0, "base_selling_price": 0}
        r = row.iloc[0]
        return {
            "name":               str(r["name"]),
            "category":           str(r["category"]),
            "cost_price":         float(r["cost_price"]),
            "base_selling_price": float(r["base_selling_price"]),
        }

    def _find_partner_products(self, product_id: int,
                                product_category: str,
                                primary_bundle) -> List[dict]:
        """
        Finds actual partner products to include in combo.
        Priority: FP-Growth frequent partners → category lookup
        """
        # Try FP-Growth first
        fp_partners = find_frequent_partners(product_id, self.itemsets, top_n=2)
        if fp_partners:
            result = []
            for p in fp_partners[:2]:
                for pid in p["partner_ids"][:1]:
                    prod = self.products_df[self.products_df["id"] == pid]
                    if not prod.empty:
                        result.append({
                            "product_id": int(pid),
                            "name": str(prod.iloc[0]["name"]),
                        })
            if result:
                return result

        # Fallback: find products from partner categories
        if primary_bundle:
            partner_cats = primary_bundle.get("bundle_categories", [])
            result = []
            for cat in partner_cats[:2]:
                cat_products = self.products_df[
                    self.products_df["category"] == cat
                ].head(1)
                if not cat_products.empty:
                    r = cat_products.iloc[0]
                    result.append({
                        "product_id": int(r["id"]),
                        "name":       str(r["name"]),
                    })
            return result

        return []

    def _compute_projected_impact(self, signal: UnifiedSignal,
                                   product_info: dict, combo: dict) -> dict:
        """Estimates revenue impact of the combo offer."""
        base_price   = product_info.get("base_selling_price", 0)
        discount_pct = combo.get("discount_pct", 10)
        combo_price  = round(base_price * (1 - discount_pct / 100), 2)

        # Estimate demand increase from bundle discount
        demand_increase  = discount_pct / 100 * 0.8   # price elasticity
        daily_sales      = signal.tft_forecast_7d / 7 if signal.tft_forecast_7d > 0 else 1
        new_daily_sales  = daily_sales * (1 + demand_increase)
        days_to_clear    = round(signal.current_stock / new_daily_sales) if new_daily_sales > 0 else 999
        revenue_recovery = round(signal.current_stock * combo_price, 2)

        return {
            "combo_price":       combo_price,
            "original_price":    base_price,
            "projected_revenue": revenue_recovery,
            "days_to_clear":     days_to_clear,
            "confidence":        combo.get("confidence_level", "LOW"),
        }
