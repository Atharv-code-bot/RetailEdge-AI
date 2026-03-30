"""
Predictify AI — Synthetic Retail Dataset Generator
====================================================
Calibrated from real D-Mart Pune sales data (20-Mar-2026).
Generates 18 months of data across 5 Pune stores.

Outputs 5 CSVs ready for PostgreSQL import:
  products.csv, stores.csv, inventory.csv, sales.csv, returns.csv

Statistical properties encoded (from Build Plan Section 3.3):
  - Pareto sales distribution (alpha=1.16) — top 20% products → 80% volume
  - Indian retail seasonality: Diwali 2.5-4x, Monsoon -30%, Summer +100% beverages
  - Near-expiry scenarios: 8% chance for perishables < 30 days shelf life
  - Correlated return rates by category (calibrated from real data)
  - Multi-store demand variation: Aundh (urban) 40% higher than Pimpri
  - Reorder level = avg_daily_sales × lead_time × 1.2

Real data anchors (from sale-20-03-26.xlsx, one day, one Pune store):
  - 3,745 units sold / day across ~1,021 SKUs
  - Median unit price: ₹56
  - Dominant categories: Groceries (Kirana), Biscuits, Detergents
  - DM own-brand products are high-volume (pulses, grains, spices)
"""

import csv
import random
import math
import os
from datetime import date, datetime, timedelta

random.seed(42)

# ─────────────────────────────────────────────────────────────
# TIME RANGE  — 18 months ending today-ish
# ─────────────────────────────────────────────────────────────
START_DATE = date(2024, 9, 1)   # 18 months of history
END_DATE   = date(2026, 2, 28)
DAYS       = (END_DATE - START_DATE).days + 1

# ─────────────────────────────────────────────────────────────
# FESTIVAL CALENDAR  (date, duration_days, spike_mult)
# ─────────────────────────────────────────────────────────────
FESTIVALS = [
    # 2024 festivals
    (date(2024, 10, 2),  1, 1.3),   # Gandhi Jayanti
    (date(2024, 10, 12), 5, 2.2),   # Navratri / Dussehra
    (date(2024, 11, 1),  7, 2.8),   # Diwali season (Diwali 2024 = Nov 1)
    (date(2024, 12, 24), 3, 1.5),   # Christmas
    (date(2024, 12, 30), 3, 1.7),   # New Year
    # 2025 festivals
    (date(2025, 1, 14),  2, 1.3),   # Makar Sankranti
    (date(2025, 1, 26),  2, 1.3),   # Republic Day
    (date(2025, 3, 14),  3, 1.6),   # Holi 2025
    (date(2025, 3, 30),  2, 1.3),   # Gudi Padwa
    (date(2025, 4, 14),  1, 1.2),   # Ambedkar Jayanti
    (date(2025, 8, 15),  2, 1.4),   # Independence Day
    (date(2025, 8, 16),  2, 1.5),   # Janmashtami
    (date(2025, 10, 2),  1, 1.3),   # Gandhi Jayanti
    (date(2025, 10, 20), 5, 2.0),   # Navratri / Dussehra 2025
    (date(2025, 10, 20), 7, 2.8),   # Diwali 2025 (≈ Oct 20)
    (date(2025, 12, 24), 3, 1.5),   # Christmas
    (date(2025, 12, 30), 3, 1.7),   # New Year 2026
    # 2026
    (date(2026, 1, 14),  2, 1.3),   # Makar Sankranti
    (date(2026, 1, 26),  2, 1.3),   # Republic Day
    (date(2026, 3, 2),   3, 1.6),   # Holi 2026
]

# ─────────────────────────────────────────────────────────────
# PRODUCT CATALOG  — 200 products
# Extracted from real Pune D-Mart sales (top-200 by volume),
# supplemented with additional SKUs to hit 200.
#
# Schema: (id, name, category, brand, cost_price, base_price,
#           shelf_life_days, daily_base_units_one_store)
#
# cost_price ≈ 75-85% of base_price (D-Mart margin model)
# daily_base_units = observed units/day at reference store, scaled down
#   from 1-store real data to per-store average across 5 stores
# shelf_life_days = None for non-perishables
# ─────────────────────────────────────────────────────────────

