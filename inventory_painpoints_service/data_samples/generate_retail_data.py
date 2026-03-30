"""
Synthetic Retail Dataset Generator — Indian Supermarket Chain (D-Mart Style)
============================================================================
Generates 5 CSV files: products, stores, inventory, sales, returns

PATTERN LOGIC:
- Products: 130 products across 10 retail categories with realistic attributes
- Stores: 20 stores across Indian cities (metro + tier-2)
- Sales: 365 days with weekday/weekend multipliers, festival spikes, seasonal trends
- Inventory: Reflects cumulative sales + restocking events; perishables have expiry
- Returns: Category-specific return rates, seasonal patterns, realistic reasons
"""

import csv
import random
import uuid
import math
from datetime import date, datetime, timedelta

random.seed(42)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

START_DATE = date(2024, 1, 1)
END_DATE   = date(2024, 12, 31)
DAYS       = (END_DATE - START_DATE).days + 1

# Festival definitions (date, duration_days, spike_multiplier)
FESTIVALS = [
    (date(2024, 1, 26), 2, 1.4),   # Republic Day
    (date(2024, 3, 25), 3, 1.5),   # Holi
    (date(2024, 4, 9),  2, 1.3),   # Gudi Padwa / Ugadi
    (date(2024, 8, 15), 2, 1.4),   # Independence Day
    (date(2024, 8, 26), 3, 1.5),   # Janmashtami
    (date(2024, 10, 2), 1, 1.3),   # Gandhi Jayanti
    (date(2024, 10, 12), 5, 2.2),  # Navratri / Dussehra
    (date(2024, 11, 1),  7, 2.8),  # Diwali season (Oct 31 = Diwali 2024)
    (date(2024, 12, 24), 3, 1.6),  # Christmas
    (date(2024, 12, 30), 3, 1.8),  # New Year
]

# ─────────────────────────────────────────────
# PRODUCT CATALOG
# ─────────────────────────────────────────────

