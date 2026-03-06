from apscheduler.schedulers.background import BackgroundScheduler
from FrontEndService import FrontEndService
from FrontEndResource import FrontEndResource
from datetime import datetime

import sys

scheduler: BackgroundScheduler = None

MODEL_URL = "http://localhost:8002" # TODO Change when hosted within a DOCKER container

def main():
    
    scheduler: BackgroundScheduler = BackgroundScheduler(timezone="America/New_York")
    
    frontEndService: FrontEndService = FrontEndService(MODEL_URL) 
    frontEndResource: FrontEndResource = FrontEndResource(frontEndService)
    scheduler.add_job(frontEndResource.run(), "data", run_date=datetime.now())

    running = True
    while (running):
        try:
            # Start scheduled jobs
            scheduler.start()
        except Exception as e:
            print("Encountered exception in FightExecutionService: {e}")
            break
    _shutdown()


def _shutdown():
    if scheduler != None:
        scheduler.shutdown()
    sys.exit()

if __name__ == "__main__":
    print("Starting FightExecutionService")
    main()
