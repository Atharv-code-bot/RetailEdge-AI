import praw
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from external_signal_service.config import settings
from .base_provider import BaseSocialProvider

logger = logging.getLogger(__name__)

class RedditProvider(BaseSocialProvider):

    def __init__(self):
        if not all([
            settings.REDDIT_CLIENT_ID,
            settings.REDDIT_CLIENT_SECRET,
            settings.REDDIT_USER_AGENT
        ]):
            raise ValueError("Missing Reddit API credentials")

        self.reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )

    def fetch_mentions(
        self,
        product_name: str,
        days_window: int,
        subreddits: List[str]
    ) -> List[Dict]:

        mentions = []
        cutoff_time = datetime.utcnow() - timedelta(days=days_window)
        product_lower = product_name.lower()

        for sub in subreddits:
            try:
                subreddit = self.reddit.subreddit(sub)

                for submission in subreddit.search(
                    product_name,
                    sort="new",
                    time_filter="month",
                    limit=100
                ):
                    created = datetime.utcfromtimestamp(submission.created_utc)

                    if created < cutoff_time:
                        continue

                    content = f"{submission.title} {submission.selftext}".lower()
                    if product_lower not in content:
                        continue

                    submission.comments.replace_more(limit=0)

                    top_comments = [
                        comment.body
                        for comment in submission.comments[:10]
                        if product_lower in comment.body.lower()
                    ]

                    mentions.append({
                        "thread_id": submission.id,
                        "title": submission.title,
                        "body": submission.selftext,
                        "comments": top_comments,
                        "upvotes": submission.score,
                        "created_utc": submission.created_utc
                    })

                time.sleep(1)  # basic rate limit safety

            except Exception as e:
                logger.error(f"Error fetching from r/{sub}: {str(e)}")

        return mentions