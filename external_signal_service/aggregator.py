from typing import List, Dict
import numpy as np
from datetime import datetime
from external_signal_service.schemas import ExternalSignals

class SignalAggregator:

    @staticmethod
    def compute_signals(
        product_name: str,
        days_window: int,
        mentions: List[Dict],
        sentiment_scores: List[float]
    ):

        if not mentions:
            return ExternalSignals(
                average_sentiment=0.0,
                positive_ratio=0.0,
                negative_ratio=0.0,
                mention_volume=0,
                unique_threads=0,
                trend_velocity="stable",
                confidence_score=0.0
            )

        avg_sentiment = float(np.mean(sentiment_scores))
        positive_ratio = float(
            sum(1 for s in sentiment_scores if s > 0.05) / len(sentiment_scores)
        )
        negative_ratio = float(
            sum(1 for s in sentiment_scores if s < -0.05) / len(sentiment_scores)
        )

        mention_volume = len(sentiment_scores)
        unique_threads = len(set(m["thread_id"] for m in mentions))
        avg_upvotes = np.mean([m["upvotes"] for m in mentions])

        trend_velocity = SignalAggregator._compute_trend_velocity(
            mentions, days_window
        )

        confidence_score = min(1.0, mention_volume / 200)

        return ExternalSignals(
            average_sentiment=round(avg_sentiment, 3),
            positive_ratio=round(positive_ratio, 3),
            negative_ratio=round(negative_ratio, 3),
            mention_volume=mention_volume,
            unique_threads=unique_threads,
            trend_velocity=trend_velocity,
            confidence_score=round(confidence_score, 3)
        )

    @staticmethod
    def _compute_trend_velocity(mentions: List[Dict], days_window: int):

        midpoint = datetime.utcnow().timestamp() - (days_window / 2) * 86400

        first_half = sum(1 for m in mentions if m["created_utc"] < midpoint)
        second_half = sum(1 for m in mentions if m["created_utc"] >= midpoint)

        if second_half > first_half * 1.2:
            return "increasing"
        elif second_half < first_half * 0.8:
            return "decreasing"
        return "stable"