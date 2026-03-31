from pydantic import BaseModel
from typing import List, Optional

class RedditTrendRequest(BaseModel):
    product_name: str
    days_window: int = 30
    subreddits: Optional[List[str]] = [
        "technology",
        "gadgets",
        "india",
        "reviews"
    ]

class ExternalSignals(BaseModel):
    average_sentiment: float
    positive_ratio: float
    negative_ratio: float
    mention_volume: int
    unique_threads: int
    trend_velocity: str
    confidence_score: float

class RedditTrendResponse(BaseModel):
    product_name: str
    time_window_days: int
    external_signals: ExternalSignals