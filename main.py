# main.py
# Location : D:\RetailEdge AI\main.py
# Run from : D:\RetailEdge AI
# Command  : python -m uvicorn main:app --reload

import sys
import os

# ── Path fix ──────────────────────────────────────────────────────────────────
# main.py lives at RetailEdge AI/ level.
# All internal files use 'from app.xxx import yyy'.
import json
import numpy as np
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from inventory_painpoints_service.app.services.nightly_pipeline import run_nightly_pipeline
from app.decision_engine.engine import DecisionEngine

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "inventory_painpoints_service")
DATA_DIR   = os.path.join(BASE_DIR, "datasamplesv2")
OUTPUT_DIR = os.path.join(BASE_DIR, "pipeline_output")

PRODUCT_ANALYSIS_PATH = os.path.join(OUTPUT_DIR, "product_analysis.csv")
PRODUCTS_PATH         = os.path.join(DATA_DIR,   "products.csv")
RECOMMENDATIONS_PATH  = os.path.join(OUTPUT_DIR, "recommendations.csv")


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP — create Decision Engine ONCE, reuse for every request
# ─────────────────────────────────────────────────────────────────────────────
# Why: DecisionEngine loads products.csv, FP-Growth itemsets, XGBoost model,
# and initialises M5/M6/M7 submodules at creation time.
# Creating it per request = reloading all of that on every API call.
# Creating it once at startup = instant response on every query.

