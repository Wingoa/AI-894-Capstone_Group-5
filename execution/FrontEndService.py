from typing import List
from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.FightStatLine import FightStatLine
from data_model.FighterComposition import FighterComposition
from data_model.Fighter import Fighter
from data_model.FighterStyle import FighterStyle

import requests

class FrontEndService:

    def __init__(self, model_url: str):
        self.model_url = model_url

    def getNextFights(self) -> List[EventInfo]:
        # TODO - Query the data service to get the upcoming fights
        return

    def getLastFights(self) -> List[EventInfo]:
        # TODO - Query the data service to get the last completed fights
        return
    
    def getAllFighters(self) -> List[Fighter]:
        # TODO - Query the data service to get all Fighters
        return
    
    def getFighter(self, fighter_id) -> Fighter:
        # TODO - Query the data service for the specific fighter info
        return
    
    def getFighterStyle(self, fighter_id) -> FighterStyle:
        resp = requests.get(f"{self.model_url}/style/{fighter_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return FighterStyle(data["fighter_id"], data["fighter"], float(data["muayThai"]), float(data["boxing"]), float(data["wrestling"]), float(data["grappling"]))
    
    def reloadData(self) -> None:
        # TODO - On a browser refresh, this should be called to check if any
        #     data needs to be reloaded. If so, update the cache's
        return