# app/modules/m6_pricing/llm_pricing.py
#
# Section 3.27 — Urgent News Pricing Path
#
# Triggered when: urgency_score > 0.5
# Uses Gemini API now → swap with fine-tuned T5-small later
#
# Build Plan output fields:
#   recommended_price, sales_prediction_score, urgency_score,
#   price_manipulation_score, rationale_sentence
#
# TO SWAP TO T5-SMALL LATER:
#   Replace _call_gemini() with _call_t5()
#   Keep everything else identical

import os
import json
import numpy as np
from decision_engine.app.unified_signal import UnifiedSignal

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_MARGIN_FACTOR = 1.02
MAX_PRICE_FACTOR  = 1.50
PMS_PRICE_FACTOR  = 1.30
PMS_THRESHOLD     = 0.10

# Gemini API — set your key in environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


class LLMPricingPath:
    """
    Urgent news pricing path.
    Calls Gemini API to generate price recommendation + rationale.

    TO SWAP TO T5-SMALL:
    ─────────────────────
    Replace _call_gemini() body with:
        from transformers import T5ForConditionalGeneration, T5Tokenizer
        model = T5ForConditionalGeneration.from_pretrained("path/to/finetuned-t5")
        tokenizer = T5Tokenizer.from_pretrained("path/to/finetuned-t5")
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(**inputs, max_length=200)
        return tokenizer.decode(outputs[0], skip_special_tokens=True)
    """

    def predict(self, signal: UnifiedSignal, product_info: dict) -> dict:
        """
        Generates urgent news price recommendation via LLM.
        """

        cost_price  = product_info.get("cost_price",          0)
        base_price  = product_info.get("base_selling_price",  0)
        product_name= product_info.get("name",                "Unknown")
        category    = product_info.get("category",            "Unknown")

        # ── Build prompt (Build Plan Section 3.27 format) ─────────────────────
        trend = self._get_trend_label(signal.sales_velocity)
        prompt = self._build_prompt(
            product_name = product_name,
            category     = category,
            current_price= base_price,
            trend        = trend,
            urgency      = signal.urgency_score,
            sentiment    = signal.news_sentiment,
            pain_points  = signal.pain_points,
        )

        # ── Call LLM ──────────────────────────────────────────────────────────
        llm_response = self._call_gemini(prompt)

        # ── Parse response ────────────────────────────────────────────────────
        recommended_price, rationale = self._parse_response(
            llm_response, base_price, cost_price
        )

        # ── Apply hard constraints (override LLM if needed) ───────────────────
        min_price = round(cost_price * MIN_MARGIN_FACTOR, 2)
        max_price = round(base_price * MAX_PRICE_FACTOR,  2)
        recommended_price = float(np.clip(recommended_price, min_price, max_price))
        recommended_price = round(recommended_price, 2)

        # ── Price Manipulation Score ───────────────────────────────────────────
        pms = (recommended_price - base_price * PMS_PRICE_FACTOR) / base_price
        fairness_clipped = pms > PMS_THRESHOLD
        if fairness_clipped:
            recommended_price = round(base_price * PMS_PRICE_FACTOR, 2)
            rationale += f" [FAIRNESS CLIPPED: price capped at {PMS_PRICE_FACTOR}x base]"

        # ── Direction ─────────────────────────────────────────────────────────
        direction = "INCREASE" if recommended_price > base_price * 1.02 else \
                    "DECREASE" if recommended_price < base_price * 0.98 else "STABLE"

        price_change_pct = round(
            (recommended_price - base_price) / base_price * 100, 2
        )

        # ── Expected revenue ──────────────────────────────────────────────────
        demand_7d = signal.tft_forecast_7d or 0.0
        expected_revenue = round(recommended_price * demand_7d, 2)

        return {
            "path":               "LLM",
            "recommended_price":  recommended_price,
            "original_price":     base_price,
            "price_direction":    direction,
            "price_change_pct":   price_change_pct,
            "expected_revenue_7d":expected_revenue,
            "price_manip_score":  round(float(pms), 4),
            "fairness_clipped":   fairness_clipped,
            "rationale":          rationale,
            "urgency_score":      signal.urgency_score,
            "news_sentiment":     signal.news_sentiment,
            "model":              "gemini-pro",   # update to "t5-small-finetuned" when ready
        }

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_prompt(self, product_name, category, current_price,
                      trend, urgency, sentiment, pain_points) -> str:
        """
        Build Plan Section 3.27 prompt format.
        Structured so T5-small can be fine-tuned on same format later.
        """
        pain_str = ", ".join(pain_points) if pain_points else "none"

        return f"""You are a retail pricing AI for a D-Mart supermarket in India.

Product: {product_name}
Category: {category}
Current price: Rs {current_price}
30-day sales trend: {trend}
News urgency score: {urgency:.2f} (scale 0-1, higher = more urgent)
News sentiment: {sentiment}
Inventory pain points: {pain_str}

Based on this external news signal, suggest a price adjustment.
Respond ONLY in this JSON format, nothing else:
{{
  "recommended_price": <number>,
  "rationale": "<one clear sentence explaining why>"
}}

Rules:
- Price must be between Rs {round(current_price * 0.7, 2)} and Rs {round(current_price * 1.3, 2)}
- If sentiment is NEGATIVE, price should decrease or stay same
- If sentiment is POSITIVE and urgency > 0.7, price can increase moderately
- Keep rationale under 20 words"""

    # ── Gemini API call ───────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str) -> str:
        """
        Calls Gemini API.
        Returns raw text response.

        TO SWAP TO T5-SMALL:
        Replace this entire method body with T5 inference code.
        Prompt format stays the same.
        """
        try:
            import google.generativeai as genai

            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-pro")
            response = model.generate_content(prompt)
            return response.text

        except ImportError:
            # google-generativeai not installed — use rule-based fallback
            return self._rule_based_fallback_response(prompt)

        except Exception as e:
            # API call failed — use rule-based fallback
            return self._rule_based_fallback_response(prompt)

    def _rule_based_fallback_response(self, prompt: str) -> str:
        """
        Fallback when Gemini API is unavailable.
        Extracts context from prompt and returns rule-based JSON.
        """
        # Extract urgency and sentiment from prompt
        urgency  = 0.0
        sentiment = "NEUTRAL"

        for line in prompt.split("\n"):
            if "urgency score:" in line.lower():
                try:
                    urgency = float(line.split(":")[-1].strip().split()[0])
                except:
                    pass
            if "sentiment:" in line.lower():
                if "POSITIVE" in line:
                    sentiment = "POSITIVE"
                elif "NEGATIVE" in line:
                    sentiment = "NEGATIVE"

        # Extract current price
        current_price = 100.0
        for line in prompt.split("\n"):
            if "current price:" in line.lower():
                try:
                    current_price = float(line.split("Rs")[-1].strip())
                except:
                    pass

        if sentiment == "POSITIVE" and urgency > 0.7:
            adjustment = 0.08
            reason = f"Strong positive news signal (urgency {urgency:.2f}) supports price increase"
        elif sentiment == "POSITIVE":
            adjustment = 0.04
            reason = f"Moderate positive news (urgency {urgency:.2f}) supports slight increase"
        elif sentiment == "NEGATIVE" and urgency > 0.6:
            adjustment = -0.12
            reason = f"Negative news signal (urgency {urgency:.2f}) requires price reduction"
        elif sentiment == "NEGATIVE":
            adjustment = -0.06
            reason = f"Mild negative sentiment suggests cautious price reduction"
        else:
            adjustment = 0.0
            reason = "Neutral sentiment — maintaining current price"

        recommended = round(current_price * (1 + adjustment), 2)
        return json.dumps({"recommended_price": recommended, "rationale": reason})

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse_response(self, response: str,
                        base_price: float, cost_price: float) -> tuple:
        """
        Parses LLM JSON response.
        Falls back to base_price if parsing fails.
        """
        try:
            # Strip markdown code blocks if present
            clean = response.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]

            data = json.loads(clean)
            recommended_price = float(data.get("recommended_price", base_price))
            rationale = str(data.get("rationale", "LLM price adjustment"))
            return recommended_price, rationale

        except Exception:
            # Parse failed — return base price unchanged
            return base_price, "LLM response parse failed — maintaining current price"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_trend_label(self, velocity: float) -> str:
        if velocity > 1.3:
            return "accelerating (strong demand)"
        elif velocity > 0.9:
            return "stable"
        elif velocity > 0.7:
            return "slightly declining"
        else:
            return "declining (weak demand)"
