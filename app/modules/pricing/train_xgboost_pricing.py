# scripts/train_xgboost_pricing.py
#
# Trains XGBoost pricing model on our synthetic D-Mart data.
#
# TWO outputs:
#   1. predictify_xgb_model.pkl  — uses our native features (for xgboost_pricing.py)
#   2. legacy_xgb_model.pkl      — uses your existing FeatureBuilder fields
#                                   (drop-in replacement for your PricePredictor)
#
# Run from project root:
#   python scripts/train_xgboost_pricing.py
#
# Build Plan Section 3.26:
#   Features: current_price, rolling_sales_7d, rolling_sales_30d,
#             stock_to_sales_ratio, seasonality_index, category
#   Target  : optimal_price = price that maximises expected_revenue
#             = selling_price × quantity_sold (from historical sales)

import os
import sys
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder

# ─────────────────────────────────────────────────────────────────────────────
# PATHS — update these to match your local setup
# ─────────────────────────────────────────────────────────────────────────────
SALES_PATH           = "datasamplesv2/sales.csv"
PRODUCTS_PATH        = "datasamplesv2/products.csv"
PRODUCT_ANALYSIS_PATH= "pipeline_output/product_analysis.csv"
MODEL_OUTPUT_DIR     = "models"

PREDICTIFY_MODEL_PATH = os.path.join(MODEL_OUTPUT_DIR, "predictify_xgb_model.pkl")
LEGACY_MODEL_PATH     = os.path.join(MODEL_OUTPUT_DIR, "legacy_xgb_model.pkl")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — BUILD TRAINING DATASET
# ─────────────────────────────────────────────────────────────────────────────

