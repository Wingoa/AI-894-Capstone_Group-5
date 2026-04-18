from fastapi import FastAPI, HTTPException, Query
import uvicorn
from clean.fighter_vectors import latest_vectors
from FightDataService import FightDataService
from RefreshDataService import RefreshDataService

from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import os

class FightDataResource:

    def __init__(self, fightDataService: FightDataService, refreshDataService: RefreshDataService, enable_background_refresh: bool = True):
        self.fightDataService = fightDataService
        self.refreshDataService = refreshDataService

        if enable_background_refresh:
            # Manage scheduler lifecycle when background refresh is enabled.
            @asynccontextmanager
            async def lifespan(app: FastAPI):
                scheduler = BackgroundScheduler()
                # Control whether to run refresh jobs immediately using env var REFRESH_ON_START
                refresh_on_start = os.getenv("REFRESH_ON_START", "false").lower() in ("1", "true", "yes")
                if refresh_on_start:
                    scheduler.add_job(refreshDataService.refreshFightData, 'interval', hours=1, next_run_time=datetime.datetime.now())
                    scheduler.add_job(refreshDataService.reloadIncompleteData, 'interval', hours=24, next_run_time=datetime.datetime.now())
                scheduler.start()
                yield
                scheduler.shutdown()

            self.app = FastAPI(title="UFC Fight Data API", lifespan=lifespan)
        else:
            self.app = FastAPI(title="UFC Fight Data API")
        self._registerEndpoints()


    def run(self):
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=8000,
            reload=False,
            workers=1
        )
        print(f"Starting FightDataResource on 0.0.0.0:8000")

    def _registerEndpoints(self):

        @self.app.get("/")
        def healthCheck():
            return {
                    "status": "ok", 
                    "message": "API is running. Go to http://localhost:8080/docs for the interactive swagger page"
                    } 
        
        @self.app.get("/refresh")
        def refresh_data():
            # Prevent accidental scraping when disabled via env var
            enable_scraping = os.getenv("ENABLE_SCRAPING", "false").lower() in ("1", "true", "yes")
            if not enable_scraping:
                raise HTTPException(status_code=403, detail="Scraping disabled (ENABLE_SCRAPING=false). Refresh disallowed.")
            return self.refreshDataService.refreshFightData()
        
        @self.app.get("/latest")
        def get_latest_fights():
            return self.fightDataService.getLastFights()

        @self.app.get("/latest/{fighter_id}")
        def get_latest_fight_vector(fighter_id: str):
            data = latest_vectors(fighter_id=fighter_id, include_no_history=True)
            return data.iloc[0].to_dict()
        
        @self.app.get("/fighter")
        def get_all_fighters():
            return self.fightDataService.getAllFighters()
        
        @self.app.get("/fighter/{fighter_id}")
        def get_fighter_metadata(fighter_id: str):
            return self.fightDataService.getFighterMetadata(fighter_id)

        @self.app.get("/fights/{name}")
        def get_fights_by_fighter(name: str):
            return self.fightDataService.get_fights_by_fighter(name)
        
        @self.app.get("/event/next")
        def get_next_event():
            return self.fightDataService.get_next_event()
