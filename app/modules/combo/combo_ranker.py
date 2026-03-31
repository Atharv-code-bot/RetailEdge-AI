# app/modules/m6_combo/combo_ranker.py
#
# Ranks combo bundles by score.
# Adds FP-Growth confidence to ranking.
#
# What changed from existing code:
#   - Was: used demand_momentum_score, inventory_pressure_score,
#           external_sentiment_score (wrong field names)
#   - Now: uses UnifiedSignal fields directly
#   - Was: no FP-Growth confidence in score
#   - Now: FP-Growth confidence is primary ranking factor
#          (HIGH confidence bundle ranked above LOW confidence one)

from typing import List, Dict
from app.decision_engine.unified_signal import UnifiedSignal

CONFIDENCE_WEIGHT = {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}
STRATEGY_BOOST    = {"inventory_clearance": 2.0, "cross_sell": 1.0,
                     "premium_upsell": 0.8, "llm_assisted": 1.5}


def compute_bundle_score(bundle: Dict, signal: UnifiedSignal) -> float:
    """
    Scores a bundle for ranking.

    Changed from existing:
      - Was: 0.35*demand + 0.35*inventory + 0.20*sentiment + 0.10*price
             (used wrong field names from old system)
      - Now: uses UnifiedSignal fields + FP-Growth confidence
    """

    # FP-Growth confidence is primary factor
    confidence_score = CONFIDENCE_WEIGHT.get(
        bundle.get("confidence_level", "LOW"), 1.0
    )

    # Strategy boost (clearance is most urgent)
    strategy_score = STRATEGY_BOOST.get(bundle.get("strategy", ""), 1.0)

    # Expiry urgency — near-expiry combos ranked higher
    if signal.days_to_expiry < 7:
        expiry_boost = 2.0
    elif signal.days_to_expiry < 14:
        expiry_boost = 1.5
    else:
        expiry_boost = 1.0

    # Composite risk — higher risk = more urgent to bundle
    risk_score = signal.composite_risk_score

    # External signal — positive news = good time to promote bundles
    sentiment_boost = 1.2 if signal.news_sentiment == "POSITIVE" else 1.0

    score = (
        confidence_score
        * strategy_score
        * expiry_boost
        * (1 + risk_score)
        * sentiment_boost
    )

    return round(score, 4)


def rank_bundles(bundles: List[Dict], signal: UnifiedSignal,
                 top_n: int = 3) -> List[Dict]:
    """
    Ranks bundles by score, returns top_n.

    Changed from existing:
      - Was: rank_bundles(bundles, signals) with old signal format
      - Now: rank_bundles(bundles, signal) with UnifiedSignal
    """
    if not bundles:
        return []

    scored = []
    for bundle in bundles:
        score = compute_bundle_score(bundle, signal)
        scored.append({**bundle, "rank_score": score})

    scored.sort(key=lambda x: x["rank_score"], reverse=True)
    return scored[:top_n]
