import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ── Gemini Config ─────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID")
GEMINI_PROJECT_NUMBER = os.getenv("GEMINI_PROJECT_NUMBER")

# Model settings
GEMINI_MODEL_NAME = "gemini-pro"

# LLM Safety
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 10))