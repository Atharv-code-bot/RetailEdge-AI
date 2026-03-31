import random
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
from .base_provider import BaseSocialProvider


class SyntheticProvider(BaseSocialProvider):

    def __init__(self):
        self.positive_templates = [
            "{product} battery life is insane",
            "Loving the new {product}",
            "{product} exceeded my expectations",
            "Best purchase ever: {product}",
        ]

        self.negative_templates = [
            "{product} is overpriced",
            "Very disappointed with {product}",
            "{product} heating issues are real",
            "Worst upgrade ever: {product}",
        ]

        self.neutral_templates = [
            "Thinking of buying {product}",
            "Is {product} worth it?",
            "{product} vs competitors?",
            "Anyone using {product}?",
        ]

    def _generate_text(self, product: str, sentiment: str):

        if sentiment == "positive":
            template = random.choice(self.positive_templates)
        elif sentiment == "negative":
            template = random.choice(self.negative_templates)
        else:
            template = random.choice(self.neutral_templates)

        return template.format(product=product)

    def fetch_mentions(
        self,
        product_name: str,
        days_window: int,
        subreddits: List[str]
    ) -> List[Dict]:

        now = datetime.utcnow()

        # Simulate trend velocity behavior
        trend_type = random.choice(["increasing", "decreasing", "stable"])

        base_volume = random.randint(80, 200)

        mentions = []

        for i in range(base_volume):

            if trend_type == "increasing":
                day_offset = int(np.random.exponential(scale=days_window / 4))
            elif trend_type == "decreasing":
                day_offset = days_window - int(np.random.exponential(scale=days_window / 4))
            else:
                day_offset = random.randint(0, days_window)

            day_offset = max(0, min(days_window - 1, day_offset))

            created_time = now - timedelta(days=day_offset)

            sentiment_distribution = np.random.choice(
                ["positive", "negative", "neutral"],
                p=[0.4, 0.35, 0.25]
            )

            title = self._generate_text(product_name, sentiment_distribution)
            body = self._generate_text(product_name, sentiment_distribution)

            comments = [
                self._generate_text(product_name, np.random.choice(
                    ["positive", "negative", "neutral"],
                    p=[0.4, 0.35, 0.25]
                ))
                for _ in range(random.randint(2, 8))
            ]

            # Realistic upvote distribution (power law)
            upvotes = int(np.random.pareto(a=2) * 50)

            mentions.append({
                "thread_id": f"synthetic_{i}",
                "title": title,
                "body": body,
                "comments": comments,
                "upvotes": upvotes,
                "created_utc": created_time.timestamp()
            })

        return mentions