import datetime
from typing import List, Dict, Any
import yfinance as yf
from ingest.providers.base import BaseMarketDataProvider


class YFinanceProvider(BaseMarketDataProvider):
    """Yahoo Finance market data provider for NSE and BSE equities."""

    def _format_symbol(self, symbol: str, exchange: str = "NSE") -> str:
        s = symbol.strip().upper()
        if s.endswith(".NS") or s.endswith(".BO"):
            return s
        if exchange.upper() == "BSE":
            return f"{s}.BO"
        return f"{s}.NS"

    def fetch_daily_ohlcv(
        self,
        symbol: str,
        start_date: datetime.date,
        end_date: datetime.date,
        exchange: str = "NSE",
    ) -> List[Dict[str, Any]]:
        yf_symbol = self._format_symbol(symbol, exchange)
        ticker = yf.Ticker(yf_symbol)
        
        # yfinance end date is exclusive, so add 1 day
        end_plus_one = end_date + datetime.timedelta(days=1)
        df = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_plus_one.strftime("%Y-%m-%d"),
            auto_adjust=False,
            raise_errors=False,
        )

        if df.empty:
            return []

        records = []
        for index, row in df.iterrows():
            obs_date = index.date() if hasattr(index, "date") else index
            records.append({
                "date": obs_date,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
                "adj_close": float(row.get("Adj Close", row["Close"])),
            })
        return records

    def fetch_corporate_actions(
        self,
        symbol: str,
        start_date: datetime.date,
        end_date: datetime.date,
        exchange: str = "NSE",
    ) -> List[Dict[str, Any]]:
        yf_symbol = self._format_symbol(symbol, exchange)
        ticker = yf.Ticker(yf_symbol)
        actions = []

        try:
            splits = ticker.splits
            if splits is not None and not splits.empty:
                for idx, ratio in splits.items():
                    ex_date = idx.date() if hasattr(idx, "date") else idx
                    if start_date <= ex_date <= end_date and float(ratio) > 0:
                        actions.append({
                            "ex_date": ex_date,
                            "action_type": "SPLIT",
                            "ratio": float(ratio),
                            "amount": None,
                        })
        except Exception:
            pass

        return actions