PRODUCT_TEMPLATES = [
    # (name, category, subcategory, brand, unit_cost, base_price, shelf_life_days)
    # shelf_life_days=None means non-perishable

    # ── GROCERY / FMCG ──
    ("Aashirvaad Atta 5kg",         "Grocery", "Flour & Grains",    "Aashirvaad",  160, 210, 365),
    ("Fortune Sunflower Oil 1L",    "Grocery", "Edible Oil",        "Fortune",      95, 130, 540),
    ("Tata Salt 1kg",               "Grocery", "Staples",           "Tata",         12,  18, 730),
    ("India Gate Basmati 5kg",      "Grocery", "Rice",              "India Gate",  280, 380, 365),
    ("Parle-G Biscuits 800g",       "Grocery", "Snacks",            "Parle",        38,  55,  90),
    ("Britannia Marie Gold 400g",   "Grocery", "Snacks",            "Britannia",    28,  42,  90),
    ("Maggi Noodles 560g (8pk)",    "Grocery", "Instant Food",      "Nestle",       72,  95,  12*30),
    ("Knorr Soup Mix 44g",          "Grocery", "Instant Food",      "Knorr",        22,  35,  18*30),
    ("Haldiram Bhujia 400g",        "Grocery", "Snacks",            "Haldiram",     55,  85,  90),
    ("MDH Chhole Masala 100g",      "Grocery", "Spices",            "MDH",          28,  45, 365),
    ("Everest Garam Masala 50g",    "Grocery", "Spices",            "Everest",      22,  38, 365),
    ("Tata Tea Gold 500g",          "Grocery", "Beverages",         "Tata Tea",     90, 135, 540),
    ("Bru Coffee 200g",             "Grocery", "Beverages",         "Bru",          95, 145, 540),
    ("Kissan Mixed Fruit Jam 500g", "Grocery", "Spreads",           "Kissan",       72,  98, 365),
    ("Amul Ghee 1L",                "Grocery", "Dairy Products",    "Amul",        380, 490,  90),
    ("Horlicks Junior 500g",        "Grocery", "Health Drinks",     "Horlicks",    185, 260, 365),
    ("Complan 500g",                "Grocery", "Health Drinks",     "Complan",     195, 275, 365),
    ("Saffola Gold Oil 1L",         "Grocery", "Edible Oil",        "Saffola",     110, 155, 540),
    ("Surf Excel 1kg",              "Grocery", "Detergent",         "Surf Excel",  155, 210, 730),
    ("Ariel Matic 1kg",             "Grocery", "Detergent",         "Ariel",       145, 200, 730),

    # ── DAIRY ──
    ("Amul Dahi 400g",              "Dairy",   "Curd",              "Amul",         32,  48,   7),
    ("Mother Dairy Paneer 200g",    "Dairy",   "Paneer",            "Mother Dairy", 65,  88,   5),
    ("Amul Butter 500g",            "Dairy",   "Butter",            "Amul",        210, 270,  30),
    ("Amul Taaza Milk 1L",          "Dairy",   "Milk",              "Amul",         48,  62,   2),
    ("Nestle Munch Milkshake 180ml","Dairy",   "Flavoured Milk",    "Nestle",       25,  38,  10),
    ("Amul Cheese Slices 200g",     "Dairy",   "Cheese",            "Amul",         95, 130,  30),
    ("Epigamia Greek Yogurt 90g",   "Dairy",   "Yogurt",            "Epigamia",     28,  45,  14),

    # ── BEVERAGES ──
    ("Coca-Cola 2L",                "Beverages","Carbonated",       "Coca-Cola",    52,  75,  90),
    ("Pepsi 2L",                    "Beverages","Carbonated",       "Pepsi",        50,  72,  90),
    ("Tropicana Orange 1L",         "Beverages","Juices",           "Tropicana",    65,  95,  60),
    ("Real Guava Nectar 1L",        "Beverages","Juices",           "Dabur Real",   58,  88,  60),
    ("Red Bull 250ml",              "Beverages","Energy Drinks",    "Red Bull",     70, 115,  18*30),
    ("Bisleri Water 1L",            "Beverages","Water",            "Bisleri",       8,  15, 365),
    ("Paperboat Aamras 250ml",      "Beverages","Juices",           "Paperboat",    18,  30,  90),

    # ── FRESH PRODUCE ──
    ("Tomato (1kg)",                "Fresh Produce","Vegetables",   "Local Farm",   20,  40,   4),
    ("Onion (1kg)",                 "Fresh Produce","Vegetables",   "Local Farm",   22,  38,  14),
    ("Potato (1kg)",                "Fresh Produce","Vegetables",   "Local Farm",   18,  30,  21),
    ("Banana (Dozen)",              "Fresh Produce","Fruits",       "Local Farm",   28,  45,   5),
    ("Apple Shimla (1kg)",          "Fresh Produce","Fruits",       "HP Orchards",  80, 130,  10),
    ("Capsicum (500g)",             "Fresh Produce","Vegetables",   "Local Farm",   22,  38,   5),
    ("Cauliflower (1pc)",           "Fresh Produce","Vegetables",   "Local Farm",   18,  30,   5),
    ("Mango Alphonso (1kg)",        "Fresh Produce","Fruits",       "Ratnagiri",   120, 200,   4),
    ("Watermelon (1pc)",            "Fresh Produce","Fruits",       "Local Farm",   55,  90,   5),
    ("Spinach (250g)",              "Fresh Produce","Vegetables",   "Local Farm",   12,  22,   3),

    # ── HOUSEHOLD SUPPLIES ──
    ("Lizol Floor Cleaner 1L",      "Household","Floor Cleaners",   "Lizol",        92, 140, 1095),
    ("Harpic Toilet Cleaner 1L",    "Household","Toilet Cleaners",  "Harpic",       82, 125, 1095),
    ("Colin Glass Cleaner 500ml",   "Household","Glass Cleaners",   "Colin",        48,  75, 1095),
    ("Scotch Brite Pad (10pc)",     "Household","Cleaning Aids",    "Scotch-Brite", 40,  65, None),
    ("Good Knight Refill",          "Household","Pest Control",     "Good Knight",  55,  85, 1095),
    ("Odomos Mosquito Repellent",   "Household","Pest Control",     "Odomos",       48,  75, 1095),
    ("Vim Dishwash Bar 400g",       "Household","Dishwash",         "Vim",          28,  45, 1095),
    ("Godrej Jumbo Cello Bag",      "Household","Storage",          "Godrej",       55,  90, None),
    ("Prestige Pressure Cooker 3L", "Household","Cookware",         "Prestige",    550, 850, None),
    ("Pigeon Non-Stick Tawa 24cm",  "Household","Cookware",         "Pigeon",      340, 550, None),

    # ── PERSONAL CARE ──
    ("Dove Shampoo 650ml",          "Personal Care","Hair Care",    "Dove",        195, 285, 1095),
    ("Head & Shoulders 340ml",      "Personal Care","Hair Care",    "H&S",         185, 265, 1095),
    ("Colgate MaxFresh 300g",       "Personal Care","Oral Care",    "Colgate",      68,  98, 1095),
    ("Oral-B Toothbrush (2pk)",     "Personal Care","Oral Care",    "Oral-B",       70, 110, None),
    ("Dettol Soap 75g (4pk)",       "Personal Care","Soaps",        "Dettol",       72, 110, 1095),
    ("Lux Soap 100g (3pk)",         "Personal Care","Soaps",        "Lux",          55,  85, 1095),
    ("Nivea Men Face Wash 100ml",   "Personal Care","Skin Care",    "Nivea",        95, 155, 1095),
    ("Parachute Coconut Oil 500ml", "Personal Care","Hair Care",    "Parachute",    88, 135, 1095),
    ("Gillette Mach3 Razor",        "Personal Care","Grooming",     "Gillette",     95, 175, None),
    ("Whisper Ultra 30 Pads",       "Personal Care","Feminine Care","Whisper",      88, 140, None),

    # ── ELECTRONICS ──
    ("Syska LED Bulb 9W",           "Electronics","Lighting",       "Syska",        85, 149, None),
    ("Philips Extension Board 4m",  "Electronics","Accessories",    "Philips",     280, 499, None),
    ("boAt Bassheads 100 Earphones","Electronics","Audio",          "boAt",        350, 699, None),
    ("Realme Buds 2 Earphones",     "Electronics","Audio",          "Realme",      480, 999, None),
    ("TP-Link Mini Plug",           "Electronics","Smart Home",     "TP-Link",     650,1299, None),
    ("Bajaj Mixer Grinder 500W",    "Electronics","Appliances",    "Bajaj",       1800,3499, None),
    ("Usha Table Fan 400mm",        "Electronics","Appliances",    "Usha",        1400,2499, None),
    ("Orient Wall Fan 400mm",       "Electronics","Appliances",    "Orient",      1100,2199, None),
    ("Havells Iron 1000W",          "Electronics","Appliances",    "Havells",     1200,2299, None),
    ("Prestige Induction 1600W",    "Electronics","Appliances",    "Prestige",    1500,2999, None),

    # ── CLOTHING & LIFESTYLE ──
    ("Jockey Cotton T-Shirt M",     "Clothing", "Men's Wear",       "Jockey",      220, 450, None),
    ("Levi's Denim Shorts",         "Clothing", "Men's Wear",       "Levi's",      550,1299, None),
    ("Peter England Formal Shirt",  "Clothing", "Men's Wear",       "Peter England",350, 799, None),
    ("Van Heusen Trousers",         "Clothing", "Men's Wear",       "Van Heusen",  480,1099, None),
    ("Biba Kurta Set Women",        "Clothing", "Women's Wear",     "Biba",        450, 999, None),
    ("W Brand Ethnic Dress",        "Clothing", "Women's Wear",     "W",           520,1199, None),
    ("Kids Cotton Pyjama Set",      "Clothing", "Kids Wear",        "Babyhug",     180, 399, None),
    ("Woodland Casual Socks 3pk",   "Clothing", "Accessories",      "Woodland",     85, 199, None),
    ("Fruit of Loom Underwear 3pk", "Clothing", "Inner Wear",       "FOTL",        190, 399, None),
    ("Thermal Wear Set Adults",     "Clothing", "Winter Wear",      "Monte Carlo", 380, 849, None),

    # ── TOYS ──
    ("Lego Classic Brick Box",      "Toys",    "Building Toys",     "LEGO",        650,1499, None),
    ("Funskool Monopoly Board Game","Toys",    "Board Games",       "Funskool",    350, 699, None),
    ("Crayola Crayons 64ct",        "Toys",    "Art & Craft",       "Crayola",     160, 329, None),
    ("Hot Wheels 5 Car Pack",       "Toys",    "Die-Cast Cars",     "Hot Wheels",  280, 549, None),
    ("Barbie Doll Set",             "Toys",    "Dolls",             "Barbie",      380, 799, None),
    ("Nerf Blaster Disruptor",      "Toys",    "Outdoor Toys",      "Nerf",        450, 999, None),
    ("Rubik's Cube 3x3",            "Toys",    "Puzzles",           "Rubik's",     180, 349, None),
    ("Funskool Cricket Set",        "Toys",    "Sports Toys",       "Funskool",    250, 499, None),
    ("Milton Kids Water Bottle",    "Toys",    "School Supplies",   "Milton",       90, 199, None),
    ("Camlin Geometry Box",         "Stationery","School Supplies", "Camlin",       42,  79, None),

    # ── STATIONERY ──
    ("Classmate Notebook 200pg",    "Stationery","Notebooks",       "Classmate",    38,  60, None),
    ("Reynolds Pen 10pk",           "Stationery","Pens",            "Reynolds",     28,  49, None),
    ("Apsara Pencil 10pk",          "Stationery","Pencils",         "Apsara",       18,  30, None),
    ("Fevicol MR 200g",             "Stationery","Adhesives",       "Fevicol",      48,  75, None),
    ("Scotch Tape 2pk",             "Stationery","Tapes",           "Scotch",       38,  65, None),

    # ── SEASONAL ──
    ("Diwali Puja Thali Set",       "Seasonal","Festival",          "Local",       180, 399, None),
    ("Rangoli Color Set 12pk",      "Seasonal","Festival",          "Tikuli Art",   42,  80, None),
    ("Agarbatti Incense 50 Sticks", "Seasonal","Puja Items",        "Cycle",        25,  45,  365),
    ("Cold Cream Pond's 100ml",     "Seasonal","Winter Care",       "Pond's",       75, 120, 1095),
    ("Sunscreen Lakme SPF50 50ml",  "Seasonal","Summer Care",       "Lakme",       145, 230, 1095),
    ("Lip Balm Himalaya",           "Seasonal","Winter Care",       "Himalaya",     48,  85, 1095),
    ("Woolens Wash Rin 500ml",      "Seasonal","Winter Laundry",    "Rin",          52,  85, 1095),
    ("Kite Making Kit",             "Seasonal","Festival",          "Local",        35,  65, None),
    ("Holi Color Powder 100g",      "Seasonal","Festival",          "Local",        12,  22, None),
    ("Christmas Decoration Box",    "Seasonal","Festival",          "Archies",      95, 199, None),
]

