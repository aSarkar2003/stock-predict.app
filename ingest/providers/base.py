from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import datetime


class BaseMarketDataProvider(ABC):
    """Abstract market data provider interface."""

    @abstractmethod
    def fetch_daily_ohlcv(
        self,
        symbol: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> List[Dict[str, Any]]:
        """
        Fetches daily historical OHLCV data.
        Returns a list of dictionaries with keys:
        - date (datetime.date)
        - open (float)
        - high (float)
        - low (float)
        - close (float)
        - volume (int)
        - adj_close (float, optional)
        """
        pass

    @abstractmethod
    def fetch_corporate_actions(
        self,
        symbol: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> List[Dict[str, Any]]:
        """
        Fetches historical corporate actions (splits, dividends).
        Returns list of dicts with:
        - ex_date (datetime.date)
        - action_type (str: 'SPLIT', 'DIVIDEND', 'BONUS')
        - ratio (float)
        - amount (float)
        """
        pass
