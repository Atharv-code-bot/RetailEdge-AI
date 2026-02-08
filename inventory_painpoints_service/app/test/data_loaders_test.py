from app.data.loaders.products_loader import load_products
from app.data.loaders.stores_loader import load_stores
from app.data.loaders.sales_loader import load_sales
from app.data.loaders.inventory_loader import load_inventory

products = load_products("data_samples/products.csv")
stores = load_stores("data_samples/stores.csv")
sales = load_sales("data_samples/sales.csv")
inventory = load_inventory("data_samples/inventory.csv")

print(products.head())
print(stores.head())
print(sales.head())
print(inventory.head())
