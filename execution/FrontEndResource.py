from fastapi import FastAPI, HTTPException, Query
from typing import List
from data_model.EventInfo import EventInfo
from data_model.FighterComposition import FighterComposition
from data_model.Fighter import Fighter
import FrontEndService

app = FastAPI(title="FrontEnd API")


@app.get("/nextFights")
def getNextFights() -> List[EventInfo]:
    return FrontEndService.getNextFights()

@app.get("/lastFights")
def getLastFights() -> List[EventInfo]:
    return FrontEndService.getLastFights()

@app.get("/fighter/all")
def getAllFighters() -> List[Fighter]:
    return FrontEndService.getAllFighters()

@app.get("/fighter/{fighter_id}")
def getFighter(fighter_id: str) -> Fighter:
    return FrontEndService.getFighter()