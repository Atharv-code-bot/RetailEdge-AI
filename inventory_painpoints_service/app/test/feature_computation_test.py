# app/test/feature_computation_test.py

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


def run_feature_computation_test():
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

    # ---------- FEATURE COMPUTATION ----------
    sales_features = compute_sales_features(sales)
    inventory_features = compute_inventory_features(inventory, sales_features)

    final_features = assemble_features(inventory_features)

    # ---------- BASIC ASSERTIONS ----------
    print("Final feature table shape:", final_features.shape)

    expected_columns = {
        "product_id",
        "store_id",
        "current_stock",
        "recent_units",
        "previous_units",
        "avg_daily_sales",
        "sales_change_pct",
        "days_of_stock",
        "reorder_level",
    }

    missing_cols = expected_columns - set(final_features.columns)
    if missing_cols:
        raise AssertionError(f"Missing feature columns: {missing_cols}")

    # Check no negative values where impossible
    assert (final_features["current_stock"] >= 0).all()
    assert (final_features["avg_daily_sales"] >= 0).all()
    assert (final_features["reorder_level"] >= 0).all()

    # days_of_stock sanity
    assert (final_features["days_of_stock"] >= 0).all()

    print("✅ Step 3 Feature Computation Test PASSED")


if __name__ == "__main__":
    run_feature_computation_test()
