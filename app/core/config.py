import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ── Gemini Config ─────────────────────────────
<<<<<<< HEAD
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID")
GEMINI_PROJECT_NUMBER = os.getenv("GEMINI_PROJECT_NUMBER")

# Model settings
GEMINI_MODEL_NAME = "gemini-pro"

# LLM Safety
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 10))
=======
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant")

# LLM Safety
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 10))


import os

# Project root (RetailEdge AI/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Data paths ─────────────────────────────────────
BASE_DIR   = os.path.join(ROOT_DIR, "inventory_painpoints_service")
DATA_DIR   = os.path.join(BASE_DIR, "datasamplesv2")
OUTPUT_DIR = os.path.join(BASE_DIR, "pipeline_output")

PRODUCT_ANALYSIS_PATH = os.path.join(OUTPUT_DIR, "product_analysis.csv")
PRODUCTS_PATH         = os.path.join(DATA_DIR,   "products.csv")
RECOMMENDATIONS_PATH  = os.path.join(OUTPUT_DIR, "recommendations.csv")

# ── Pricing model ──────────────────────────────────
PRICING_MODEL_PATH = os.path.join(
    ROOT_DIR,
    "app",
    "modules",
    "pricing",
    "models",
    "predictify_xgb_model.pkl"
)
>>>>>>> 4b7054477534506885cd5590b0a9c806aafe7247
