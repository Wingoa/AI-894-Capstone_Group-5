from fastapi import FastAPI, HTTPException, Query
from data_model.FighterStyle import FighterStyle
import uvicorn

from style.StylePredictionService import StylePredictionService
from fight.OutcomePredictionService import OutcomePredictionService

class PredictionResource:

    def __init__(self, styleService: StylePredictionService, predictionService: OutcomePredictionService, app: FastAPI = None):
        # If an existing FastAPI app is provided, register endpoints on it.
        # Otherwise, create a standalone app (backwards compatible).
        if app is None:
            self.app = FastAPI(title="PredictionService API")
            self._created_app = True
        else:
            self.app = app
            self._created_app = False

        self.styleService = styleService
        self.predictionService = predictionService
        self._register_endpoints()

    def run(self):
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=8002,
            reload=False,
            workers=1
        )
        print(f"Starting PredictionResource on 0.0.0.0:8002")

    def _register_endpoints(self):

        @self.app.get("/style/{fighter_id}")
        def getStyle(fighter_id: str) -> FighterStyle:
            return self.styleService.getFighterStyle(fighter_id)
        
        @self.app.get("/outcome")
        def getFightPrediction(fighter_a_id: str, fighter_b_id: str):
            return self.predictionService.predictFightFromLatest(fighter_a_id, fighter_b_id)