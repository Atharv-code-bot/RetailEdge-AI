# app/modules/m7_xai/llm_narrator.py
#
# Section 3.32 — LLM Narration grounded in SHAP values
#
# Takes the structured 4-part explanation and generates
# one clear sentence for the store manager.
#
# Build Plan Section 3.34:
#   "Format SHAP values into a structured prompt with context:
#    'The top factors increasing the markdown recommendation are:
#     days_to_expiry (contribution: +0.41, value: 6 days),
#     return_rate (contribution: +0.28, value: 0.22)...
#     Generate one clear sentence explaining this to a store manager.'"
#
# Uses Gemini API (same as M6). Fallback to template-based sentence.

import os
import json
from typing import List
from app.core.config import GROQ_API_KEY, GROQ_MODEL_NAME, LLM_TIMEOUT
from groq import Groq
import logging

logger = logging.getLogger("LLM_NARRATOR")
logger.setLevel(logging.INFO)



def generate_rationale(
    action_type: str,
    trigger: dict,
    evidence: dict,
    reasoning: dict,
    projection: dict,
    shap_values: List[dict],
) -> str:
    """
    Generates one clear manager-facing sentence explaining the recommendation.
    Grounded in SHAP values to prevent hallucination.

    Returns: string rationale
    """

    prompt = _build_prompt(
        action_type, trigger, evidence, reasoning, projection, shap_values
    )
    return _call_llm(prompt)


def _build_prompt(action_type, trigger, evidence, reasoning,
                  projection, shap_values) -> str:
    """
    Section 3.34 prompt format.
    SHAP values explicitly included to ground LLM output.
    """

    shap_str = ""
    if shap_values:
        shap_lines = []
        for s in shap_values[:3]:
            shap_lines.append(
                f"{s['feature']} (contribution: {s['direction']}{abs(s['shap_value']):.3f}, "
                f"value: {s['raw_value']})"
            )
        shap_str = "Top contributing factors:\n" + "\n".join(shap_lines)
    else:
        shap_str = "Key signals: " + ", ".join(trigger.get("pain_points", []))

    pain_points = trigger.get("pain_points", [])
    risk        = trigger.get("composite_risk_score", 0)
    urgency     = evidence.get("urgency_score", 0)
    days_expiry = evidence.get("days_to_expiry", 9999)
    velocity    = evidence.get("sales_velocity_ratio", 1.0)
    stock       = evidence.get("current_stock", 0)

    # Action-specific context
    if action_type == "LOGISTICS":
        action_context = (
            f"Action: {reasoning.get('action_chosen', 'MARKDOWN')}. "
            f"Expected revenue recovery: Rs{projection.get('revenue_recovery', 0):.0f}. "
            f"Days to clear: {projection.get('days_to_clear', '?')}."
        )
    elif action_type == "PRICING":
        action_context = (
            f"Action: Price {reasoning.get('price_direction', 'STABLE')} "
            f"{abs(reasoning.get('price_change_pct', 0)):.1f}% "
            f"to Rs{projection.get('recommended_price', 0)}. "
            f"Path: {reasoning.get('path_chosen', 'XGBOOST')}."
        )
    elif action_type == "COMBO":
        action_context = (
            f"Action: Bundle offer. "
            f"Confidence: {reasoning.get('confidence_level', 'LOW')}. "
            f"Expected revenue: Rs{projection.get('projected_revenue', 0):.0f}."
        )
    else:
        action_context = f"Action: {action_type}"

    return f"""You are an AI assistant explaining a retail inventory recommendation to a D-Mart store manager.

{shap_str}

Situation:
- Pain points: {pain_points}
- Risk score: {risk:.2f}
- News urgency: {urgency:.2f}
- Days to expiry: {days_expiry if days_expiry < 9999 else 'non-perishable'}
- Sales velocity: {velocity:.2f} (1.0 = normal, < 0.7 = stagnant)
- Current stock: {stock} units

{action_context}

Generate ONE clear sentence (max 25 words) explaining this recommendation to a store manager.
Be specific about numbers. Use simple language. No jargon."""




def _call_llm(prompt: str) -> str:
    """
    Calls LLM provider.
    Falls back to rule-based response if API unavailable.
    """
    try:
        

        
        logger.info(f"Calling XAI LLM Model: {GROQ_MODEL_NAME}")

        client = Groq(api_key=GROQ_API_KEY)

        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        logger.info("XAILLM API Response received")
        return response.choices[0].message.content.strip()
    except Exception:
        return _template_rationale(prompt)



def _template_rationale(prompt: str) -> str:
    """
    Template-based rationale when Gemini unavailable.
    Extracts key numbers from prompt and generates a sentence.
    """
    lines = prompt.split("\n")
    action = "take action"
    revenue = 0
    days = None

    for line in lines:
        if "Action:" in line:
            action = line.replace("Action:", "").strip()
        if "revenue recovery" in line.lower() or "revenue:" in line.lower():
            try:
                import re
                nums = re.findall(r"Rs(\d+)", line)
                if nums:
                    revenue = int(nums[0])
            except:
                pass
        if "Days to clear:" in line:
            try:
                days = line.split(":")[-1].strip()
            except:
                pass

    if revenue > 0 and days:
        return (f"Recommended to {action} — "
                f"expected to recover Rs{revenue} in {days} days.")
    elif revenue > 0:
        return f"Recommended to {action} — expected revenue recovery Rs{revenue}."
    else:
        return f"Action recommended based on inventory risk analysis."
