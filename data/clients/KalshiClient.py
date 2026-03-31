import requests
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

class KalshiClient:

    def __init__(self):
        self.url = "https://api.elections.kalshi.com/trade-api/v2/markets"
        self.params = {
            'status': 'open',
            'series_ticker': "KXUFCFIGHT"
        }
    
    def getLatest(self):
        response = requests.get(self.url, self.params)
        if response.status_code == 200:
            markets = response.json()["markets"]
            print(f"Found {len(markets)} markets for upcoming UFC fights")
            return [self.parse_kalshi_market(m) for m in markets]
        else:
            print(f"Error when gathering latest data from Kalshi: {response.status_code}")
            return []


    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        if value is None or value == "":
            return None
        return float(str(value))


    def _extract_date_from_ticker(self, ticker: str) -> Optional[str]:
        """
        Example:
        KXUFCFIGHT-26APR04EWIEST-EWI
        Extracts:
        26APR04 -> 2026-04-04
        """
        match = re.search(r"-(\d{2}[A-Z]{3}\d{2})", ticker)
        if not match:
            return None

        parsed = datetime.strptime(match.group(1), "%y%b%d").date()
        return parsed.isoformat()


    def parse_kalshi_market(self, market: dict) -> dict:
        ticker = market["ticker"]

        # Best source for names in this payload shape
        fighter = (market.get("yes_sub_title") or "").strip()

        if not fighter:
            raise ValueError(f"Missing fighter in market: {ticker}")

        # Prefer title-based date, fallback to ticker-based date
        fight_date = self._extract_date_from_ticker(ticker)

        if not fight_date:
            raise ValueError(f"Could not extract fight date from market: {ticker}")

        yes_money = self._to_decimal(market.get("yes_ask_dollars"))
        no_money = self._to_decimal(market.get("no_ask_dollars"))

        return {
            'kalshi_ticker': ticker,
            'fighter': fighter,
            'fight_date': fight_date,
            'yes_money': yes_money,
            'no_money': no_money,
            'timestamp': datetime.now().date()
        }


if __name__ == '__main__':
    client = KalshiClient()
    client.getLatest()