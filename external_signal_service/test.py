from main import reddit_trend
from aggregator import SignalAggregator

external = reddit_trend("Mango", 30, None)

print(external)