PRODUCTS = [
    # ── CLEANING ACCESSORIES ──
    (1,  "Vim Bar 5RS",                  "Cleaning Accessories", "Vim",          4,    5,   365,  38),
    (2,  "Vim Bar 60g",                  "Cleaning Accessories", "Vim",          4,    5,   365,   3),
    (3,  "VIM BUY 4 GET 2 FREE 90GM",   "Cleaning Accessories", "Vim",         28,   34,   365,   5),
    (4,  "Scotch Brite Scrub Pad",       "Cleaning Accessories", "Scotch-Brite", 30,  45,  None,   3),
    (5,  "Scotch Brite Dish Cloth",      "Cleaning Accessories", "Scotch-Brite", 22,  35,  None,   2),

    # ── BEVERAGES ──
    (6,  "Nescafe Sunrise 1.8gm Sachet", "Beverages",           "Nestle",        1,    2,   365,  30),
    (7,  "Nescafe Sunrise 1.7gm Sachet", "Beverages",           "Nestle",        1,    2,   365,   3),
    (8,  "Bru Coffee 1.2gm Sachet",      "Beverages",           "Bru",           1,    2,   365,   3),
    (9,  "Tata Tea Gold 500g",           "Beverages",           "Tata Tea",     90,  135,   540,   3),
    (10, "Red Label Tea 250g",           "Beverages",           "Brooke Bond",  55,   85,   540,   3),
    (11, "Coca-Cola 600ml",              "Beverages",           "Coca-Cola",    30,   45,    90,   4),
    (12, "Pepsi 600ml",                  "Beverages",           "Pepsi",        28,   42,    90,   3),
    (13, "Bisleri Water 1L",             "Beverages",           "Bisleri",       8,   15,   365,   5),
    (14, "Tropicana Orange 1L",          "Beverages",           "Tropicana",    65,   95,    60,   2),

    # ── GROCERIES (KIRANA) — PULSES & GRAINS (DM own-brand heavy) ──
    (15, "DM Fortune Wheat 1kg",         "Groceries (Kirana)",  "D-Mart",       30,   35,   365,  25),
    (16, "Pani Glass 50pc",              "Groceries (Kirana)",  "Local",        22,   30,  None,  19),
    (17, "Rice 1kg",                     "Groceries (Kirana)",  "Local",        55,   65,   365,  15),
    (18, "DM Udid Mogar 1kg",            "Groceries (Kirana)",  "D-Mart",      110,  130,   365,   7),
    (19, "Sharbati Wheat 1kg",           "Groceries (Kirana)",  "Sharbati",     33,   39,   365,   7),
    (20, "DM Math Mogar 1kg",            "Groceries (Kirana)",  "D-Mart",       80,   95,   365,   6),
    (21, "Swastik Jada Poha 1kg",        "Groceries (Kirana)",  "Swastik",      55,   65,   365,   6),
    (22, "Tea Cup 50pc",                 "Groceries (Kirana)",  "Local",        16,   20,  None,   6),
    (23, "DM Udid Dal 1kg",              "Groceries (Kirana)",  "D-Mart",      100,  120,   365,   5),
    (24, "DM Kalimuch Rice 1kg",         "Groceries (Kirana)",  "D-Mart",       75,   92,   365,   5),
    (25, "DM Mung Mogar 1kg",            "Groceries (Kirana)",  "D-Mart",      105,  125,   365,   4),
    (26, "DM Sugar 5kg",                 "Groceries (Kirana)",  "D-Mart",      188,  225,   730,   4),
    (27, "DM Chana Dal 1kg",             "Groceries (Kirana)",  "D-Mart",       68,   82,   365,   4),
    (28, "DM Shengdana 1kg",             "Groceries (Kirana)",  "D-Mart",      142,  170,   365,   4),
    (29, "Patarwadi Jumbo 100pc",        "Groceries (Kirana)",  "Local",        83,  100,   180,   4),
    (30, "DM Masoor Dal 1kg",            "Groceries (Kirana)",  "D-Mart",       72,   87,   365,   3),
    (31, "DM Cashew W-320 250g",         "Groceries (Kirana)",  "D-Mart",      208,  250,   180,   3),
    (32, "DM Basmati Rice 1kg",          "Groceries (Kirana)",  "D-Mart",       92,  110,   365,   3),
    (33, "DM Sugar 2kg",                 "Groceries (Kirana)",  "D-Mart",       75,   90,   730,   3),
    (34, "Zed Black Manthan Mogra Dhoop","Groceries (Kirana)",  "Zed Black",    12,   15,   730,   3),
    (35, "DM Chavali Mogar 1kg",         "Groceries (Kirana)",  "D-Mart",       96,  115,   365,   3),
    (36, "DM Khobra 500g",              "Groceries (Kirana)",  "D-Mart",      188,  225,   180,   3),
    (37, "Tulsi Rajratna Chilli Pow 500g","Groceries (Kirana)", "Tulsi",       142,  170,   365,   3),
    (38, "DM Mungdal 1kg",               "Groceries (Kirana)",  "D-Mart",      104,  125,   365,   3),
    (39, "DM Sabudana 1kg",              "Groceries (Kirana)",  "D-Mart",       58,   70,   365,   2),
    (40, "DM Sabudana 500g",             "Groceries (Kirana)",  "D-Mart",       30,   37,   365,   2),
    (41, "DM Jada Poha 1kg",             "Groceries (Kirana)",  "D-Mart",       50,   60,   365,   2),
    (42, "DM Khobra 1kg",               "Groceries (Kirana)",  "D-Mart",      375,  450,   180,   2),
    (43, "DM Jeera 100g",               "Groceries (Kirana)",  "D-Mart",       32,   38,   365,   2),
    (44, "DM Shoap 250g",               "Groceries (Kirana)",  "D-Mart",       79,   95,   365,   1),
    (45, "Aashirvaad Atta 5kg",          "Groceries (Kirana)",  "Aashirvaad",  160,  210,   365,   2),
    (46, "India Gate Basmati 5kg",       "Groceries (Kirana)",  "India Gate",  280,  380,   365,   1),
    (47, "Tata Salt 1kg",               "Salt, Sugar & Jaggery","Tata",         12,   18,   730,   8),

    # ── SALT, SUGAR & JAGGERY ──
    (48, "Ankur Salt 1kg",              "Salt, Sugar & Jaggery","Ankur",         8,   10,   730,  16),
    (49, "DM Sugar 1kg",               "Salt, Sugar & Jaggery","D-Mart",        42,   50,   730,   2),
    (50, "Patanjali Desi Khand 1kg",   "Salt, Sugar & Jaggery","Patanjali",     55,   68,   365,   1),

    # ── BISCUITS, COOKIES & WAFERS ──
    (51, "Britannia Bourbon 60g",       "Biscuits, Cookies & Wafers","Britannia",  8,  10,   120,   7),
    (52, "Parle Happy Happy 31.5g",     "Biscuits, Cookies & Wafers","Parle",       3,   4,    90,   5),
    (53, "Parle Gold 68.75g",           "Biscuits, Cookies & Wafers","Parle",       7,   9,    90,   3),
    (54, "Britannia Good Day 60g",      "Biscuits, Cookies & Wafers","Britannia",   8,  10,   120,   3),
    (55, "Britannia Jim Jam 62g",       "Biscuits, Cookies & Wafers","Britannia",   8,  10,   120,   3),
    (56, "Parle-G Biscuit 80g",         "Biscuits, Cookies & Wafers","Parle",       6,   8,    90,   4),
    (57, "Sunfeast Dark Fantasy 75g",   "Biscuits, Cookies & Wafers","ITC",        14,  18,   180,   2),
    (58, "Oreo Biscuit 120g",           "Biscuits, Cookies & Wafers","Cadbury",    16,  20,   180,   2),
    (59, "Patanjali Doodh Biscuit 80g", "Biscuits, Cookies & Wafers","Patanjali",   8,  10,    90,   3),
    (60, "Hide & Seek 120g",            "Biscuits, Cookies & Wafers","Parle",      14,  18,   180,   2),
    (61, "Kream Biscuit Elaichi 100g",  "Biscuits, Cookies & Wafers","Parle",       8,  10,    90,   2),
    (62, "Lays Classic 26g",            "Snacks & Farsan",     "Lays",           10,  10,   180,   3),
    (63, "Haldiram Bhujia 200g",        "Snacks & Farsan",     "Haldiram",       38,  50,   180,   2),
    (64, "Kurkure Masala Munch 90g",    "Snacks & Farsan",     "Kurkure",        10,  10,   180,   3),

    # ── DETERGENTS ──
    (65, "Comfort Fabric Conditioner 18ml","Detergents",         "Comfort",       3,   4,   730,   7),
    (66, "Wheel Bar 180g",              "Detergents",          "Wheel",          8,  10,   730,   7),
    (67, "Sargam Plus Soap 10RS",       "Detergents",          "Sargam",         8,  10,   730,   4),
    (68, "Rin Bar 200g×4",             "Detergents",          "Rin",            35,  43,   730,   4),
    (69, "Sargam Soap 5RS",             "Detergents",          "Sargam",          4,   5,   730,   3),
    (70, "Rin Bar 130+30g Extra",       "Detergents",          "Rin",             8,  10,   730,   4),
    (71, "Wheel Active 2in1 180+50g",   "Detergents",          "Wheel",           8,  10,   730,   5),
    (72, "Surf Excel 1kg",              "Detergents",          "Surf Excel",    155, 210,   730,   2),
    (73, "Ariel Matic 1kg",             "Detergents",          "Ariel",         145, 200,   730,   2),
    (74, "Tide Plus 1kg",               "Detergents",          "Tide",          120, 160,   730,   2),

    # ── READY TO EAT & COOK ──
    (75, "Maggi Noodles 70g",           "Ready To Eat & Cook", "Nestle",        12,  15,   365,   6),
    (76, "Maggi Noodles 560g 8pk",      "Ready To Eat & Cook", "Nestle",        72,  95,   365,   2),
    (77, "Nestle Everyday Milk 15g",    "Ready To Eat & Cook", "Nestle",         8,  10,   365,   3),
    (78, "Knorr Soup Mix 44g",          "Ready To Eat & Cook", "Knorr",         22,  35,   540,   2),
    (79, "MTR Poha Ready Mix 80g",      "Ready To Eat & Cook", "MTR",           18,  25,   365,   2),
    (80, "Yippee Noodles 70g",          "Ready To Eat & Cook", "ITC",           12,  15,   365,   3),
    (81, "DM Ponga 200g",               "Ready To Eat & Cook", "D-Mart",        18,  24,   180,   1),

    # ── MASALA & SPICES ──
    (82, "Maggi Masala 6g Sachet",      "Masala & Spices",     "Nestle",         4,   5,   365,   8),
    (83, "Suruchi Pasta Masala 7g",     "Masala & Spices",     "Suruchi",        4,   5,   365,   4),
    (84, "Everest Garam Masala 50g",    "Masala & Spices",     "Everest",        22,  38,   365,   2),
    (85, "MDH Chhole Masala 100g",      "Masala & Spices",     "MDH",            28,  45,   365,   2),
    (86, "Raj Garam Masala 500g",       "Masala & Spices",     "Raj",           105, 140,   365,   2),
    (87, "Ambari Mirchi Powder 200g",   "Masala & Spices",     "Ambari",         68,  85,   365,   2),
    (88, "Ambari Mirchi Powder 500g",   "Masala & Spices",     "Ambari",        145, 175,   365,   2),
    (89, "Suhana Sambar Masala 50g",    "Masala & Spices",     "Suhana",         18,  25,   365,   2),
    (90, "Badshah Rajwadi Masala 100g", "Masala & Spices",     "Badshah",        32,  45,   365,   2),

    # ── HAIR CARE ──
    (91,  "Clinic Plus Shampoo 6ml",    "Hair Care",           "HUL",            0,   1,  1095,  11),
    (92,  "Indulekha Shampoo 6ml",      "Hair Care",           "Indulekha",      1,   2,  1095,   5),
    (93,  "Dove Shampoo 650ml",         "Hair Care",           "Dove",          195, 285,  1095,   1),
    (94,  "Head & Shoulders 340ml",     "Hair Care",           "H&S",           185, 265,  1095,   1),
    (95,  "Parachute Hair Oil 100ml",   "Hair Care",           "Parachute",      37,  44,  1095,   3),
    (96,  "Vatika Hair Oil 150ml",      "Hair Care",           "Vatika",         70,  95,  1095,   2),

    # ── EDIBLE OIL & GHEE ──
    (97,  "KMC Groundnut Oil 1L",       "Edible Oil & Ghee",   "KMC",           145, 174,   540,   5),
    (98,  "Sunflower Vanaspati 1L",     "Edible Oil & Ghee",   "Vanaspati",     142, 170,   540,   4),
    (99,  "Fortune Sunflower Oil 800g", "Edible Oil & Ghee",   "Fortune",       140, 168,   540,   3),
    (100, "Fortune Soya Plus 840g",     "Edible Oil & Ghee",   "Fortune",       120, 144,   540,   3),
    (101, "Saffola Gold Oil 1L",        "Edible Oil & Ghee",   "Saffola",       110, 155,   540,   2),
    (102, "Amul Ghee 1L",               "Edible Oil & Ghee",   "Amul",          380, 490,    90,   1),

    # ── CHOCOLATE ──
    (103, "Cadbury Dairy Milk 30g",     "Chocolate",           "Cadbury",       18,  20,   365,   5),
    (104, "Kit Kat 2 Finger 12g",       "Chocolate",           "Nestle",        10,  10,   365,   5),
    (105, "5 Star 40g",                 "Chocolate",           "Cadbury",       18,  20,   365,   4),
    (106, "Dairy Milk Silk 60g",        "Chocolate",           "Cadbury",       55,  65,   365,   2),
    (107, "Munch 12g",                  "Chocolate",           "Nestle",         5,   5,   365,   4),
    (108, "Perk 13g",                   "Chocolate",           "Cadbury",        7,   5,   365,   3),
    (109, "Eclairs 10pc",               "Chocolate",           "Cadbury",        8,  10,   365,   4),

    # ── PERSONAL CARE ──
    (110, "Dettol Powder to Liquid 10RS","Personal Hygiene",   "Dettol",         8,  10,  1095,   3),
    (111, "Dettol Soap 75g 4pk",        "Personal Care",       "Dettol",        72, 110,  1095,   2),
    (112, "Lux Soap 100g 3pk",          "Personal Care",       "Lux",           55,  85,  1095,   2),
    (113, "Lifebuoy Soap 125g",         "Personal Care",       "Lifebuoy",      22,  30,  1095,   3),
    (114, "Colgate MaxFresh 300g",      "Oral Care",           "Colgate",        68,  98,  1095,   2),
    (115, "Colgate Strong Teeth 200g",  "Oral Care",           "Colgate",        45,  65,  1095,   3),
    (116, "Pepsodent 200g",             "Oral Care",           "Pepsodent",      38,  55,  1095,   2),
    (117, "Nivea Men Face Wash 100ml",  "Skin Care",           "Nivea",          95, 155,  1095,   1),
    (118, "Dettol Hand Wash 675ml",     "Personal Hygiene",    "Dettol",        160, 215,  1095,   1),
    (119, "Whisper Ultra 30 Pads",      "Personal Hygiene",    "Whisper",        88, 140,  None,   1),

    # ── DRY FRUITS ──
    (120, "DM Cashew W-180 250g",       "Dry Fruits",          "D-Mart",        210, 280,   180,   2),
    (121, "DM Anjeer 250g",             "Dry Fruits",          "D-Mart",        280, 350,   180,   2),
    (122, "DM Sada Pista 100g",         "Dry Fruits",          "D-Mart",        160, 240,   180,   1),
    (123, "DM Badam 250g",              "Dry Fruits",          "D-Mart",        480, 600,   365,   2),
    (124, "DM Badam 100g",              "Dry Fruits",          "D-Mart",        192, 240,   365,   1),
    (125, "DM Tukda Kaju 50g",          "Dry Fruits",          "D-Mart",         84, 105,   180,   1),

    # ── FROZENS & DAIRY ──
    (126, "Amul Cheese Cube 25gm",      "Frozens & Dairy",     "Amul",           15,  18,    30,   4),
    (127, "Amul Butter 100g",           "Frozens & Dairy",     "Amul",           48,  58,    30,   2),
    (128, "Mother Dairy Paneer 200g",   "Frozens & Dairy",     "Mother Dairy",   65,  88,     5,   2),
    (129, "Amul Dahi 400g",             "Frozens & Dairy",     "Amul",           32,  48,     7,   3),
    (130, "Epigamia Greek Yogurt 90g",  "Frozens & Dairy",     "Epigamia",       28,  45,    14,   2),

    # ── PAPER & DISPOSABLE ──
    (131, "Dron Thermocol 50pcs",       "Paper & Disposable",  "Dron",           33,  40,  None,   7),
    (132, "Tissue Paper Box 100 pulls", "Paper & Disposable",  "Selpak",         40,  55,  None,   2),

    # ── HEALTH SUPPLEMENTS ──
    (133, "Horlicks Junior 500g",       "Health Supplements",  "Horlicks",      185, 260,   365,   1),
    (134, "Complan 500g",               "Health Supplements",  "Complan",       195, 275,   365,   1),
    (135, "Protinex Powder 250g",       "Health Supplements",  "Protinex",      280, 380,   365,   1),

    # ── HOUSEHOLD ──
    (136, "Lizol Floor Cleaner 1L",     "Household",           "Lizol",          92, 140,  1095,   2),
    (137, "Harpic Toilet Cleaner 1L",   "Household",           "Harpic",         82, 125,  1095,   2),
    (138, "Colin Glass Cleaner 500ml",  "Household",           "Colin",          48,  75,  1095,   2),
    (139, "Good Knight Refill",         "Household",           "Good Knight",    55,  85,  1095,   2),
    (140, "All Out Liquid 60N",         "Household",           "All Out",       158, 190,  1095,   1),
    (141, "Odomos Mosquito Repellent",  "Household",           "Odomos",         48,  75,  1095,   1),
    (142, "Air Freshener Odonil 75g",   "Air Freshener",       "Odonil",         50,  68,  1095,   2),

    # ── PICKLES & CHUTNEY ──
    (143, "Kissan Mixed Fruit Jam 500g","Pickles & Chutney",   "Kissan",         72,  98,   365,   2),
    (144, "Maggi Hot Sweet Sauce 1kg",  "Pickles & Chutney",   "Maggi",          98, 135,   365,   1),
    (145, "Priya Mango Pickle 300g",    "Pickles & Chutney",   "Priya",          55,  75,   365,   1),

    # ── STATIONERY ──
    (146, "Classmate Notebook 200pg",   "Stationery",          "Classmate",      38,  60,  None,   2),
    (147, "Reynolds Pen 10pk",          "Stationery",          "Reynolds",       28,  49,  None,   2),
    (148, "Apsara Pencil 10pk",         "Stationery",          "Apsara",         18,  30,  None,   2),
    (149, "Fevicol MR 200g",            "Stationery",          "Fevicol",        48,  75,  None,   1),

    # ── POOJA SAMAGRI ──
    (150, "Cycle Agarbatti 50 Sticks",  "Pooja Samagri",       "Cycle",          25,  45,   365,   2),
    (151, "Zed Black Dhoop",            "Pooja Samagri",       "Zed Black",      10,  15,   365,   2),

    # ── BABY CARE ──
    (152, "Pampers Pants M 34pc",       "Baby Care",           "Pampers",       420, 560,  None,   1),
    (153, "Mamypoko Pants M",           "Baby Care",           "Mamypoko",      380, 495,  None,   1),

    # ── CHINESE FOODS / NOODLES ──
    (154, "Ching's Secret Hakka Noodles 150g","Chinese Foods",  "Ching's",       38,  50,   365,   1),
    (155, "Smith & Jones Pasta 200g",   "Chinese Foods",       "S&J",            35,  45,   365,   1),

    # ── BREAKFAST ──
    (156, "Kelloggs Corn Flakes 475g",  "Breakfast & Cereals", "Kelloggs",      155, 210,   365,   1),
    (157, "Quaker Oats 500g",           "Breakfast & Cereals", "Quaker",         90, 130,   365,   1),

    # ── ADDITIONAL DM OWN BRAND ──
    (158, "DM Elichi 25g",              "Groceries (Kirana)",  "D-Mart",        110, 135,   365,   2),
    (159, "DM Turdal 1kg",              "Groceries (Kirana)",  "D-Mart",         95, 115,   365,   2),
    (160, "DM Mohari 500g",             "Groceries (Kirana)",  "D-Mart",         88, 110,   365,   1),
    (161, "DM Naylon Sabudana 500g",    "Groceries (Kirana)",  "D-Mart",         55,  68,   365,   2),
    (162, "DM Khaskhas 100g",           "Groceries (Kirana)",  "D-Mart",        200, 240,   365,   1),
    (163, "DM Laung 25g",               "Groceries (Kirana)",  "D-Mart",         38,  48,   365,   1),
    (164, "DM Ajwan 250g",              "Groceries (Kirana)",  "D-Mart",         90, 115,   365,   1),
    (165, "DM Khobra 250g",             "Groceries (Kirana)",  "D-Mart",         95, 115,   180,   1),
    (166, "DM Nachni 1kg",              "Groceries (Kirana)",  "D-Mart",        108, 130,   365,   1),
    (167, "DM Red Chana 1kg",           "Groceries (Kirana)",  "D-Mart",         58,  70,   365,   1),
    (168, "DM Kapuri Sugar 1kg",        "Groceries (Kirana)",  "D-Mart",         63,  75,   730,   2),
    (169, "DM Barik Shoap 250g",        "Groceries (Kirana)",  "D-Mart",         92, 110,   365,   1),
    (170, "DM Makhane 125g",            "Groceries (Kirana)",  "D-Mart",        117, 140,   180,   1),
    (171, "DM Dhaniya Dal 100g",        "Groceries (Kirana)",  "D-Mart",         42,  50,   365,   1),
    (172, "DM Jeera 250g",              "Groceries (Kirana)",  "D-Mart",         80,  95,   365,   1),

    # ── PERSONAL CARE EXTRA ──
    (173, "Gillette Mach3 Razor",       "Personal Care",       "Gillette",       95, 175,  None,   1),
    (174, "Veet Hair Removal Cream 25g","Personal Care",       "Veet",           38,  55,  1095,   1),
    (175, "Ponds Talcum Powder 100g",   "Personal Care",       "Ponds",          38,  55,  1095,   2),
    (176, "Fair & Lovely Cream 25g",    "Skin Care",           "HUL",            28,  38,  1095,   2),
    (177, "Vaseline Intensive Care 400ml","Skin Care",         "Vaseline",        95, 135,  1095,   1),

    # ── SHAVING ──
    (178, "Gillette Fusion Shave Gel",  "Shaving Needs",       "Gillette",       95, 145,  1095,   1),
    (179, "Dettol After Shave 50ml",    "Shaving Needs",       "Dettol",         38,  55,  1095,   1),

    # ── REMAINING FILLER TO REACH 200 ──
    (180, "Amul Taaza Milk 1L",         "Frozens & Dairy",     "Amul",           48,  62,     2,   4),
    (181, "Britannia Bread 400g",       "Bread & Bakery",      "Britannia",      35,  45,     5,   3),
    (182, "English Oven Bread 400g",    "Bread & Bakery",      "English Oven",   38,  50,     5,   2),
    (183, "Fresh Tomato 1kg",           "Fresh Produce",       "Local Farm",     20,  40,     4,   5),
    (184, "Fresh Onion 1kg",            "Fresh Produce",       "Local Farm",     22,  38,    14,   4),
    (185, "Fresh Potato 1kg",           "Fresh Produce",       "Local Farm",     18,  30,    21,   4),
    (186, "Fresh Banana Dozen",         "Fresh Produce",       "Local Farm",     28,  45,     5,   3),
    (187, "Fresh Spinach 250g",         "Fresh Produce",       "Local Farm",     12,  22,     3,   3),
    (188, "Fresh Capsicum 500g",        "Fresh Produce",       "Local Farm",     22,  38,     5,   2),
    (189, "Syska LED Bulb 9W",          "Electronics",         "Syska",          85, 149,  None,   1),
    (190, "Philips Extension Board 4m", "Electronics",         "Philips",       280, 499,  None,   1),
    (191, "boAt Bassheads 100",         "Electronics",         "boAt",          350, 699,  None,   1),
    (192, "Lego Classic Brick Box",     "Toys",                "LEGO",          650,1499,  None,   1),
    (193, "Funskool Monopoly",          "Toys",                "Funskool",      350, 699,  None,   1),
    (194, "Hot Wheels 5 Car Pack",      "Toys",                "Hot Wheels",    280, 549,  None,   1),
    (195, "Jockey Cotton T-Shirt M",    "Clothing",            "Jockey",        220, 450,  None,   1),
    (196, "Thermal Wear Adults Set",    "Clothing",            "Monte Carlo",   380, 849,  None,   1),
    (197, "Diwali Puja Thali Set",      "Seasonal",            "Local",         180, 399,  None,   1),
    (198, "Rangoli Color Set 12pk",     "Seasonal",            "Tikuli Art",     42,  80,  None,   1),
    (199, "Sunscreen Lakme SPF50 50ml", "Seasonal",            "Lakme",         145, 230,  1095,   1),
    (200, "G S Soya 15kg",              "Groceries (Kirana)",  "GS",           2100,2540,   365,   1),
]

