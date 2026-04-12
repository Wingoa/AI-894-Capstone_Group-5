from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
from apscheduler.schedulers.background import BackgroundScheduler
from PredictionResource import PredictionResource
from style.StylePredictionService import StylePredictionService
from style.StylePredictor import StylePredictor
from fight.OutcomePredictionService import OutcomePredictionService
from fight.OutcomePredictor import OutcomePredictor
from client.DataApiClient import DataApiClient
from datetime import datetime

import sys

DATA_URL = os.getenv("DATA_URL", os.getenv("DATA_API_URL", "http://localhost:8000"))
scheduler: BackgroundScheduler = None
fight_style_csv_path: str = "../resources/fighter_vectors/fighter_style_predictions.csv" 

def main():
    
    scheduler: BackgroundScheduler = BackgroundScheduler(timezone="America/New_York")
    
    dataApiClient: DataApiClient = DataApiClient(DATA_URL)

    stylePredictor: StylePredictor = StylePredictor()
    styleService: StylePredictionService = StylePredictionService(stylePredictor, dataApiClient, fight_style_csv_path)
    print("StyleService successfully instantiated")

    outcomePredictor: OutcomePredictor = OutcomePredictor()
    outcomeService: OutcomePredictionService = OutcomePredictionService(outcomePredictor, styleService, dataApiClient)
    print("OutcomeService successfully instantiated")

    predictionResource: PredictionResource = PredictionResource(styleService, outcomeService)
    scheduler.add_job(predictionResource.run(), "data", run_date=datetime.now())

    running = True
    while (running):
        try:
            # Start scheduled jobs
            scheduler.start()
        except Exception as e:
            print("Encountered exception in PredictionService: {e}")
            break
    _shutdown()


def _shutdown():
    if scheduler != None:
        scheduler.shutdown()
    sys.exit()

if __name__ == "__main__":
    print("Starting FightExecutionService")
    main()