# ─────────────────────────────────────────────
# STORE DEFINITIONS
# ─────────────────────────────────────────────

STORE_TEMPLATES = [
    ("MUM-001", "Mumbai - Andheri West",     "Mumbai",    "Hypermarket"),
    ("MUM-002", "Mumbai - Thane",            "Mumbai",    "Hypermarket"),
    ("MUM-003", "Mumbai - Navi Mumbai",      "Mumbai",    "Supermarket"),
    ("DEL-001", "Delhi - Rohini",            "Delhi",     "Hypermarket"),
    ("DEL-002", "Delhi - Dwarka",            "Delhi",     "Supermarket"),
    ("BLR-001", "Bengaluru - Koramangala",   "Bengaluru", "Hypermarket"),
    ("BLR-002", "Bengaluru - Whitefield",    "Bengaluru", "Supermarket"),
    ("HYD-001", "Hyderabad - Kukatpally",    "Hyderabad", "Hypermarket"),
    ("HYD-002", "Hyderabad - Gachibowli",    "Hyderabad", "Supermarket"),
    ("CHE-001", "Chennai - T. Nagar",        "Chennai",   "Hypermarket"),
    ("CHE-002", "Chennai - Velachery",       "Chennai",   "Supermarket"),
    ("PUN-001", "Pune - Hinjewadi",          "Pune",      "Supermarket"),
    ("PUN-002", "Pune - Kothrud",            "Pune",      "Supermarket"),
    ("AHM-001", "Ahmedabad - SG Highway",    "Ahmedabad", "Hypermarket"),
    ("AHM-002", "Ahmedabad - Vastrapur",     "Ahmedabad", "Supermarket"),
    ("KOL-001", "Kolkata - New Town",        "Kolkata",   "Hypermarket"),
    ("KOL-002", "Kolkata - Dumdum",          "Kolkata",   "Supermarket"),
    ("JAI-001", "Jaipur - Vaishali Nagar",   "Jaipur",    "Supermarket"),
    ("LUC-001", "Lucknow - Gomti Nagar",     "Lucknow",   "Supermarket"),
    ("NGP-001", "Nagpur - Dharampeth",       "Nagpur",    "Supermarket"),
]