decision_engine: DecisionEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup — initialise heavy objects once.
    Runs on shutdown — cleanup if needed.
    """
    global decision_engine

    print("\n" + "="*55)
    print("  Predictify AI — Starting up")
    print("="*55)

    # Only initialise Decision Engine if product_analysis.csv exists
    # (it's created by POST /run-pipeline)
    if os.path.exists(PRODUCT_ANALYSIS_PATH):
        print("  Initialising Decision Engine...")
        decision_engine = DecisionEngine(
            product_analysis_path = PRODUCT_ANALYSIS_PATH,
            products_path         = PRODUCTS_PATH,
        )
        print("  Decision Engine ready ✓")
    else:
        print("  product_analysis.csv not found.")
        print("  Call POST /run-pipeline first, then restart the server.")
        print("  Decision Engine will be initialised after that.")

    print("="*55 + "\n")

    yield   # server runs here

    # Shutdown
    print("RetailEdge AI shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "RetailEdge AI",
    description = "Retail Inventory Intelligence System for D-Mart",
    version     = "1.0.0",
    lifespan    = lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_for_json(df: pd.DataFrame) -> list:
    """Replaces inf/NaN with None for JSON serialisation."""
    df = df.copy()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.where(pd.notnull(df), None)
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


def _pain_point_summary(df: pd.DataFrame) -> dict:
    """Counts how many products have each pain point."""
    from collections import Counter
    all_pp = [
        pp
        for pps in df["pain_points_triggered"].apply(json.loads)
        for pp in pps
    ]
    return dict(Counter(all_pp))


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# Quick check the service is running
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":          "ok",
        "service":         "Predictify AI",
        "decision_engine": "ready" if decision_engine else "not initialised — run /run-pipeline first",
        "pipeline_output": os.path.exists(PRODUCT_ANALYSIS_PATH),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /run-pipeline
# Nightly batch — computes features + pain points for ALL products
# Saves product_analysis.csv
# After first run: restart server so Decision Engine initialises
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/run-pipeline")
def run_pipeline():
    result = run_nightly_pipeline(
        data_dir   = DATA_DIR,
        output_dir = OUTPUT_DIR,
    )

    flagged = result[result["pain_points_triggered"] != "[]"].copy()
    flagged = flagged.sort_values("composite_risk_score", ascending=False)

    note = None
    if decision_engine is None:
        note = "Decision Engine not yet initialised. Restart the server to load it."

    return {
        "message":              "Pipeline executed successfully",
        "output_csv":           PRODUCT_ANALYSIS_PATH,
        "total_products":       len(result),
        "flagged_count":        len(flagged),
        "high_risk_count":      int((result["composite_risk_score"] > 0.5).sum()),
        "pain_point_breakdown": _pain_point_summary(result),
        "note":                 note,
        "flagged_products":     sanitize_for_json(flagged[[
            "product_id", "store_id", "pain_points_triggered",
            "composite_risk_score", "days_to_expiry",
            "current_stock", "reorder_level",
            "sales_velocity_ratio", "return_rate_30d",
        ]]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /results
# Returns last nightly pipeline output — all 200 products
# Used by dashboard to show store overview
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/results")
def get_results():
    if not os.path.exists(PRODUCT_ANALYSIS_PATH):
        return JSONResponse(
            status_code=404,
            content={"error": "No results found. Run POST /run-pipeline first."}
        )

    df = pd.read_csv(PRODUCT_ANALYSIS_PATH)
    flagged = df[df["pain_points_triggered"] != "[]"].copy()
    flagged = flagged.sort_values("composite_risk_score", ascending=False)

    return {
        "run_date":              df["run_date"].iloc[0] if len(df) > 0 else None,
        "total_products":        len(df),
        "flagged_count":         len(flagged),
        "high_risk_count":       int((df["composite_risk_score"] > 0.5).sum()),
        "pain_point_breakdown":  _pain_point_summary(df),
        "flagged_products":      sanitize_for_json(flagged[[
            "product_id", "store_id", "pain_points_triggered",
            "composite_risk_score", "days_to_expiry",
            "current_stock", "reorder_level",
            "sales_velocity_ratio", "return_rate_30d",
        ]]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /results/{product_id}
# Returns pre-computed feature row for one product
# Used by Decision Engine internally + directly by dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/results/{product_id}")
def get_product_result(product_id: int):
    if not os.path.exists(PRODUCT_ANALYSIS_PATH):
        return JSONResponse(
            status_code=404,
            content={"error": "No results found. Run POST /run-pipeline first."}
        )

    df  = pd.read_csv(PRODUCT_ANALYSIS_PATH)
    row = df[df["product_id"] == product_id]

    if row.empty:
        return JSONResponse(
            status_code=404,
            content={"error": f"product_id {product_id} not found in last run."}
        )

    return sanitize_for_json(row)[0]


# ─────────────────────────────────────────────────────────────────────────────
# GET /decision/{product_id}
# Runs Decision Engine for ONE product on manager query.
#
# Flow:
#   1. Reads pre-computed row from product_analysis.csv (instant)
#   2. Fetches live Reddit urgency signal (stub for now)
#   3. Builds UnifiedSignal (combines both)
#   4. Routes to M5 / M6 in parallel
#   5. M7 explains and saves to recommendations.csv
#   6. Returns full recommendation to manager
#
# Decision Engine object is created ONCE at startup (see lifespan above).
# This endpoint just calls run_for_product() — no heavy loading here.
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/decision/{product_id}")
async def get_decision(product_id: int):

    # Guard: pipeline must have run first
    if not os.path.exists(PRODUCT_ANALYSIS_PATH):
        return JSONResponse(
            status_code=404,
            content={"error": "No analysis found. Run POST /run-pipeline first."}
        )

    # Guard: Decision Engine must be initialised
    if decision_engine is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Decision Engine not initialised.",
                "fix":   "Run POST /run-pipeline, then restart the server."
            }
        )

    result = await decision_engine.run_for_product(product_id)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GET /recommendations
# Returns all recommendations saved by M7 (from recommendations.csv)
# Used by dashboard to show recommendation feed
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/recommendations")
def get_recommendations():
    if not os.path.exists(RECOMMENDATIONS_PATH):
        return JSONResponse(
            status_code=404,
            content={"error": "No recommendations yet. Call GET /decision/{product_id} first."}
        )

    df = pd.read_csv(RECOMMENDATIONS_PATH)

    # Latest recommendation per product (deduplicate)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at", ascending=False)
    df = df.drop_duplicates(subset=["product_id", "action_type"], keep="first")
    df = df.sort_values("action_priority_score", ascending=False)

    return {
        "total":           len(df),
        "recommendations": sanitize_for_json(df[[
            "product_id", "product_name", "action_type",
            "action_priority_score", "pain_points_triggered",
            "rationale", "acted_on",
        ]]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /recommendations/{product_id}
# Returns full recommendation detail for one product
# Including reason_json, projected_impact, rationale
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/recommendations/{product_id}")
def get_product_recommendation(product_id: int):
    if not os.path.exists(RECOMMENDATIONS_PATH):
        return JSONResponse(
            status_code=404,
            content={"error": "No recommendations yet."}
        )

    df  = pd.read_csv(RECOMMENDATIONS_PATH)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df  = df.sort_values("created_at", ascending=False)

    rows = df[df["product_id"] == product_id]

    if rows.empty:
        return JSONResponse(
            status_code=404,
            content={"error": f"No recommendation for product_id {product_id}. "
                               f"Call GET /decision/{product_id} first."}
        )

    # Latest per action type
    rows = rows.drop_duplicates(subset=["action_type"], keep="first")
    return sanitize_for_json(rows)[0] if len(rows) == 1 else sanitize_for_json(rows)
