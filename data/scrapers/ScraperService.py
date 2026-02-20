from scrapers.EventScraper import scrapeEvents
from scrapers.EventInfoScraper import scrapeEventInfo
from scrapers.FightDataScraper import scrapeFight

from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.FightStatLine import FightStatLine

from typing import List

### A Facade class to hide the implementation of the individual scrapers
class ScraperService:

    # Will scrape for all event metadata
    def scrape_all_events(self) -> List[Event]:
        return scrapeEvents()
    
    # Will scrape for all fight metadata for a specific event id
    def scrape_event_info(self, event_id: str) -> List[EventInfo]:
        return scrapeEventInfo(event_id)
    
    # Will scrape the stats of each fighter from the fight id
    def scrape_fight_info(self, fight_id: str) -> List[FightStatLine]:
        return scrapeFight(fight_id)