# Store size multipliers (Hypermarket sells more)
STORE_TYPE_MULT = {"Hypermarket": 1.0, "Supermarket": 0.55}

# City-level popularity bias
CITY_MULT = {
    "Mumbai": 1.2, "Delhi": 1.15, "Bengaluru": 1.1,
    "Hyderabad": 1.05, "Chennai": 1.0, "Pune": 0.95,
    "Ahmedabad": 0.90, "Kolkata": 0.95, "Jaipur": 0.75,
    "Lucknow": 0.70, "Nagpur": 0.65,
}

# ─────────────────────────────────────────────
# CATEGORY BEHAVIOR CONFIG
# ─────────────────────────────────────────────

CATEGORY_CONFIG = {
    # category: (base_daily_units_per_store, return_rate, weekend_mult, festival_boost_cats)
    "Grocery":       {"base": 35, "return_rate": 0.02, "weekend": 1.30, "seasonal": None},
    "Dairy":         {"base": 25, "return_rate": 0.03, "weekend": 1.20, "seasonal": None},
    "Beverages":     {"base": 20, "return_rate": 0.01, "weekend": 1.35, "seasonal": "summer"},
    "Fresh Produce": {"base": 40, "return_rate": 0.04, "weekend": 1.40, "seasonal": None},
    "Household":     {"base": 10, "return_rate": 0.02, "weekend": 1.20, "seasonal": None},
    "Personal Care": {"base": 8,  "return_rate": 0.03, "weekend": 1.25, "seasonal": None},
    "Electronics":   {"base": 2,  "return_rate": 0.08, "weekend": 1.40, "seasonal": "diwali"},
    "Clothing":      {"base": 5,  "return_rate": 0.07, "weekend": 1.45, "seasonal": "seasonal"},
    "Toys":          {"base": 4,  "return_rate": 0.05, "weekend": 1.50, "seasonal": "diwali"},
    "Stationery":    {"base": 6,  "return_rate": 0.02, "weekend": 1.10, "seasonal": "school"},
    "Seasonal":      {"base": 8,  "return_rate": 0.04, "weekend": 1.30, "seasonal": "festival"},
}

