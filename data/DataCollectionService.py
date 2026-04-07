import sys
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from RefreshDataService import RefreshDataService
from scrapers.ScraperService import ScraperService

from FightDataResource import FightDataResource
from FightDataService import FightDataService

from cache.FightCache import FightCache
from cache.EventCache import EventCache
from cache.EventInfoCache import EventInfoCache
from cache.CsvUtil import dedupe_csv

FIGHT_CSV = "../resources/initial_data/fights.csv"
FIGHT_CSV_DEDUPE = "../resources/initial_data/fights_dedupe.csv"
EVENT_CSV = "../resources/initial_data/events.csv"
EVENT_INFO_CSV = "../resources/initial_data/events-info.csv"

scheduler: BackgroundScheduler = None

def main():
    print("Starting DataCollectionService...")
    eventCache: EventCache = EventCache(EVENT_CSV)
    print(f"EventCache initialized with the following csv {EVENT_CSV}")
    eventInfoCache: EventInfoCache = EventInfoCache(EVENT_INFO_CSV)
    print(f"EventInfoCache initialized with the following csv {EVENT_INFO_CSV}")
    fightCache: FightCache = FightCache(FIGHT_CSV)
    print(f"FightCache initialized with the following csv {FIGHT_CSV}")
    
    scraperService: ScraperService = ScraperService()
    
    refreshDataService: RefreshDataService = RefreshDataService(fightCache, eventCache, eventInfoCache, scraperService)


    # Run the swagger page
    fightDataService: FightDataService = FightDataService(eventCache, eventInfoCache, fightCache)
    fightDataResource: FightDataResource = FightDataResource(fightDataService, refreshDataService)

    scheduler: BackgroundScheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(fightDataResource.run(), "data", run_date=datetime.now())

    running = True
    while (running):
        try:
            # Start scheduled jobs
            scheduler.start()
        except Exception as e:
            print("Encountered exception in DataCollectionService: {e}")
            break
    _shutdown()


def _shutdown():
    if scheduler != None:
        scheduler.shutdown()
    sys.exit()

if __name__ == "__main__":
    main()