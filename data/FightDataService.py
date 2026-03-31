import pandas as pd
from dataclasses import asdict, is_dataclass
from datetime import datetime

from fastapi import HTTPException

from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache
from cache.FightCache import FightCache
from scrapers.EventInfoScraper import scrapeEventInfo
from clients.KalshiClient import KalshiClient

class FightDataService:

    def __init__(self, eventCache: EventCache, eventInfoCache: EventInfoCache, fightCache: FightCache):
        self.eventCache = eventCache
        self.eventInfoCache = eventInfoCache
        self.fightCache = fightCache
        self.kalshiClient = KalshiClient()

    def get_next_event(self):
        # Convert all entries to a DF
        df = pd.DataFrame([
            asdict(event) if is_dataclass(event) else event
            for event in self.eventCache.all()
        ])
        # Parse the string dates
        df["event_date_parsed"] = pd.to_datetime(df["event_date"], format="%B %d, %Y")
        # Current date
        today = pd.Timestamp(datetime.now().date())
        # Keep only future events
        future_events = df[df["event_date_parsed"] > today]
        if future_events.empty:
            return {}
        # Get the soonest upcoming event
        next_event = future_events.sort_values("event_date_parsed").iloc[0]
        # Return full row as dict
        event = next_event.drop(labels=["event_date_parsed"]).to_dict()
        
        print(f"Latest Event: {event}")
        event_info = scrapeEventInfo(event["event_id"])
        # Enrich event info with betting info
        latest_lines = pd.DataFrame(self.kalshiClient.getLatest())
        for fight in event_info:
            fight["fighter_a"] = fight["winner_name"]
            del fight["winner_name"]
            fight["fighter_a_odds"] = self._getOdds(fight["fighter_a"], latest_lines)

            fight["fighter_b"] = fight["loser_name"]
            del fight["loser_name"]
            fight["fighter_b_odds"] = self._getOdds(fight["fighter_b"], latest_lines)
        
        return {
            "event": event,
            "fights": event_info
        }
    
    def _getOdds(self, fighter_name: str, df: pd.DataFrame):
        try:
            return df[df["fighter"] == fighter_name]["yes_money"].iloc[0]
        except IndexError:
            # Probably a name mismatch from Kalshi to UFC stats, search for just last name
            last_name = fighter_name.split(" ")[-1]
            odds = df[df["fighter"].str.contains(last_name)]["yes_money"].iloc[0]
            print(f"last name: {last_name}, odds: {odds}")
            return odds

    def get_fights_by_fighter(self, name: str):
        """
        Returns all fights where the fighter name contains the given string.
        Case-insensitive.
        """
        name_lower = name.lower()

        fights = self.fightCache.all()
        matches = []
        for fight in fights:
            for fighter in fight:
                if name_lower in fighter.fighter.lower():
                    matches.append(fighter)


        if len(matches) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No fights found for fighter containing '{name}'"
            )

        return {
                "totalMatches": len(matches),
                "matches": matches
            }