RETURN_REASONS = {
    "Grocery":       ["Damaged packaging", "Near expiry", "Wrong product", "Quality issue"],
    "Dairy":         ["Expired product", "Spoiled", "Wrong variant", "Damaged packaging"],
    "Beverages":     ["Damaged packaging", "Wrong flavour", "Leaking bottle"],
    "Fresh Produce": ["Spoiled on arrival", "Damaged", "Wrong quantity", "Over-ripened"],
    "Household":     ["Damaged product", "Wrong size", "Defective item", "Not as described"],
    "Personal Care": ["Allergic reaction", "Wrong variant", "Damaged packaging", "Expired"],
    "Electronics":   ["Defective item", "Wrong product", "Damaged in transit", "Not as described", "Customer changed mind"],
    "Clothing":      ["Wrong size", "Colour mismatch", "Fabric quality", "Customer changed mind", "Damage found"],
    "Toys":          ["Broken part", "Missing pieces", "Wrong product", "Safety concern"],
    "Stationery":    ["Damaged packaging", "Wrong product"],
    "Seasonal":      ["Festival over", "Damaged packaging", "Wrong product"],
}

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def new_id():
    return str(uuid.uuid4())

def date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def festival_multiplier(d):
    for fdate, duration, mult in FESTIVALS:
        if 0 <= (d - fdate).days < duration:
            return mult
    return 1.0

