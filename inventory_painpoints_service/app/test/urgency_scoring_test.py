# app/test/urgency_scoring_test.py

from app.test.pain_point_detection_test import run_pain_point_detection_test
from app.scoring.urgency_scoring import compute_urgency_scores
from app.detectors.detector_runner import run_all_detectors
from app.test.pain_point_detection_test import (
    load_products,
    load_stores,
    load_sales,
    load_inventory,
    clean_products,
    clean_stores,
    clean_sales,
    clean_inventory,
    compute_sales_features,
    compute_inventory_features,
    assemble_features,
)


def run_urgency_scoring_test():
    # Re-run pipeline up to pain points
    products = load_products("data_samples/products.csv")
    stores = load_stores("data_samples/stores.csv")
    sales = load_sales("data_samples/sales.csv")
    inventory = load_inventory("data_samples/inventory.csv")

    products = clean_products(products)
    stores = clean_stores(stores)
    sales = clean_sales(sales, products, stores)
    inventory = clean_inventory(inventory, products, stores)

    sales_features = compute_sales_features(sales)
    inventory_features = compute_inventory_features(inventory, sales_features)
    final_features = assemble_features(inventory_features)

    pain_points = run_all_detectors(final_features)

    urgency = compute_urgency_scores(pain_points)

    print("Urgency score table shape:", urgency.shape)
    print("\nSample urgency scores:")
    print(urgency.head(10))

    assert not urgency.empty
    assert urgency["urgency_score"].between(0, 100).all()

    print("\n✅ Step 5 Urgency Scoring Test PASSED")


if __name__ == "__main__":
    run_urgency_scoring_test()
