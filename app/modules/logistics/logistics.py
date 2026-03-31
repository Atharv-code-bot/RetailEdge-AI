# app/modules/m5_logistics/logistics.py
#
# M5 — Logistics Intelligence entry point.
# Called by Decision Engine: await m5.run(signal, needs_reverse)
#
# Routes to forward or reverse logistics based on direction flag
# set by conflict_resolver.py in the Decision Engine.

import pandas as pd
from app.decision_engine.unified_signal import UnifiedSignal
from logistics.forward_logistics import compute_forward_logistics
from logistics.reverse_logistics import compute_reverse_logistics


class LogisticsModule:

    def __init__(self, products_path: str):
        """
        products_path: path to products.csv
        Loaded once, reused for all product queries.
        """
        self.products_df = pd.read_csv(products_path)

    async def run(self, signal: UnifiedSignal, needs_reverse: bool) -> dict:
        """
        Main entry point called by Decision Engine.

        signal       : UnifiedSignal from Decision Engine
        needs_reverse: True = clear stock, False = restock
        """

        product_info = self._get_product_info(signal.product_id)

        if needs_reverse:
            result = compute_reverse_logistics(signal, product_info)
        else:
            result = compute_forward_logistics(signal, product_info)

        # Add product context to result
        result["product_id"]   = signal.product_id
        result["store_id"]     = signal.store_id
        result["product_name"] = product_info.get("name", f"product_{signal.product_id}")

        return result

    def _get_product_info(self, product_id: int) -> dict:
        """Fetches product cost_price and base_selling_price."""
        row = self.products_df[self.products_df["id"] == product_id]
        if row.empty:
            return {"cost_price": 0, "base_selling_price": 0, "name": f"product_{product_id}"}
        r = row.iloc[0]
        return {
            "name":               r["name"],
            "cost_price":         float(r["cost_price"]),
            "base_selling_price": float(r["base_selling_price"]),
        }
