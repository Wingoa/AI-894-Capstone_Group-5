from typing import List
from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.FightStatLine import FightStatLine
from data_model.FighterComposition import FighterComposition
from data_model.Fighter import Fighter
from data_model.FighterStyle import FighterStyle

import requests

class FrontEndService:

    def __init__(self, model_url: str, data_url: str):
        self.model_url = model_url
        self.data_url = data_url

    def getNextFights(self) -> List[EventInfo]:
        # Query the data service to get the upcoming fights
        resp = requests.get(f"{self.data_url}/event/next", timeout=10)
        resp.raise_for_status()
        return resp.json() 

    def getLastFights(self) -> List[EventInfo]:
        # Query the data service to get the last completed fights
        resp = requests.get(f"{self.data_url}/latest", timeout=10)
        resp.raise_for_status()
        return resp.json()
    
    def getAllFighters(self) -> List[Fighter]:
        # Query the data service to get all Fighters
        resp = requests.get(f"{self.data_url}/fighter", timeout=10)
        resp.raise_for_status()

        # Unsure this will be efficient or useful

        return resp.json()
    
    def getFighter(self, fighter_id) -> Fighter:
        # Query the data service for the specific fighter info
        fighter_metadata_resp = requests.get(f"{self.data_url}/fighter/{fighter_id}")
        fighter_metadata_resp.raise_for_status()
        data = fighter_metadata_resp.json()
        fighter_style = self.getFighterStyle(fighter_id)
        return Fighter(data["name"], fighter_id, self._getFighterComposition(fighter_style), data["fight_ids"])
    
    def _getFighterComposition(self, fighter_style: FighterStyle) -> FighterComposition:
        return FighterComposition(None, fighter_style.boxing, fighter_style.muayThai, fighter_style.wrestling, fighter_style.grappling)

    def getFighterStyle(self, fighter_id) -> FighterStyle:
        resp = requests.get(f"{self.model_url}/style/{fighter_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return FighterStyle(data["fighter_id"], data["fighter"], float(data["muayThai"]), float(data["boxing"]), float(data["wrestling"]), float(data["grappling"]))
    
    def refreshData(self):
        # On a browser refresh, this should be called to check if any
        #     data needs to be reloaded. If so, update the cache's
        resp = requests.get(f"{self.data_url}/refresh", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data
    
    def predictFight(self, fighter_a_id: str, fighter_b_id: str):
        queryParams = {
            "fighter_a_id": fighter_a_id,
            "fighter_b_id": fighter_b_id
        }
        resp = requests.get(f"{self.model_url}/outcome", params=queryParams, timeout=60)
        resp.raise_for_status()
        fight_prediction = resp.json()
        print(f"Fight prediction for {fighter_a_id} v {fighter_b_id}: {fight_prediction}")
        return fight_prediction