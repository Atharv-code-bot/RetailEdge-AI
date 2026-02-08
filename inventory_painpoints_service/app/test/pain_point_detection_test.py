# app/test/pain_point_detection_test.py

from app.data.loaders.products_loader import load_products
from app.data.loaders.stores_loader import load_stores
from app.data.loaders.sales_loader import load_sales
from app.data.loaders.inventory_loader import load_inventory

from app.data.cleaners.clean_products import clean_products
from app.data.cleaners.clean_stores import clean_stores
from app.data.cleaners.clean_sales import clean_sales
from app.data.cleaners.clean_inventory import clean_inventory

from app.features.sales_features import compute_sales_features
from app.features.inventory_features import compute_inventory_features
from app.features.feature_assembler import assemble_features

from app.detectors.detector_runner import run_all_detectors


def run_pain_point_detection_test():
    # ---------- LOAD ----------
    products = load_products("data_samples/products.csv")
    stores = load_stores("data_samples/stores.csv")
    sales = load_sales("data_samples/sales.csv")
    inventory = load_inventory("data_samples/inventory.csv")

    # ---------- CLEAN ----------
    products = clean_products(products)
    stores = clean_stores(stores)
    sales = clean_sales(sales, products, stores)
    inventory = clean_inventory(inventory, products, stores)

    # ---------- FEATURES ----------
    sales_features = compute_sales_features(sales)
    inventory_features = compute_inventory_features(inventory, sales_features)
    final_features = assemble_features(inventory_features)

    # ---------- PAIN POINT DETECTION ----------
    pain_points = run_all_detectors(final_features)

    # ---------- BASIC ASSERTIONS ----------
    print("Detected pain points shape:", pain_points.shape)

    assert not pain_points.empty, "❌ No pain points detected — check rules or data"

    required_columns = {
        "product_id",
        "store_id",
        "issue_type",
        "severity",
        "explanation",
    }

    missing = required_columns - set(pain_points.columns)
    if missing:
        raise AssertionError(f"❌ Missing required columns: {missing}")

    allowed_severity = {"LOW", "MEDIUM", "HIGH"}
    assert pain_points["severity"].isin(allowed_severity).all()
    assert pain_points["issue_type"].notna().all()

    # ---------- PRINT ALL OUTPUT ----------
    print("\nAll detected pain points:")
    print(
        pain_points[
            ["product_id", "store_id", "issue_type", "severity"]
        ].to_string(index=False)
    )

    print("\nPain point count by type:")
    print(pain_points["issue_type"].value_counts())

    print("\nPain point count by severity:")
    print(pain_points["severity"].value_counts())

    print("\n✅ Step 4 Pain Point Detection Test PASSED")


if __name__ == "__main__":
    run_pain_point_detection_test()
