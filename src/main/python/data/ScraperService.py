from typing import Dict, List

import data.cache.FightCache as FightCache
import data.cache.EventCache as EventCache
import data.cache.EventInfoCache as EventInfoCache

import data.scrapers.FightDataScraper as FightDataScraper
import data.scrapers.EventScraper as EventScraper
import data.scrapers.EventInfoScraper as EventInfoScraper

class ScraperService:

    FIGHT_CSV = "../../resources/fights.csv"
    EVENT_CSV = "../../resources/events.csv"
    EVENT_INFO_CSV = "../../resources/events-info.csv"

    def __init__(self):
        self.fight_cache = FightCache(self.FIGHT_CSV)
        self.event_cache = EventCache(self.EVENT_CSV)
        self.event_info_cache = EventInfoCache(self.EVENT_INFO_CSV)

        self.event_scraper = EventScraper

    def loadFights(self):
        return self.fight_cache.all()
    
    def loadEvents(self):
        return self.event_cache.all()
    
    def loadEventInfo(self):
        return self.event_info_cache.all()

    def refreshFightData(self):
        # Find new events.
        #   1. Add new events to events.csv database
        #   2. Scrape event and fight info
        events = EventScraper.scrapeEvents()
        new_event_ids = self.findNewEvents(self.getEventIds(events))

        print(f"Found {len(new_event_ids)} new event ids when refreshing data")
        for event_id in new_event_ids:
            new_event = self.event_cache.getEvent(event_id, events)
            # Add new event to the events.csv database
            self.event_cache.save(new_event)

            # Scrape for the corresponding Event Info rows that need to be added
            new_event_info = EventInfoScraper.scrapeEventInfo(event_id)
            # Save all new event info objects
            self.event_info_cache.saveAll(new_event_info)

            # For each new event info object, scrape for new fight info
            for event_info in new_event_info:
                fight_id = event_info["fight_id"]
                new_fights = FightDataScraper.scrapeFight(fight_id)
                # Save all fights
                self.fight_cache.saveAll(new_fights)


    def getEventIds(self, events: List[Dict]) -> List[str]:
        return [d["event_id"] for d in events if "event_id" in d]

    def findNewEvents(self, current_event_ids: List[str]) -> List[str]:
        existing_events = self.event_cache.all()
        existing_event_ids = set(self.getEventIds(existing_events))
        return [x for x in current_event_ids if x not in existing_event_ids]

