# app/modules/m5_logistics/logistics.py
#
# M5 — Logistics Intelligence entry point.
# Called by Decision Engine: await m5.run(signal, needs_reverse)
#
# Routes to forward or reverse logistics based on direction flag
# set by conflict_resolver.py in the Decision Engine.

import pandas as pd
from app.decision_engine.unified_signal import UnifiedSignal
from app.modules.logistics.forward_logistics import compute_forward_logistics
from app.modules.logistics.reverse_logistics import compute_reverse_logistics


class LogisticsModule:

    def __init__(self, products_path: str):
        """
        products_path: path to cleaned products.csv
        NOTE:
        - 'id' is already renamed to 'product_id' in cleaner
        - So always use 'product_id' here
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
        """
        Fetch product metadata safely.
        Uses cleaned schema (product_id, name, cost_price, base_selling_price)
        """

        # ✅ Correct column after cleaning
        col = "product_id" if "product_id" in self.products_df.columns else "id"

        row = self.products_df[self.products_df[col] == product_id]

        # ✅ Handle missing product
        if row.empty:
            return {
                "name": f"product_{product_id}",
                "cost_price": 0.0,
                "base_selling_price": 0.0,
            }

        r = row.iloc[0]

        # ✅ Safe extraction
        return {
            "name": r.get("name", f"product_{product_id}"),
            "cost_price": float(r.get("cost_price", 0.0)),
            "base_selling_price": float(r.get("base_selling_price", 0.0)),
        }