def build_training_data(sales_path, products_path, analysis_path):
    """
    Builds training data from our CSV files.

    Target variable:
        optimal_price = the price point that historically generated
                        maximum revenue for this product
        Computed as: price at the day with highest (price × quantity)
        for each product over its 18-month history

    Features:
        All features from product_analysis.csv + products.csv
    """

    print("Loading data...")
    sales    = pd.read_csv(sales_path)
    products = pd.read_csv(products_path)
    analysis = pd.read_csv(analysis_path)

    sales["sold_at"] = pd.to_datetime(sales["sold_at"])
    sales["revenue"] = sales["selling_price"] * sales["quantity_sold"]

    # ── Compute target: optimal price per product ─────────────────────────────
    # For each product, find the price point that generated most revenue
    # This is what XGBoost learns to predict
    price_revenue = (
        sales.groupby(["product_id", "selling_price"])["revenue"]
        .sum()
        .reset_index()
    )
    # Best price = price with highest total revenue per product
    optimal_prices = (
        price_revenue.loc[price_revenue.groupby("product_id")["revenue"].idxmax()]
        [["product_id", "selling_price"]]
        .rename(columns={"selling_price": "optimal_price"})
    )

    print(f"  Products with optimal price computed: {len(optimal_prices)}")

    # ── Merge features ────────────────────────────────────────────────────────
    df = analysis.merge(optimal_prices, on="product_id", how="inner")
    df = df.merge(
        products[["id","category","cost_price","base_selling_price"]].rename(
            columns={"id":"product_id"}
        ),
        on="product_id", how="left"
    )

    print(f"  Training rows: {len(df)}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — BUILD NATIVE FEATURE MATRIX (for xgboost_pricing.py)
# ─────────────────────────────────────────────────────────────────────────────

NATIVE_FEATURE_COLS = [
    "current_price",
    "rolling_sales_7d",
    "rolling_sales_30d",
    "stock_to_sales_ratio",
    "seasonality_index",
    "sales_velocity_ratio",
    "avg_daily_sales",
    "expiry_risk_score",
    "return_rate_30d",
    "category_encoded",
]

def build_native_features(df: pd.DataFrame):
    """
    Builds feature matrix using our product_analysis.csv columns.
    These map directly to xgboost_pricing.py FEATURE_COLS.
    """
    le = LabelEncoder()
    df = df.copy()
    df["category_encoded"] = le.fit_transform(df["category"].fillna("unknown"))
    df["current_price"]    = df["base_selling_price"]

    # Cap inf values
    df["stock_to_sales_ratio"] = df["stock_to_sales_ratio"].replace(
        [np.inf, -np.inf], 9999.0
    ).fillna(0)
    df["days_of_stock"] = df["days_of_stock"].replace(
        [np.inf, -np.inf], 9999.0
    ).fillna(0)

    X = df[NATIVE_FEATURE_COLS].fillna(0).values
    y = df["optimal_price"].values

    return X, y, le


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — BUILD LEGACY FEATURE MATRIX (compatible with your FeatureBuilder)
# ─────────────────────────────────────────────────────────────────────────────

LEGACY_FEATURE_COLS = [
    "current_price",
    "inventory_pressure_n",
    "demand_momentum_n",
    "sentiment_n",          # stubbed 0.0 — no sentiment in training data
    "urgency_n",            # stubbed 0.0 — no news in training data
    "risk_encoded",
    "price_elasticity_proxy",
    "sentiment_demand_interaction",
    "urgency_inventory_interaction",
]

RISK_ENCODING = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

def build_legacy_features(df: pd.DataFrame):
    """
    Maps our columns to your existing FeatureBuilder field names.
    This produces a model compatible with your PricePredictor.

    Mapping:
        inventory_pressure_score → derived from stock_to_sales_ratio
        demand_momentum_score    → derived from sales_velocity_ratio
        external_sentiment_score → 0.0 (no sentiment in training data)
        urgency_score            → 0.0 (no news in training data)
        risk_level               → derived from composite_risk_score
    """
    df = df.copy()

    def normalize(series, min_val=0, max_val=1):
        return (series - min_val) / (max_val - min_val + 1e-8)

    # Map to your FeatureBuilder fields
    # inventory_pressure: higher stock_to_sales = more pressure
    inv_pressure = df["stock_to_sales_ratio"].replace(
        [np.inf, -np.inf], 100.0
    ).clip(0, 100)
    df["inventory_pressure_n"] = normalize(inv_pressure, 0, 100)

    # demand_momentum: velocity_ratio scaled to 0-100
    df["demand_momentum_n"] = normalize(
        df["sales_velocity_ratio"].fillna(1.0) * 50, 0, 100
    )

    # sentiment and urgency: 0.0 in training (no news data)
    df["sentiment_n"] = 0.0
    df["urgency_n"]   = 0.0

    # risk_level from composite_risk_score
    df["risk_level"] = pd.cut(
        df["composite_risk_score"].fillna(0),
        bins=[0, 0.33, 0.66, 1.0],
        labels=["LOW", "MEDIUM", "HIGH"]
    )
    df["risk_encoded"] = df["risk_level"].map(RISK_ENCODING).fillna(1)

    df["current_price"] = df["base_selling_price"]

    # Derived features (same as your FeatureBuilder)
    df["price_elasticity_proxy"] = (
        df["demand_momentum_n"] / (df["current_price"] + 1e-5)
    )
    df["sentiment_demand_interaction"] = (
        df["sentiment_n"] * df["demand_momentum_n"]
    )
    df["urgency_inventory_interaction"] = (
        df["urgency_n"] * df["inventory_pressure_n"]
    )

    X = df[LEGACY_FEATURE_COLS].fillna(0).values
    y = df["optimal_price"].values

    return X, y


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — TRAIN MODEL
# ─────────────────────────────────────────────────────────────────────────────

def train_xgboost(X, y, model_name="model"):
    """
    Trains XGBoost with GridSearchCV.
    Same setup as your existing ModelTrainer.train()
    """
    print(f"\nTraining {model_name}...")
    print(f"  X shape: {X.shape}")
    print(f"  y range: {y.min():.2f} - {y.max():.2f}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    param_grid = {
        "n_estimators":    [100, 200],
        "max_depth":       [3, 5],
        "learning_rate":   [0.05, 0.1],
        "subsample":       [0.8],
        "colsample_bytree":[0.8],
    }

    xgb = XGBRegressor(
        objective="reg:squarederror",
        random_state=42,
        verbosity=0,
    )

    grid = GridSearchCV(
        estimator  = xgb,
        param_grid = param_grid,
        cv         = 3,
        scoring    = "neg_root_mean_squared_error",
        verbose    = 1,
        n_jobs     = -1,
    )

    grid.fit(X_train, y_train)
    best_model = grid.best_estimator_

    y_pred = best_model.predict(X_test)
    rmse   = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae    = float(mean_absolute_error(y_test, y_pred))
    r2     = float(r2_score(y_test, y_pred))

    print(f"  Best params : {grid.best_params_}")
    print(f"  RMSE        : {rmse:.4f}")
    print(f"  MAE         : {mae:.4f}")
    print(f"  R2          : {r2:.4f}")

    return best_model, {"rmse": rmse, "mae": mae, "r2": r2}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — SAVE MODELS
# ─────────────────────────────────────────────────────────────────────────────

def save_model(model, metrics, feature_cols, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump({
        "model":        model,
        "metrics":      metrics,
        "feature_cols": feature_cols,
    }, path)
    print(f"  Saved → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("  Predictify AI — XGBoost Pricing Model Training")
    print("="*60)

    # Build training data
    df = build_training_data(SALES_PATH, PRODUCTS_PATH, PRODUCT_ANALYSIS_PATH)

    # ── Model 1: Native features (for xgboost_pricing.py) ────────────────────
    print("\n--- Model 1: Native features (Predictify pipeline) ---")
    X_native, y_native, label_encoder = build_native_features(df)
    model_native, metrics_native = train_xgboost(X_native, y_native, "predictify_xgb")
    save_model(model_native, metrics_native, NATIVE_FEATURE_COLS, PREDICTIFY_MODEL_PATH)

    # ── Model 2: Legacy features (compatible with your PricePredictor) ────────
    print("\n--- Model 2: Legacy features (your existing PricePredictor) ---")
    X_legacy, y_legacy = build_legacy_features(df)
    model_legacy, metrics_legacy = train_xgboost(X_legacy, y_legacy, "legacy_xgb")
    save_model(model_legacy, metrics_legacy, LEGACY_FEATURE_COLS, LEGACY_MODEL_PATH)

    # ── Integration instructions ──────────────────────────────────────────────
    print(f"""
{"="*60}
  Training Complete
{"="*60}

  Models saved:
    {PREDICTIFY_MODEL_PATH}  ← use with xgboost_pricing.py
    {LEGACY_MODEL_PATH}       ← use with your PricePredictor

  HOW TO INTEGRATE with pricing.py:
  ──────────────────────────────────
  import joblib
  from app.modules.m6_pricing.pricing import PricingModule

  # Load model
  bundle = joblib.load("{PREDICTIFY_MODEL_PATH}")

  # Pass to PricingModule
  m6 = PricingModule(
      products_path = "datasamplesv2/products.csv",
      xgb_model     = bundle["model"],
      xgb_metrics   = bundle["metrics"],
  )

  HOW TO INTEGRATE with your existing PricePredictor:
  ─────────────────────────────────────────────────────
  import joblib
  bundle = joblib.load("{LEGACY_MODEL_PATH}")

  predictor = PricePredictor(
      model   = bundle["model"],
      metrics = bundle["metrics"],
  )
""")


if __name__ == "__main__":
    main()
