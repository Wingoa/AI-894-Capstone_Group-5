from fastapi import FastAPI, HTTPException, Query
from data_model.FighterStyle import FighterStyle
import uvicorn

from style.StylePredictionService import StylePredictionService

class PredictionResource:

    def __init__(self, styleService: StylePredictionService):
        self.app = FastAPI(title="PredictionService API")
        self.styleService = styleService
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
        