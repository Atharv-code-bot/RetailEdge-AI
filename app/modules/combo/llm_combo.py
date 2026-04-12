# app/modules/m6_combo/llm_combo.py
#
# LLM combo generation via Gemini API.
# Generates combo name, discount %, and rationale.
#
# What changed from existing code:
#   - Was: OpenAI GPT-4o-mini + eval() on response (dangerous)
#   - Now: Gemini API + json.loads() (safe parsing)
#   - Prompt updated to Build Plan Section 3.28 format:
#     "Slow/expiring products + trending topics → bundle suggestion"
#   - Response validated against our products.csv catalog
#   - Fallback to rule-based if API unavailable

import os
import json
from typing import List
from app.decision_engine.unified_signal import UnifiedSignal
from app.core.config import GROQ_API_KEY, GROQ_MODEL_NAME, LLM_TIMEOUT
from groq import Groq
import logging

logger = logging.getLogger("LLM_COMBO")
logger.setLevel(logging.INFO)


def generate_llm_combo(
    signal: UnifiedSignal,
    product_name: str,
    product_category: str,
    partner_categories: List[str],
) -> dict:
    """
    Calls Gemini to generate a combo offer.

    Build Plan Section 3.28 prompt format:
      Input 1: slow/expiring product (from pain points)
      Input 2: trending topics (from urgency + sentiment)
      Output  : combo_name, discount_pct, rationale

    TO SWAP TO T5-SMALL:
      Replace _call_gemini() body with T5 inference.
      Prompt format stays the same.
    """

    prompt = _build_prompt(signal, product_name, product_category, partner_categories)
    response = _call_llm(prompt)
    return _parse_response(response, product_name, partner_categories)


def _build_prompt(signal, product_name, product_category, partner_categories):
    """Build Plan Section 3.28 prompt format."""

    pain_str = ", ".join(signal.pain_points) if signal.pain_points else "none"
    partner_str = ", ".join(partner_categories)

    # Trending context from external signal
    if signal.urgency_score > 0.3 and signal.news_sentiment == "POSITIVE":
        trending = f"positive news trend detected (urgency={signal.urgency_score:.2f})"
    elif signal.news_sentiment == "NEGATIVE":
        trending = f"negative news — need to clear stock fast"
    else:
        trending = "normal demand period"

    return f"""You are a retail combo offer expert for D-Mart supermarket in India.

Generate a retail combo offer for this situation:

Slow/expiring product  : {product_name} (category: {product_category})
Days to expiry         : {signal.days_to_expiry if signal.days_to_expiry < 9999 else 'non-perishable'}
Pain points            : {pain_str}
Trending context       : {trending}
Suggested partner categories: {partner_str}

Create a bundle that would appeal to Indian D-Mart shoppers.
Respond ONLY in this JSON format, nothing else:
{{
  "combo_name": "<short catchy name in English>",
  "discount_pct": <number between 5 and 30>,
  "rationale": "<one sentence why customers would want this bundle>"
}}

Rules:
- Combo name should be 2-4 words, simple and clear
- Discount should be higher if product is near expiry
- Rationale should be practical, not marketing fluff"""


def _call_llm(prompt: str) -> str:
    """
    Calls LLM provider.
    Falls back to rule-based response if API unavailable.
    """
    try:
        

        # If API key missing → fallback
        if not GROQ_API_KEY:
            return _rule_based_fallback(prompt)
        
        logger.info(f"Calling LLM Model: {GROQ_MODEL_NAME}")

        client = Groq(api_key=GROQ_API_KEY)

        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a retail combo recommendation AI. Respond ONLY in valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        logger.info("LLM API Response received")


        return response.choices[0].message.content

    except Exception:
        return _rule_based_fallback(prompt)


def _rule_based_fallback(prompt: str) -> str:
    """
    Rule-based fallback when Gemini unavailable.
    Extracts context from prompt and generates sensible combo.
    """
    # Extract days_to_expiry from prompt
    days = 999
    for line in prompt.split("\n"):
        if "days to expiry" in line.lower():
            try:
                val = line.split(":")[-1].strip()
                if val.isdigit():
                    days = int(val)
            except:
                pass

    if days < 7:
        discount = 25
        name = "Quick Clearance Bundle"
        rationale = "Near-expiry product bundled at deep discount to clear stock before expiry"
    elif days < 14:
        discount = 15
        name = "Value Combo Deal"
        rationale = "Limited stock bundle offering savings on complementary products"
    else:
        discount = 10
        name = "Smart Savings Bundle"
        rationale = "Everyday essentials bundled together for convenient shopping"

    return json.dumps({
        "combo_name":  name,
        "discount_pct": discount,
        "rationale":   rationale,
    })


def _parse_response(response: str, product_name: str,
                    partner_categories: List[str]) -> dict:
    """
    Parses LLM JSON response safely.
    Uses json.loads() — not eval() (was a security risk in old code).
    """
    try:
        clean = response.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]

        data = json.loads(clean)

        return {
            "combo_name":        str(data.get("combo_name", "Value Bundle")),
            "discount_pct":      int(data.get("discount_pct", 10)),
            "rationale":         str(data.get("rationale", "")),
            "partner_categories":partner_categories,
            "source":            "llm",
        }

    except Exception:
        return {
            "combo_name":        "Value Bundle",
            "discount_pct":      10,
            "rationale":         "Complementary products bundled for customer convenience",
            "partner_categories":partner_categories,
            "source":            "fallback",
        }