def seasonal_multiplier(d, season_type):
    month = d.month
    if season_type == "summer":
        if month in [4, 5, 6]:    return 1.5
        if month in [3, 7]:       return 1.2
        if month in [11, 12, 1]:  return 0.6
    elif season_type == "diwali":
        if month in [10, 11]:     return 1.6
    elif season_type == "seasonal":  # Clothing
        if month in [10, 11, 12]: return 1.5  # Winter wear
        if month in [3, 4]:       return 1.3  # Summer wear
        if month in [7, 8]:       return 0.7  # Monsoon slow
    elif season_type == "school":
        if month in [6, 7]:       return 2.0  # School reopening
        if month in [1, 2]:       return 1.3  # New academic quarter
    elif season_type == "festival":
        if month in [10, 11]:     return 2.5  # Diwali
        if month in [3]:          return 1.8  # Holi
        if month in [12]:         return 1.5  # Christmas
    return 1.0

def weekend_mult(d, cat_mult):
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return cat_mult
    return 1.0

def is_perishable(shelf_life_days):
    return shelf_life_days is not None and shelf_life_days < 180

def compute_expiry(sale_date, shelf_life_days):
    if shelf_life_days is None:
        return None
    return sale_date + timedelta(days=shelf_life_days)

# ─────────────────────────────────────────────
# GENERATE PRODUCTS
# ─────────────────────────────────────────────

def generate_products():
    products = []
    for i, (name, cat, subcat, brand, unit_cost, base_price, shelf_life) in enumerate(PRODUCT_TEMPLATES):
        pid = f"PRD-{i+1:04d}"
        products.append({
            "id": pid,
            "name": name,
            "category": cat,
            "subcategory": subcat,
            "brand": brand,
            "unit_cost": unit_cost,
            "base_price": base_price,
            "shelf_life_days": shelf_life if shelf_life else "",
        })
    return products

# ─────────────────────────────────────────────
# GENERATE STORES
# ─────────────────────────────────────────────

def generate_stores():
    stores = []
    for sid, name, city, stype in STORE_TEMPLATES:
        stores.append({
            "id": sid,
            "name": name,
            "location": city,
            "store_type": stype,
            "created_at": datetime(2022, 1, 1, 9, 0, 0).isoformat(),
        })
    return stores

# ─────────────────────────────────────────────
# GENERATE SALES
# ─────────────────────────────────────────────

