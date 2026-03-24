from fastapi import FastAPI, HTTPException, Query
import uvicorn
from clean.fighter_vectors import latest_vectors
from FightDataService import FightDataService


class FightDataResource:

    def __init__(self, fightDataService: FightDataService):
        self.app = FastAPI(title="UFC Fight Data API")
        self.fightDataService = fightDataService
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
        
        @self.app.get("/latest/{fighter_id}")
        def get_latest_fight_vector(fighter_id: str):
            data = latest_vectors(fighter_id=fighter_id, include_no_history=True)
            return data.iloc[0].to_dict()

        @self.app.get("/fights/{name}")
        def get_fights_by_fighter(name: str):
            return self.fightDataService.get_fights_by_fighter(name)
        
        @self.app.get("/event/next")
        def get_next_event():
            return self.fightDataService.get_next_event()
