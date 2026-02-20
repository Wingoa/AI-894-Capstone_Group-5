from typing import Dict, List

from scrapers.ScraperService import ScraperService

from cache.FightCache import FightCache
from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache

from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.FightStatLine import FightStatLine

class RefreshDataService:

    def __init__(self, 
                 fight_cache: FightCache, 
                 event_cache: EventCache, 
                 event_info_cache: EventInfoCache, 
                 scraper_service: ScraperService):
        self.fight_cache = fight_cache
        self.event_cache = event_cache
        self.event_info_cache = event_info_cache
        self.scraper_service = scraper_service

    def refreshFightData(self):
        # Find new events.
        #   1. Add new events to events.csv database
        #   2. Scrape event and fight info
        events: List[Event] = self.scraper_service.scrape_all_events()
        new_event_ids = self._findNewEvents(self._getEventIdsFromDict(events))

        print(f"Found {len(new_event_ids)} new event ids when refreshing data: {new_event_ids}")
        for event_id in new_event_ids:
            new_event = self._getEvent(event_id, events)
            # Add new event to the events.csv database
            print(f"Found new event: {new_event}")
            self.event_cache.save(new_event)

            # Scrape for the corresponding Event Info rows that need to be added
            self._scrapeEventInfo(event_id)

    def reloadIncompleteData(self) -> None:
        self._reloadIncompleteEventInfo()
        self._reloadIncompleteFightData()

    def _reloadIncompleteEventInfo(self) -> None:
        allEventIds: List[str] = self._getEventIdsFromEvent(self._loadEvents())
        allEventInfoIDs: List[str] = self._getEventIdsFromEventInfo(self._loadEventInfo())
        incompleteEventInfoIDs: List[str] = [x for x in allEventIds if x not in allEventInfoIDs]
        print(f"Found {len(incompleteEventInfoIDs)} incomplete event info data: {incompleteEventInfoIDs}")
        for event_id in incompleteEventInfoIDs:
            self._scrapeEventInfo(event_id)
    
    def _reloadIncompleteFightData(self) -> None:
        allFightIds: List[str] = self._getFightIdsFromEventInfo(self._loadEventInfo())
        existingFightIds: List[str] = self._getFightIdsFromFightData(self._loadFights())
        incompleteFightIDs: List[str] = [x for x in allFightIds if x not in existingFightIds and x != None]
        print(f"Found {len(incompleteFightIDs)} incomplete fight info data: {incompleteFightIDs}")
        for fight_id in incompleteFightIDs:
            if fight_id != None:
                self._scrapeFightData(fight_id)

    def _scrapeEventInfo(self, event_id: str):
        new_event_info = self.scraper_service.scrape_event_info(event_id)
        print(f"Found new event info: {new_event_info}")
        for event_info in new_event_info:
            if event_info["fight_id"] == '':
                # This is a future event, we will not process it this way
                # TODO process future fights
                fighter1: str = event_info["winner_name"]
                fighter2: str = event_info["loser_name"]
                print(f"Fight {fighter1} vs {fighter2} is in the future, will process separately")
                continue

            # Save all new event info objects
            self.event_info_cache.save(event_info)

            # For each new event info object, scrape for new fight info
            for event_info in new_event_info:
                fight_id = event_info["fight_id"]
                self._scrapeFightData(fight_id)

    def _scrapeFightData(self, fight_id: str) -> None:
        new_fights = self.scraper_service.scrape_fight_info(fight_id)
        # Save all fights
        if not self.fight_cache.hasFight(fight_id):
            self.fight_cache.saveAll(new_fights)

    def _getEventIdsFromDict(self, events: List[Dict]) -> List[str]:
        return [event["event_id"] for event in events if "event_id" in event]

    def _getEventIdsFromEvent(self, events: List[Event]) -> List[str]:
        event_ids: List[str] = []
        for event in events:
            event_ids.append(event.getEventId())
        return event_ids
    
    def _getEventIdsFromEventInfo(self, events: List[List[EventInfo]]) -> List[str]:
        # print(f"{len(eventInfos[0])}")
        event_ids: List[str] = []
        for event in events:
            for eventInfo in event:
                event_ids.append(eventInfo.getEventId())
        return event_ids
    
    def _getFightIdsFromEventInfo(self, events: List[List[EventInfo]]) -> List[str]:
        fight_ids: List[str] = []
        for event in events:
            for eventInfo in event:
                fight_ids.append(eventInfo.getFightId())
        return fight_ids
    
    def _getFightIdsFromFightData(self, fights: List[List[FightStatLine]]) -> List[str]:
        fight_ids: List[str] = []
        for fight in fights:
            for fightData in fight:
                fight_ids.append(fightData.getFightId())
        return fight_ids

    def _findNewEvents(self, current_event_ids: List[str]) -> List[str]:
        existing_events: List[Event] = self.event_cache.all()
        print(f"Existing events in cache: {len(existing_events)}")
        existing_event_ids = self._getEventIdsFromEvent(existing_events)
        return [x for x in current_event_ids if x not in existing_event_ids]
    
    def _getEvent(self, target_id: str, events: List[Event]) -> Event:
        return next((e for e in events if e["event_id"] == target_id),None)

    def _loadFights(self):
        return self.fight_cache.all()
    
    def _loadEvents(self):
        return self.event_cache.all()
    
    def _loadEventInfo(self):
        return self.event_info_cache.all()
