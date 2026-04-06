from fastapi import FastAPI, HTTPException
import logging
import numpy as np
from external_signal_service.schemas import RedditTrendRequest, RedditTrendResponse
from external_signal_service.sentiment import SentimentEngine
from external_signal_service.aggregator import SignalAggregator
from external_signal_service.providers.synthetic_provider import SyntheticProvider
from external_signal_service.providers.reddit_provider import RedditProvider

logging.basicConfig(level=logging.INFO)

# app = FastAPI(title="Predictify AI - Reddit Trend Moduln e")

USE_SYNTHETIC = True  # toggle here

if USE_SYNTHETIC:
    provider = SyntheticProvider()
else:
    provider = RedditProvider()

sentiment_engine = SentimentEngine()


# @app.post("/reddit-trend", response_model=RedditTrendResponse)
def reddit_trend(product_name : str, days_window : int, subreddits : None ):

    try:

        mentions = provider.fetch_mentions(
            product_name,
            days_window,
            subreddits,
        )

        all_texts = []

        for m in mentions:
            all_texts.append(m["title"])
            all_texts.append(m["body"])
            all_texts.extend(m["comments"])

        sentiment_scores = sentiment_engine.analyze_texts(all_texts)

        signals = SignalAggregator.compute_signals(
            product_name=product_name,
            days_window=days_window,
            mentions=mentions,
            sentiment_scores=sentiment_scores
        )
        
        mention_weight = min(signals.mention_volume/ 10, 1.0)
        urgency_score  = abs(signals.average_sentiment) * mention_weight * signals.confidence_score
        urgency_score  = float(np.clip(urgency_score, 0.0, 1.0))
        
        if signals.average_sentiment > 0.05:
            news_sentiment = "POSITIVE"
        elif signals.average_sentiment < -0.05:
            news_sentiment = "NEGATIVE"
        else:
            news_sentiment = "NEUTRAL"

        news_sentiment = "POSITIVE"
        urgency_score = 0.8

        # return {
        #     "product_name": product_name,
        #     "time_window_days": days_window,
        #     "external_signals": signals,
        #     "urgency_score" : urgency_score,
        #     "news_sentiment" : news_sentiment
        # }
        return {
            "product_name": product_name,
            "time_window_days": days_window,
            "external_signals": signals.dict(),
            "urgency_score" : urgency_score,
            "news_sentiment" : news_sentiment
        }

    except Exception as e:
        logging.exception("Trend analysis failed")
        raise HTTPException(status_code=500, detail=str(e))