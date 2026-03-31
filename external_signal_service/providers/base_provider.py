from abc import ABC, abstractmethod
from typing import List, Dict


class BaseSocialProvider(ABC):

    @abstractmethod
    def fetch_mentions(
        self,
        product_name: str,
        days_window: int,
        subreddits: List[str]
    ) -> List[Dict]:
        pass