# app/main.py

import os
import json
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from inventory_painpoints_service.app.services.nightly_pipeline import run_nightly_pipeline
from decision_engine.app.engine import DecisionEngine

app = FastAPI(title="Predictify AI — Pain Point Detection Service")

# ─────────────────────────────────────────────────────────────────────────────
# Your local data path — update this if you move the folder
# ─────────────────────────────────────────────────────────────────────────────
# After — works on any machine
BASE_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory_painpoints_service")
DATA_DIR   = os.path.join(BASE_DIR, "datasamplesv2")
OUTPUT_DIR = os.path.join(BASE_DIR, "pipeline_output")


def sanitize_for_json(df: pd.DataFrame) -> list:
    """
    Replaces inf / -inf / NaN with None so FastAPI can serialise to JSON.
    Also handles any remaining non-finite floats row by row.
    Returns list of dicts (JSON-safe).
    """
    df = df.copy()

    # Replace inf/-inf first, then NaN
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.where(pd.notnull(df), None)

    # Convert to records and scrub any remaining non-finite values
    # (catches edge cases like float('inf') stored as Python float, not numpy)
    records = df.to_dict(orient="records")
    clean = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, float) and (np.isinf(v) or np.isnan(v)):
                clean_row[k] = None
            else:
                clean_row[k] = v
        clean.append(clean_row)
    return clean


# ─────────────────────────────────────────────────────────────────────────────
# POST /run-pipeline
# Runs the full nightly pipeline and saves product_analysis.csv
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/run-pipeline")
def run_pipeline():
    result = run_nightly_pipeline(
        data_dir   = DATA_DIR,
        output_dir = OUTPUT_DIR,
    )

    # Split into two views for the API response:
    # 1. flagged  — products with at least one pain point
    # 2. all      — full product_analysis (already saved to CSV by the pipeline)

    flagged = result[result["pain_points_triggered"] != "[]"].copy()
    flagged = flagged.sort_values("composite_risk_score", ascending=False)

    return {
        "message":        "Pipeline executed successfully",
        "output_csv":     os.path.join(OUTPUT_DIR, "product_analysis.csv"),
        "total_products": len(result),
        "flagged_count":  len(flagged),
        "high_risk_count": int((result["composite_risk_score"] > 0.5).sum()),
        "pain_point_breakdown": _pain_point_summary(result),
        "flagged_products": sanitize_for_json(flagged[[
            "product_id", "store_id", "pain_points_triggered",
            "composite_risk_score", "days_to_expiry",
            "current_stock", "reorder_level",
            "sales_velocity_ratio", "return_rate_30d",
        ]]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# Quick check that the service is running
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "Predictify AI Pain Point Detection"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /results
# Returns the last saved product_analysis.csv without re-running the pipeline
# Use this for the Decision Engine to fetch pre-computed results
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/results")
def get_results():
    path = os.path.join(OUTPUT_DIR, "product_analysis.csv")

    if not os.path.exists(path):
        return JSONResponse(
            status_code=404,
            content={"error": "No results found. Run POST /run-pipeline first."}
        )

    df = pd.read_csv(path)
    flagged = df[df["pain_points_triggered"] != "[]"].copy()
    flagged = flagged.sort_values("composite_risk_score", ascending=False)

    return {
        "run_date":        df["run_date"].iloc[0] if len(df) > 0 else None,
        "total_products":  len(df),
        "flagged_count":   len(flagged),
        "high_risk_count": int((df["composite_risk_score"] > 0.5).sum()),
        "pain_point_breakdown": _pain_point_summary(df),
        "flagged_products": sanitize_for_json(flagged[[
            "product_id", "store_id", "pain_points_triggered",
            "composite_risk_score", "days_to_expiry",
            "current_stock", "reorder_level",
            "sales_velocity_ratio", "return_rate_30d",
        ]]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /results/{product_id}
# Returns full analysis for one product — used by Decision Engine at runtime
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/results/{product_id}")
def get_product_result(product_id: int):
    path = os.path.join(OUTPUT_DIR, "product_analysis.csv")

    if not os.path.exists(path):
        return JSONResponse(
            status_code=404,
            content={"error": "No results found. Run POST /run-pipeline first."}
        )

    df = pd.read_csv(path)
    row = df[df["product_id"] == product_id]

    if row.empty:
        return JSONResponse(
            status_code=404,
            content={"error": f"product_id {product_id} not found in last run."}
        )

    return sanitize_for_json(row)[0]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _pain_point_summary(df: pd.DataFrame) -> dict:
    """Count how many products have each pain point."""
    from collections import Counter
    all_pp = [
        pp
        for pps in df["pain_points_triggered"].apply(json.loads)
        for pp in pps
    ]
    return dict(Counter(all_pp))


# ─────────────────────────────────────────────────────────────────────────────
# GET /decision/{product_id}
# Runs Decision Engine for one product on manager query.
# Fetches pre-computed features + live Reddit signal → returns recommendation.
# ─────────────────────────────────────────────────────────────────────────────
 

 
@app.get("/decision/{product_id}")
async def get_decision(product_id: int):
    path = os.path.join(OUTPUT_DIR, "product_analysis.csv")
 
    if not os.path.exists(path):
        return JSONResponse(
            status_code=404,
            content={"error": "No analysis found. Run POST /run-pipeline first."}
        )
 
    de = DecisionEngine(
        product_analysis_path = path,
        products_path         = os.path.join(DATA_DIR, "products.csv"),
    )
 
    result = await de.run_for_product(product_id)
    return result