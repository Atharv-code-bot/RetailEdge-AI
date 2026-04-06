# app/decision_engine/conflict_resolver.py
#
# Section 3.5.7 — Conflict Resolution Rules
#
# Prevents contradictory actions on the same product at the same store.
# Must run AFTER routing_rules.py and BEFORE dispatching to M5/M6/M7.
#
# Four conflict types from build plan:
#   1. FORWARD + REVERSE simultaneously → REVERSE wins
#   2. PRICING increase + COMBO discount → COMBO wins if near expiry
#   3. (Transfer conflicts handled at M5 level — need multi-store data)
#   4. (Destination store capacity conflicts handled at M5 level)

from typing import List, Dict
from app.decision_engine.unified_signal import UnifiedSignal


def resolve_conflicts(signal: UnifiedSignal,
                      action_types: List[str]) -> Dict:
    """
    Takes the list of action_types and resolves any conflicts.

    Returns dict with:
        action_types      : cleaned list after conflict resolution
        conflicts_resolved: number of conflicts found and resolved
        conflict_log      : list of what was resolved and why
    """

    resolved_types = list(action_types)
    conflict_log   = []
    conflicts_resolved = 0

    # ── Conflict 1: FORWARD + REVERSE logistics simultaneously ───────────────
    # A product that needs clearing should NOT also be restocked.
    # REVERSE wins.
    has_logistics = "LOGISTICS" in resolved_types
    needs_reverse = (
        "NEAR_EXPIRY"  in signal.pain_points or
        "HIGH_RETURN"  in signal.pain_points or
        signal.news_sentiment == "NEGATIVE"
    )
    needs_forward = (
        "LOW_STOCK" in signal.pain_points or
        (signal.news_sentiment == "POSITIVE" and signal.sales_velocity > 1.0)
    )

    if has_logistics and needs_reverse and needs_forward:
        # REVERSE wins — log the conflict
        conflict_log.append({
            "conflict": "FORWARD_vs_REVERSE",
            "resolution": "REVERSE wins — clearing product takes priority over restocking",
            "cancelled": "FORWARD_RESTOCK"
        })
        conflicts_resolved += 1
        # Mark as reverse in metadata (actual forward/reverse decision
        # happens inside M5 logistics module based on this flag)

    # ── Conflict 2: PRICING increase + COMBO discount ────────────────────────
    # If near expiry (< 14 days) → COMBO takes priority
    # Otherwise → PRICING takes priority
    has_pricing = "PRICING" in resolved_types
    has_combo   = "COMBO"   in resolved_types

    if has_pricing and has_combo:
        if signal.days_to_expiry < 14:
            # Near expiry — COMBO drives more volume, better than price increase
            resolved_types.remove("PRICING")
            conflict_log.append({
                "conflict": "PRICING_vs_COMBO",
                "resolution": "COMBO wins — days_to_expiry < 14, volume clearing preferred",
                "cancelled": "PRICING"
            })
            conflicts_resolved += 1
        else:
            # Not near expiry — PRICING takes priority
            resolved_types.remove("COMBO")
            conflict_log.append({
                "conflict": "PRICING_vs_COMBO",
                "resolution": "PRICING wins — not near expiry, margin optimisation preferred",
                "cancelled": "COMBO"
            })
            conflicts_resolved += 1

    return {
        "action_types":       resolved_types,
        "conflicts_resolved": conflicts_resolved,
        "conflict_log":       conflict_log,
        "needs_reverse":      needs_reverse,  # passed to M5 to determine direction
        "needs_forward":      needs_forward,
    }
