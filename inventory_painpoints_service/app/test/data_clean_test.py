from app.data.loaders.products_loader import load_products
from app.data.loaders.stores_loader import load_stores
from app.data.loaders.sales_loader import load_sales
from app.data.loaders.inventory_loader import load_inventory

from app.data.cleaners.clean_products import clean_products
from app.data.cleaners.clean_stores import clean_stores
from app.data.cleaners.clean_sales import clean_sales
from app.data.cleaners.clean_inventory import clean_inventory

products = clean_products(load_products("data_samples/products.csv"))
stores = clean_stores(load_stores("data_samples/stores.csv"))
sales = clean_sales(
    load_sales("data_samples/sales.csv"),
    products,
    stores
)
inventory = clean_inventory(
    load_inventory("data_samples/inventory.csv"),
    products,
    stores
)

print(products.shape, stores.shape, sales.shape, inventory.shape)