# ─────────────────────────────────────────────────────────────
# STORES — 5 Pune branches with real coordinates
# Demand multipliers calibrated: Aundh (urban) ~40% higher than Pimpri
# ─────────────────────────────────────────────────────────────
STORES = [
    # Single store build — D-Mart Aundh, Pune
    # demand_mult=1.0 (reference store, calibrated to real sales file)
    # Expand to multi-city later by adding rows here
    (1, "D-Mart Aundh", "Pune", 18.5590, 73.8079, "physical", 1.0, 50000),
]

# ─────────────────────────────────────────────────────────────
# CATEGORY BEHAVIOR
# return_rate calibrated from real data (very low — 5/1021 items had returns)
# lead_time_days for reorder level calculation
# ─────────────────────────────────────────────────────────────
CATEGORY_CONFIG = {
    "Cleaning Accessories":        {"return_rate": 0.005, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Beverages":                   {"return_rate": 0.005, "weekend": 1.35, "seasonal": "summer",   "lead_time": 3},
    "Groceries (Kirana)":          {"return_rate": 0.008, "weekend": 1.30, "seasonal": None,       "lead_time": 3},
    "Salt, Sugar & Jaggery":       {"return_rate": 0.003, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Biscuits, Cookies & Wafers":  {"return_rate": 0.005, "weekend": 1.25, "seasonal": None,       "lead_time": 3},
    "Snacks & Farsan":             {"return_rate": 0.005, "weekend": 1.30, "seasonal": None,       "lead_time": 3},
    "Detergents":                  {"return_rate": 0.003, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Ready To Eat & Cook":         {"return_rate": 0.010, "weekend": 1.25, "seasonal": None,       "lead_time": 3},
    "Masala & Spices":             {"return_rate": 0.005, "weekend": 1.15, "seasonal": None,       "lead_time": 3},
    "Hair Care":                   {"return_rate": 0.015, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Edible Oil & Ghee":           {"return_rate": 0.005, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Chocolate":                   {"return_rate": 0.005, "weekend": 1.35, "seasonal": "diwali",   "lead_time": 3},
    "Personal Care":               {"return_rate": 0.020, "weekend": 1.25, "seasonal": None,       "lead_time": 3},
    "Personal Hygiene":            {"return_rate": 0.010, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Oral Care":                   {"return_rate": 0.010, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Dry Fruits":                  {"return_rate": 0.005, "weekend": 1.30, "seasonal": "diwali",   "lead_time": 3},
    "Frozens & Dairy":             {"return_rate": 0.030, "weekend": 1.25, "seasonal": None,       "lead_time": 1},
    "Bread & Bakery":              {"return_rate": 0.020, "weekend": 1.30, "seasonal": None,       "lead_time": 1},
    "Fresh Produce":               {"return_rate": 0.040, "weekend": 1.40, "seasonal": None,       "lead_time": 1},
    "Paper & Disposable":          {"return_rate": 0.005, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Health Supplements":          {"return_rate": 0.015, "weekend": 1.15, "seasonal": None,       "lead_time": 3},
    "Household":                   {"return_rate": 0.010, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Air Freshener":               {"return_rate": 0.010, "weekend": 1.15, "seasonal": None,       "lead_time": 3},
    "Pickles & Chutney":           {"return_rate": 0.010, "weekend": 1.15, "seasonal": None,       "lead_time": 3},
    "Pooja Samagri":               {"return_rate": 0.005, "weekend": 1.20, "seasonal": "festival", "lead_time": 3},
    "Stationery":                  {"return_rate": 0.005, "weekend": 1.10, "seasonal": "school",   "lead_time": 3},
    "Baby Care":                   {"return_rate": 0.020, "weekend": 1.15, "seasonal": None,       "lead_time": 3},
    "Chinese Foods":               {"return_rate": 0.010, "weekend": 1.25, "seasonal": None,       "lead_time": 3},
    "Breakfast & Cereals":         {"return_rate": 0.010, "weekend": 1.20, "seasonal": None,       "lead_time": 3},
    "Skin Care":                   {"return_rate": 0.020, "weekend": 1.20, "seasonal": "summer",   "lead_time": 3},
    "Shaving Needs":               {"return_rate": 0.015, "weekend": 1.15, "seasonal": None,       "lead_time": 3},
    "Electronics":                 {"return_rate": 0.060, "weekend": 1.40, "seasonal": "diwali",   "lead_time": 7},
    "Toys":                        {"return_rate": 0.040, "weekend": 1.50, "seasonal": "diwali",   "lead_time": 5},
    "Clothing":                    {"return_rate": 0.050, "weekend": 1.45, "seasonal": "seasonal", "lead_time": 5},
    "Seasonal":                    {"return_rate": 0.030, "weekend": 1.30, "seasonal": "festival", "lead_time": 3},
}

RETURN_REASONS = {
    "Cleaning Accessories": ["Damaged packaging", "Defective item", "Wrong product"],
    "Beverages":            ["Leaking bottle", "Damaged packaging", "Wrong flavour"],
    "Groceries (Kirana)":   ["Damaged packaging", "Near expiry", "Wrong product", "Quality issue"],
    "Detergents":           ["Damaged packaging", "Wrong variant", "Defective item"],
    "Ready To Eat & Cook":  ["Expired product", "Damaged packaging", "Wrong product"],
    "Masala & Spices":      ["Damaged packaging", "Quality issue", "Near expiry"],
    "Hair Care":            ["Allergic reaction", "Wrong variant", "Damaged packaging"],
    "Personal Care":        ["Allergic reaction", "Wrong variant", "Damaged packaging", "Expired"],
    "Personal Hygiene":     ["Damaged packaging", "Wrong product", "Defective item"],
    "Frozens & Dairy":      ["Expired product", "Spoiled", "Wrong variant"],
    "Bread & Bakery":       ["Mold found", "Incorrect expiry", "Damaged"],
    "Fresh Produce":        ["Spoiled on arrival", "Damaged", "Over-ripened"],
    "Electronics":          ["Defective item", "Wrong product", "Damaged in transit", "Not as described"],
    "Toys":                 ["Broken part", "Missing pieces", "Wrong product", "Safety concern"],
    "Clothing":             ["Wrong size", "Colour mismatch", "Fabric quality", "Customer changed mind"],
    "Seasonal":             ["Festival over", "Damaged packaging", "Wrong product"],
}
DEFAULT_RETURN_REASONS = ["Damaged packaging", "Wrong product", "Quality issue"]

# ─────────────────────────────────────────────────────────────
# PARETO SALES WEIGHT  (alpha=1.16, as per Build Plan 3.3)
# Top 20% of products → ~80% of volume
# ─────────────────────────────────────────────────────────────
def pareto_weights(n, alpha=1.16):
    """Generate Pareto-distributed sales weights for n products."""
    raw = [random.paretovariate(alpha) for _ in range(n)]
    total = sum(raw)
    return [r / total for r in raw]

# ─────────────────────────────────────────────────────────────
# DATE HELPERS
# ─────────────────────────────────────────────────────────────
def date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def festival_mult(d):
    for fdate, duration, mult in FESTIVALS:
        if 0 <= (d - fdate).days < duration:
            return mult
    return 1.0

def seasonal_mult(d, season_type):
    m = d.month
    if season_type == "summer":
        if m in (4, 5, 6): return 2.0    # Build plan: beverages +100% in summer
        if m in (3, 7):     return 1.3
        if m in (11, 12, 1):return 0.6
    elif season_type == "diwali":
        if m in (10, 11):   return 2.5   # Build plan: electronics 2.5-4x Diwali
    elif season_type == "seasonal":       # Clothing
        if m in (10, 11, 12): return 1.6
        if m in (3, 4):       return 1.3
        if m in (7, 8):       return 0.7
    elif season_type == "school":
        if m in (6, 7):       return 2.0
        if m in (1, 2):       return 1.3
    elif season_type == "festival":
        if m in (10, 11):     return 2.5
        if m in (3,):         return 1.8
        if m in (12,):        return 1.5
    return 1.0

def weekend_boost(d, cat_mult):
    return cat_mult if d.weekday() >= 5 else 1.0

# ─────────────────────────────────────────────────────────────
# MONSOON ADJUSTMENT  (Build Plan: Fresh Produce -30% Jun-Aug)
# ─────────────────────────────────────────────────────────────
def monsoon_mult(d, category):
    if d.month in (6, 7, 8) and category == "Fresh Produce":
        return 0.70
    return 1.0

# ─────────────────────────────────────────────────────────────
# GENERATE PRODUCTS
# ─────────────────────────────────────────────────────────────
def generate_products():
    rows = []
    for (pid, name, cat, brand, cost, price, shelf, _daily) in PRODUCTS:
        rows.append({
            "id":                pid,
            "name":              name,
            "category":          cat,
            "brand":             brand,
            "cost_price":        cost,
            "base_selling_price":price,
            "shelf_life_days":   shelf if shelf else "",
        })
    return rows

# ─────────────────────────────────────────────────────────────
# GENERATE STORES
# ─────────────────────────────────────────────────────────────
def generate_stores():
    rows = []
    for (sid, name, city, lat, lng, stype, _dmult, cap) in STORES:
        rows.append({
            "id":            sid,
            "name":          name,
            "location_city": city,
            "location_lat":  lat,
            "location_lng":  lng,
            "store_type":    stype,
            "capacity_units":cap,
        })
    return rows

# ─────────────────────────────────────────────────────────────
# GENERATE SALES
# ─────────────────────────────────────────────────────────────
def generate_sales():
    """
    Calibration: Real data = ~3,745 units/day in one Pune store.
    5 stores × different demand_mult → average ~3,000 units/store/day across 200 products.
    daily_base_units in PRODUCTS is the per-product anchor at the reference store (demand_mult=1.0).
    Pareto weights modulate this so top products sell much more.
    """
    # Assign Pareto weights per product (shuffle so high weights don't always go to low-id products)
    weights = pareto_weights(len(PRODUCTS))
    random.shuffle(weights)
    product_weight = {p[0]: w for p, w in zip(PRODUCTS, weights)}

    # Trend per (product, store): some grow, some decline over 18 months
    trend_map = {}
    for p in PRODUCTS:
        for s in STORES:
            trend_map[(p[0], s[0])] = random.choice(
                ["stable", "stable", "stable", "grow", "decline"]
            )

    sales = []
    cumulative = {}  # (prod_id, store_id) -> total units
    sale_id = 0

    prod_lookup = {p[0]: p for p in PRODUCTS}
    store_lookup = {s[0]: s for s in STORES}

    for store_row in STORES:
        sid, sname, scity, slat, slng, stype, demand_mult, scap = store_row

        for prod_row in PRODUCTS:
            pid, pname, pcat, pbrand, pcost, pprice, pshelf, pbase_daily = prod_row
            cfg = CATEGORY_CONFIG.get(pcat, CATEGORY_CONFIG["Groceries (Kirana)"])
            wknd = cfg["weekend"]
            season = cfg["seasonal"]

            trend = trend_map[(pid, sid)]
            pareto_w = product_weight[pid]

            # Scale base units: product's own anchor × store demand × pareto × 5-store normalisation
            # The 5-store normalisation keeps total volume realistic when summed across stores
            # Real data anchor: pbase_daily is already calibrated to the reference store (demand_mult=1.0)
            effective_base = pbase_daily * demand_mult * (pareto_w * len(PRODUCTS)) * 3.5

            key = (pid, sid)
            total_units = 0

            for d in date_range(START_DATE, END_DATE):
                day_idx = (d - START_DATE).days

                # Trend multiplier
                progress = day_idx / DAYS
                if trend == "grow":
                    trend_m = 1 + 0.5 * progress
                elif trend == "decline":
                    trend_m = 1 - 0.4 * progress
                else:
                    trend_m = 1.0

                daily = (
                    effective_base
                    * trend_m
                    * weekend_boost(d, wknd)
                    * festival_mult(d)
                    * seasonal_mult(d, season)
                    * monsoon_mult(d, pcat)
                    * max(0.1, random.gauss(1.0, 0.18))  # ±18% noise
                )

                units = max(0, round(daily))
                if units == 0:
                    continue

                selling_price = round(pprice * random.uniform(0.95, 1.05), 2)
                # Ensure never below cost + 2% margin
                selling_price = max(selling_price, round(pcost * 1.02, 2))

                sale_id += 1
                sale_ts = datetime(d.year, d.month, d.day,
                                   random.randint(9, 21), random.randint(0, 59), 0)
                sales.append({
                    "id":            sale_id,
                    "product_id":    pid,
                    "store_id":      sid,
                    "quantity_sold": units,
                    "selling_price": selling_price,
                    "sold_at":       d.isoformat(),
                    "channel":       "in_store",
                })
                total_units += units

            cumulative[key] = total_units

    return sales, cumulative

# ─────────────────────────────────────────────────────────────
# GENERATE INVENTORY  (current state as of END_DATE)
# ─────────────────────────────────────────────────────────────
def generate_inventory(cumulative):
    """
    Reorder level = avg_daily_sales × lead_time_days × 1.2  (Build Plan 3.3)
    5% chance low-stock scenario, 5% chance overstock scenario.
    Near-expiry injection: 8% for short shelf-life, 4% for medium.
    """
    inventory = []
    inv_id = 0

    prod_lookup = {p[0]: p for p in PRODUCTS}

    for store_row in STORES:
        sid, sname, scity, slat, slng, stype, demand_mult, scap = store_row

        for prod_row in PRODUCTS:
            pid, pname, pcat, pbrand, pcost, pprice, pshelf, pbase = prod_row
            cfg = CATEGORY_CONFIG.get(pcat, CATEGORY_CONFIG["Groceries (Kirana)"])
            lead_time = cfg["lead_time"]

            total_sold = cumulative.get((pid, sid), 0)
            avg_daily = total_sold / DAYS if DAYS > 0 else pbase

            # Reorder level formula from Build Plan
            reorder_level = max(5, round(avg_daily * lead_time * 1.2))

            # Current stock scenario injection
            scenario_roll = random.random()
            if scenario_roll < 0.05:
                # LOW STOCK / near stockout (pain point trigger)
                current_stock = random.randint(0, max(0, reorder_level - 1))
            elif scenario_roll < 0.10:
                # OVERSTOCK (stagnant pain point)
                current_stock = round(avg_daily * random.uniform(30, 60))
            else:
                # Normal: reasonable buffer
                current_stock = max(0, round(avg_daily * random.uniform(5, 20)))

            # Expiry date logic
            expiry_date = ""
            if pshelf:
                shelf = int(pshelf)
                if shelf < 30:
                    near_expiry_chance = 0.10   # 10% for very short shelf life
                elif shelf < 180:
                    near_expiry_chance = 0.06   # 6% for medium
                else:
                    near_expiry_chance = 0.03   # 3% for long shelf life

                if random.random() < near_expiry_chance:
                    # Near-expiry scenario (1-14 days from END_DATE)
                    days_until_expiry = random.randint(1, 14)
                else:
                    # Normal: somewhere within the product's shelf life
                    low = min(shelf // 4, shelf)
                    high = shelf
                    days_until_expiry = random.randint(max(1, low), max(1, high))

                expiry_date = (END_DATE + timedelta(days=days_until_expiry)).isoformat()

            last_restocked = END_DATE - timedelta(days=random.randint(0, lead_time * 3))

            inv_id += 1
            inventory.append({
                "id":              inv_id,
                "product_id":      pid,
                "store_id":        sid,
                "current_stock":   current_stock,
                "reorder_level":   reorder_level,
                "expiry_date":     expiry_date,
                "last_restocked_at": datetime(last_restocked.year, last_restocked.month,
                                              last_restocked.day, 8, 0, 0).isoformat(),
            })

    return inventory

# ─────────────────────────────────────────────────────────────
# GENERATE RETURNS
# ─────────────────────────────────────────────────────────────
def generate_returns(sales):
    """
    Return rates are category-specific and very low (calibrated from real data).
    Electronics spike post-Diwali. Clothing spikes after festivals.
    Fresh produce spikes in summer (quality issues).
    """
    returns = []
    ret_id = 0

    prod_lookup = {p[0]: p for p in PRODUCTS}

    for sale in sales:
        pid = sale["product_id"]
        prod = prod_lookup[pid]
        pcat = prod[2]
        cfg = CATEGORY_CONFIG.get(pcat, CATEGORY_CONFIG["Groceries (Kirana)"])
        rate = cfg["return_rate"]

        d = date.fromisoformat(sale["sold_at"])
        m = d.month

        # Seasonal return rate boosts (calibrated, small)
        if pcat == "Electronics" and m == 11:      rate *= 1.5
        if pcat == "Clothing" and m in (11, 1):    rate *= 1.4
        if pcat == "Fresh Produce" and m in (5,6): rate *= 1.3
        if pcat == "Frozens & Dairy" and m in (5,6,7): rate *= 1.3

        if random.random() > rate:
            continue

        qty_sold = sale["quantity_sold"]
        qty_returned = random.randint(1, max(1, min(qty_sold, 3)))
        reason = random.choice(RETURN_REASONS.get(pcat, DEFAULT_RETURN_REASONS))

        return_date = d + timedelta(days=random.randint(1, 14))
        if return_date > END_DATE:
            return_date = END_DATE

        ret_id += 1
        returns.append({
            "id":               ret_id,
            "product_id":       pid,
            "store_id":         sale["store_id"],
            "quantity_returned":qty_returned,
            "reason":           reason,
            "returned_at":      return_date.isoformat(),
        })

    return returns

# ─────────────────────────────────────────────────────────────
# CSV WRITER
# ─────────────────────────────────────────────────────────────
def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓  {path}  ({len(rows):,} rows)")

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    out_dir = "/mnt/user-data/outputs/predictify_single_store"
    os.makedirs(out_dir, exist_ok=True)

    print("🏪  Predictify AI — Synthetic Data Generator")
    print(f"    Products: {len(PRODUCTS)} | Stores: {len(STORES)} | Period: {START_DATE} → {END_DATE} ({DAYS} days)\n")

    print("Step 1/5 — Products")
    products = generate_products()
    write_csv(f"{out_dir}/products.csv", products,
              ["id","name","category","brand","cost_price","base_selling_price","shelf_life_days"])

    print("Step 2/5 — Stores")
    stores = generate_stores()
    write_csv(f"{out_dir}/stores.csv", stores,
              ["id","name","location_city","location_lat","location_lng","store_type","capacity_units"])

    print("Step 3/5 — Sales  (largest step — ~18 months × 200 products × 5 stores)")
    sales, cumulative = generate_sales()
    write_csv(f"{out_dir}/sales.csv", sales,
              ["id","product_id","store_id","quantity_sold","selling_price","sold_at","channel"])

    print("Step 4/5 — Inventory")
    inventory = generate_inventory(cumulative)
    write_csv(f"{out_dir}/inventory.csv", inventory,
              ["id","product_id","store_id","current_stock","reorder_level","expiry_date","last_restocked_at"])

    print("Step 5/5 — Returns")
    returns = generate_returns(sales)
    write_csv(f"{out_dir}/returns.csv", returns,
              ["id","product_id","store_id","quantity_returned","reason","returned_at"])

    # ── VALIDATION REPORT ──
    import collections
    total_units = sum(s["quantity_sold"] for s in sales)
    total_rev   = sum(s["quantity_sold"] * s["selling_price"] for s in sales)
    daily_avg   = total_units / (DAYS * len(STORES))

    cat_units = collections.Counter()
    prod_lookup = {p[0]: p for p in PRODUCTS}
    for s in sales:
        cat_units[prod_lookup[s["product_id"]][2]] += s["quantity_sold"]
    top_cats = cat_units.most_common(5)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅  Dataset generated — Predictify AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Products  : {len(products):>8,}
Stores    : {len(stores):>8,}
Sales     : {len(sales):>8,}   rows
Inventory : {len(inventory):>8,}   rows
Returns   : {len(returns):>8,}   rows

Calibration check vs real data
  Real store (1 day)   : ~3,745 units
  Synthetic daily avg  : {daily_avg:>8.0f} units/store
  Total revenue 18m    : ₹{total_rev/1e7:.2f} crore

Top 5 categories by volume:""")
    for cat, units in top_cats:
        print(f"  {cat:<30} {units:>8,} units")
    print(f"""
Output → {out_dir}/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")

if __name__ == "__main__":
    main()