def generate_sales(products, stores):
    """Generate daily sales records with realistic patterns."""
    sales = []
    sid_counter = 0

    # Pre-build lookup: product_id -> product dict
    prod_lookup = {p["id"]: p for p in products}
    
    # Track cumulative sales per (product, store) for inventory later
    cumulative_sales = {}  # (prod_id, store_id) -> total_units

    for store in stores:
        store_id = store["id"]
        city = store["location"]
        store_mult = STORE_TYPE_MULT[store["store_type"]] * CITY_MULT[city]

        for prod in products:
            prod_id = prod["id"]
            cat = prod["category"]
            cfg = CATEGORY_CONFIG[cat]
            base = cfg["base"]
            season = cfg["seasonal"]
            wknd = cfg["weekend"]

            # Some products are slow-movers in certain stores (5% chance)
            slow_mover = random.random() < 0.05
            product_store_mult = 0.3 if slow_mover else random.uniform(0.7, 1.3)

            # Trend factor: some products decline over year, some grow
            trend = random.choice(["stable", "stable", "grow", "decline"])
            total = 0

            for d in date_range(START_DATE, END_DATE):
                day_of_year = (d - START_DATE).days  # 0–364

                # Trend
                if trend == "grow":
                    trend_mult = 1 + 0.5 * (day_of_year / 364)
                elif trend == "decline":
                    trend_mult = 1 - 0.4 * (day_of_year / 364)
                else:
                    trend_mult = 1.0

                daily_units = (
                    base
                    * store_mult
                    * product_store_mult
                    * trend_mult
                    * weekend_mult(d, wknd)
                    * festival_multiplier(d)
                    * seasonal_multiplier(d, season)
                    * random.gauss(1.0, 0.15)  # noise
                )

                units = max(0, round(daily_units))
                if units == 0:
                    continue

                selling_price = round(prod["base_price"] * random.uniform(0.95, 1.05), 2)
                sid_counter += 1
                sale_id = f"SAL-{sid_counter:07d}"
                total += units

                sale_ts = datetime(d.year, d.month, d.day,
                                   random.randint(9, 21), random.randint(0, 59))
                sales.append({
                    "id": sale_id,
                    "sale_date": d.isoformat(),
                    "quantity_sold": units,
                    "selling_price": selling_price,
                    "created_at": sale_ts.isoformat(),
                    "product_id": prod_id,
                    "store_id": store_id,
                })

            cumulative_sales[(prod_id, store_id)] = total

    return sales, cumulative_sales

# ─────────────────────────────────────────────
# GENERATE INVENTORY
# ─────────────────────────────────────────────

