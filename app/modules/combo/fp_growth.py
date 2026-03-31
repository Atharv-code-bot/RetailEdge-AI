# app/modules/m6_combo/fp_growth.py
#
# FP-Growth validation for combo offers.
# Runs on sales.csv to find frequent itemsets.
# Caches results to avoid recomputing on every query.
#
# Build Plan Section 3.28:
#   min_support    = 0.02
#   min_confidence = 0.3
#   HIGH   : support >= 0.02
#   MEDIUM : 0.01 - 0.02
#   LOW    : < 0.01

import os
import json
import pandas as pd
from typing import List

# FP-Growth confidence thresholds
HIGH_SUPPORT   = 0.02
MEDIUM_SUPPORT = 0.01

# Cache file path
ITEMSETS_CACHE = "pipeline_output/fp_growth_itemsets.json"


def run_fp_growth(sales_path: str, cache_path: str = ITEMSETS_CACHE) -> dict:
    """
    Runs FP-Growth on sales.csv.
    Builds basket: each product_id that appeared in sales on same day = transaction.
    Saves frequent itemsets to cache.

    Returns dict: {frozenset_key: support_score}
    """
    try:
        from mlxtend.frequent_patterns import fpgrowth
        from mlxtend.preprocessing import TransactionEncoder
    except ImportError:
        print("  [fp_growth] mlxtend not installed — pip install mlxtend")
        return {}

    print("  [fp_growth] Building transaction baskets from sales.csv...")
    sales = pd.read_csv(sales_path)

    # Build daily baskets: products bought on same day = transaction
    baskets = (
        sales.groupby("sold_at")["product_id"]
        .apply(list)
        .tolist()
    )

    print(f"  [fp_growth] {len(baskets)} daily transactions")

    # Encode transactions
    te = TransactionEncoder()
    te_array = te.fit(baskets).transform(baskets)
    basket_df = pd.DataFrame(te_array, columns=te.columns_)

    # Run FP-Growth
    # Build plan min_support=0.02 but with 1 store we lower to 0.005
    # (build plan note: "lower to 0.005 for first 3 months")
    frequent_itemsets = fpgrowth(
        basket_df,
        min_support=0.005,
        use_colnames=True,
    )

    print(f"  [fp_growth] Found {len(frequent_itemsets)} frequent itemsets")

    # Convert to serialisable dict
    itemsets_dict = {}
    for _, row in frequent_itemsets.iterrows():
        key = str(sorted(list(row["itemsets"])))
        itemsets_dict[key] = float(row["support"])

    # Save cache
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(itemsets_dict, f)

    print(f"  [fp_growth] Saved to {cache_path}")
    return itemsets_dict


def load_itemsets(cache_path: str = ITEMSETS_CACHE) -> dict:
    """Loads cached frequent itemsets."""
    if not os.path.exists(cache_path):
        return {}
    with open(cache_path) as f:
        return json.load(f)


def get_confidence_level(product_ids: List[int],
                          itemsets: dict) -> tuple:
    """
    Checks if a set of product_ids appears as a frequent itemset.
    Returns (confidence_level, support_score).

    confidence_level: HIGH / MEDIUM / LOW
    support_score   : float 0..1
    """
    if not itemsets:
        return "LOW", 0.0

    key = str(sorted([int(p) for p in product_ids]))
    support = itemsets.get(key, 0.0)

    if support >= HIGH_SUPPORT:
        return "HIGH", support
    elif support >= MEDIUM_SUPPORT:
        return "MEDIUM", support
    else:
        return "LOW", support


def find_frequent_partners(product_id: int,
                            itemsets: dict,
                            top_n: int = 3) -> List[dict]:
    """
    Finds the top_n most frequent co-purchase partners for a product.
    Used to suggest combo partners when LLM is not available.
    """
    partners = []

    for key, support in itemsets.items():
        try:
            ids = eval(key)  # safe — our own JSON
            if product_id in ids and len(ids) >= 2:
                partner_ids = [i for i in ids if i != product_id]
                partners.append({
                    "partner_ids": partner_ids,
                    "support":     support,
                    "confidence":  "HIGH" if support >= HIGH_SUPPORT else
                                   "MEDIUM" if support >= MEDIUM_SUPPORT else "LOW"
                })
        except Exception:
            continue

    # Sort by support descending
    partners.sort(key=lambda x: x["support"], reverse=True)
    return partners[:top_n]
