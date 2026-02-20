from pathlib import Path
import sys
from typing import List
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Allow importing project modules when running from front-end directory; this way, we can reuse data models and services without needing to duplicate code or set up a separate package
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_model.EventInfo import EventInfo
from data_model.Fighter import Fighter
from FrontEndService import FrontEndService

app = FastAPI(title="UFC Fighter Optimizer Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
service = FrontEndService()

@app.get("/", response_class=HTMLResponse)
def homepage(request: Request) -> HTMLResponse:
    fighters = service.getAllFighters()
    # Using Jinja2 templates to render the homepage
    return templates.TemplateResponse("index.html", {"request": request, "fighters": fighters})

@app.get("/nextFights", response_model=List[EventInfo])
def getNextFights() -> List[EventInfo]:
    return service.getNextFights()

@app.get("/lastFights", response_model=List[EventInfo])
def getLastFights() -> List[EventInfo]:
    return service.getLastFights()

@app.get("/fighter/all", response_model=List[Fighter])
def getAllFighters() -> List[Fighter]:
    return service.getAllFighters()

@app.get("/fighter/{fighter_id}", response_model=Fighter)
def getFighter(fighter_id: str):
    fighter = service.getFighter(fighter_id)
    if not fighter:
        raise HTTPException(
            status_code=404,
            detail=f"No fighter found with id '{fighter_id}'"
        )
    return fighter
