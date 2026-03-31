from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List

class SentimentEngine:

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze_texts(self, texts: List[str]) -> List[float]:
        scores = []

        for text in texts:
            score = self.analyzer.polarity_scores(text)["compound"]
            scores.append(score)

        return scores