def generate_inventory(products, stores, cumulative_sales):
    """
    Inventory = starting_stock + restocking - cumulative_sales
    Perishables have expiry_date set (some near-expiry for testing).
    Deliberately creates low-stock and overstock cases.
    """
    inventory = []
    prod_lookup = {p["id"]: p for p in products}

    for store in stores:
        store_id = store["id"]
        for prod in products:
            prod_id = prod["id"]
            cat = prod["category"]
            cfg = CATEGORY_CONFIG[cat]
            shelf_life = prod["shelf_life_days"]

            total_sold = cumulative_sales.get((prod_id, store_id), 0)

            # Reorder level: proportional to daily base volume
            daily_base = cfg["base"] * STORE_TYPE_MULT[store["store_type"]]
            reorder_level = max(5, round(daily_base * 7))  # 7-day safety stock

            # Scenario injection (5% chance each of edge cases)
            scenario = random.random()
            if scenario < 0.05:
                # Low stock / stock-out scenario
                current_stock = random.randint(0, reorder_level - 1)
            elif scenario < 0.10:
                # Overstock scenario
                current_stock = round(total_sold * random.uniform(0.8, 1.5) + daily_base * 60)
            else:
                # Normal: total_sold + buffer stock added for restocking
                restocked = total_sold + round(daily_base * random.uniform(20, 45))
                current_stock = max(0, restocked - total_sold + random.randint(-5, 20))
                current_stock = max(0, round(daily_base * random.uniform(5, 25)))

            # Expiry date logic
            expiry_date = ""
            if shelf_life and shelf_life != "":
                try:
                    sl = int(shelf_life)
                    # Some near-expiry (within 14 days) for perishables
                    near_expiry_chance = 0.08 if sl < 30 else 0.04
                    if random.random() < near_expiry_chance:
                        days_until_expiry = random.randint(1, 14)
                    else:
                        days_until_expiry = random.randint(sl // 4, sl)
                    expiry_date = (END_DATE + timedelta(days=days_until_expiry - 365)).isoformat()
                    # Make some actually near-expiry from now (from END_DATE perspective)
                    expiry_date = (date(2025, 1, 1) + timedelta(days=days_until_expiry)).isoformat()
                except:
                    expiry_date = ""

            last_updated_days_ago = random.randint(0, 7)
            last_updated = datetime(2024, 12, 31) - timedelta(days=last_updated_days_ago)

            inventory.append({
                "id": new_id(),
                "product_id": prod_id,
                "store_id": store_id,
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "expiry_date": expiry_date,
                "last_updated": last_updated.isoformat(),
                "created_at": datetime(2024, 1, 1, 8, 0, 0).isoformat(),
            })

    return inventory

# ─────────────────────────────────────────────
# GENERATE RETURNS
# ─────────────────────────────────────────────

def generate_returns(sales, products):
    """
    Returns are derived from sales records.
    Each sale row has a probability of generating a return based on category.
    """
    returns = []
    prod_lookup = {p["id"]: p for p in products}
    ret_counter = 0

    for sale in sales:
        prod_id = sale["product_id"]
        prod = prod_lookup[prod_id]
        cat = prod["category"]
        cfg = CATEGORY_CONFIG[cat]
        base_rate = cfg["return_rate"]

        # Seasonal return rate boost
        d = date.fromisoformat(sale["sale_date"])
        month = d.month
        # Electronics returns spike post-Diwali (Nov)
        if cat == "Electronics" and month == 11:
            base_rate *= 1.5
        # Clothing returns after festivals
        if cat == "Clothing" and month in [11, 1]:
            base_rate *= 1.4
        # Fresh produce returns highest in summer (quality)
        if cat == "Fresh Produce" and month in [5, 6]:
            base_rate *= 1.3

        # Apply return probability
        if random.random() > base_rate:
            continue

        units_sold = sale["quantity_sold"]
        qty_returned = random.randint(1, max(1, min(units_sold, 3)))
        reason = random.choice(RETURN_REASONS.get(cat, ["Damaged product"]))

        return_date = date.fromisoformat(sale["sale_date"]) + timedelta(days=random.randint(1, 14))
        if return_date > END_DATE:
            return_date = END_DATE

        ret_counter += 1
        returns.append({
            "id": f"RET-{ret_counter:07d}",
            "product_id": prod_id,
            "return_date": return_date.isoformat(),
            "quantity_returned": qty_returned,
            "reason": reason,
            "created_at": datetime(return_date.year, return_date.month, return_date.day,
                                   random.randint(9, 20), random.randint(0, 59)).isoformat(),
            "store_id": sale["store_id"],
        })

    return returns

# ─────────────────────────────────────────────
# CSV WRITER
# ─────────────────────────────────────────────

def write_csv(filepath, rows, fieldnames):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ {filepath}  ({len(rows):,} rows)")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    import os
    out_dir = "/mnt/user-data/outputs/retail_dataset"
    os.makedirs(out_dir, exist_ok=True)

    print("🏪  Generating D-Mart style synthetic retail dataset...\n")

    print("Step 1/5 — Products")
    products = generate_products()
    write_csv(f"{out_dir}/products.csv", products,
              ["id","name","category","subcategory","brand","unit_cost","base_price","shelf_life_days"])

    print("Step 2/5 — Stores")
    stores = generate_stores()
    write_csv(f"{out_dir}/stores.csv", stores,
              ["id","name","location","store_type","created_at"])

    print("Step 3/5 — Sales (this takes a moment…)")
    sales, cumulative_sales = generate_sales(products, stores)
    write_csv(f"{out_dir}/sales.csv", sales,
              ["id","sale_date","quantity_sold","selling_price","created_at","product_id","store_id"])

    print("Step 4/5 — Inventory")
    inventory = generate_inventory(products, stores, cumulative_sales)
    write_csv(f"{out_dir}/inventory.csv", inventory,
              ["id","product_id","store_id","current_stock","reorder_level","expiry_date","last_updated","created_at"])

    print("Step 5/5 — Returns")
    returns = generate_returns(sales, products)
    write_csv(f"{out_dir}/returns.csv", returns,
              ["id","product_id","return_date","quantity_returned","reason","created_at","store_id"])

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅  Dataset generated successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Products  : {len(products):>8,}
Stores    : {len(stores):>8,}
Sales     : {len(sales):>8,}
Inventory : {len(inventory):>8,}
Returns   : {len(returns):>8,}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Output    : {out_dir}/
""")

if __name__ == "__main__":
    main()
