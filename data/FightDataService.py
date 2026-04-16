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
        df = self.getAllEvents()
        # Parse the string dates
        df["event_date_parsed"] = pd.to_datetime(df["event_date"], format="%B %d, %Y")
        # Current date
        today = pd.Timestamp(datetime.now().date())
        # Keep only future events
        future_events = df[df["event_date_parsed"] >= today]
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
        print(f"Latest odds from Kalshi: {latest_lines}")
        for fight in event_info:
            fight["fighter_a"] = fight["winner_name"]
            del fight["winner_name"]
            fight["fighter_a_id"] = self.fightCache.get_fighter_id(fight["fighter_a"])
            fight["fighter_a_odds"] = self._getOdds(fight["fighter_a"], latest_lines)

            fight["fighter_b"] = fight["loser_name"]
            del fight["loser_name"]
            fight["fighter_b_id"] = self.fightCache.get_fighter_id(fight["fighter_b"])
            fight["fighter_b_odds"] = self._getOdds(fight["fighter_b"], latest_lines)

            # Clean up if odds were not offered to one fighter
            if fight["fighter_a_odds"] != -1 and fight["fighter_b_odds"] == -1:
                fight["fighter_b_odds"] = 1 - fight["fighter_a_odds"]
            elif fight["fighter_b_odds"] != -1 and fight["fighter_a_odds"] == -1:
                fight["fighter_a_odds"] = 1 - fight["fighter_b_odds"]
        
        return {
            "event": event,
            "fights": event_info
        }
    
    def _getOdds(self, fighter_name: str, df: pd.DataFrame):
        try:
            odds = df[df["fighter"] == fighter_name]["yes_money"]
            return odds.iloc[0] if not odds.empty else self._getOddsFromLastName(fighter_name, df)
        except IndexError:
            # Probably a name mismatch from Kalshi to UFC stats, search for just last name
            return self._getOddsFromLastName(fighter_name, df)
            

    def _getOddsFromLastName(self, fighter_name: str, df: pd.DataFrame):
        last_name = fighter_name.split(" ")[-1]
        print(f"Could not find odds from fighter {fighter_name}, attempting to match last name {last_name}")
        odds = df[df["fighter"].str.contains(last_name)]["yes_money"]
        print(f"last name: {last_name}, odds: {odds}")
        return odds.iloc[0] if not odds.empty else -1

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
    
    def getLastFights(self) -> list:
        # Convert all entries to a DF
        df = self.getAllEvents()
        # Parse the string dates
        df["event_date_parsed"] = pd.to_datetime(df["event_date"], format="%B %d, %Y")
        # Current date
        today = pd.Timestamp(datetime.now().date())
        # Keep only past events
        past_events = df[df["event_date_parsed"] <= today]
        if past_events.empty:
            return {}
        
        # Get the latest upcoming event
        next_event = past_events.sort_values("event_date_parsed", ascending=False).iloc[0]
        # Return full row as dict
        event = next_event.drop(labels=["event_date_parsed"]).to_dict()
        
        print(f"Latest Event: {event}")
        return scrapeEventInfo(event["event_id"])
    
    def getAllEvents(self) -> pd.DataFrame:
        return pd.DataFrame([
            asdict(event) if is_dataclass(event) else event
            for event in self.eventCache.all()
        ])

    def getFighterMetadata(self, fighter_id: str):
        # Flatten the list of lists into a list of dictionaries
        df = pd.DataFrame([
            asdict(f) if is_dataclass(f) else f
            for sublist in self.fightCache.all() 
            for f in sublist
        ])
        relevant_fights = df.loc[df["fighter_id"] == fighter_id]
        name = None
        fight_ids = []
        fights = []
        if len(relevant_fights) > 0:
            name = relevant_fights.iloc[0]["fighter"]
            fight_ids = relevant_fights["fight_id"].tolist()
            fights = relevant_fights.to_dict(orient="records")

        return {
            "name": name,
            "fighter_id": fighter_id,
            "fight_ids": fight_ids,
            "fights": fights
        }
        
    # For the fighter comparison page, we need a list of all fighters with their IDs and fight IDs to populate the dropdowns    
    def getAllFighters(self) -> list:
        df = pd.DataFrame([
            asdict(f) if is_dataclass(f) else f
            for sublist in self.fightCache.all()
            for f in sublist
        ])
        if df.empty:
            return []
        # One row per unique fighter_id, keeping name and aggregating fight_ids
        grouped = (
            df.groupby("fighter_id")
            .agg(
                name=("fighter", "first"),
                fight_ids=("fight_id", list),
            )
            .reset_index()
        )
        return [
            {
                "name": row["name"],
                "fighter_id": row["fighter_id"],
                "fight_ids": row["fight_ids"],
            }
            for _, row in grouped.iterrows()
        ]