from typing import List
from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.FightStatLine import FightStatLine
from data_model.FighterComposition import FighterComposition
from data_model.Fighter import Fighter

class FrontEndService:

    def getNextFights() -> List[EventInfo]:
        # TODO - Query the data service to get the upcoming fights
        return

    def getLastFights() -> List[EventInfo]:
        # TODO - Query the data service to get the last completed fights
        return
    
    def getAllFighters() -> List[Fighter]:
        # TODO - Query the data service to get all Fighters
        return
    
    def getFighter(fighter_id) -> Fighter:
        # TODO - Query the data service for the specific fighter info
        return
    
    def reloadData() -> None:
        # TODO - On a browser refresh, this should be called to check if any
        #     data needs to be reloaded. If so, update the cache's
        return