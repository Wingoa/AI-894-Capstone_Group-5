from fastapi import FastAPI, HTTPException, Query
import uvicorn
from typing import List
from data_model.EventInfo import EventInfo
from data_model.FighterComposition import FighterComposition
from data_model.Fighter import Fighter
from data_model.FighterStyle import FighterStyle
from FrontEndService import FrontEndService


class FrontEndResource:

    def __init__(self, front_end_service: FrontEndService):
        self.front_end_service = front_end_service
        self.app = FastAPI(title="FrontEnd API")
        self._register_endpoints()

    def run(self):
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=8001,
            reload=False,
            workers=1
        )
        print(f"Starting FightDataResource on 0.0.0.0:8001")

    def _register_endpoints(self):

        @self.app.get("/nextFights")
        def getNextFights() -> List[EventInfo]:
            return self.front_end_service.getNextFights()

        @self.app.get("/lastFights")
        def getLastFights() -> List[EventInfo]:
            return self.front_end_service.getLastFights()

        @self.app.get("/fighter/all")
        def getAllFighters() -> List[Fighter]:
            return self.front_end_service.getAllFighters()

        @self.app.get("/fighter/{fighter_id}")
        def getFighter(fighter_id: str) -> Fighter:
            return self.front_end_service.getFighter(fighter_id)
        
        @self.app.get("/fighter/style/{fighter_id}")
        def getFighterStyle(fighter_id: str) -> FighterStyle:
            return self.front_end_service.getFighterStyle(fighter_id)