from apscheduler.schedulers.background import BackgroundScheduler
from PredictionResource import PredictionResource
from style.StylePredictionService import StylePredictionService
from style.StylePredictor import StylePredictor
from datetime import datetime

import sys

scheduler: BackgroundScheduler = None
fight_style_csv_path: str = "../resources/fighter_vectors/fighter_style_predictions.csv" 

def main():
    
    scheduler: BackgroundScheduler = BackgroundScheduler(timezone="America/New_York")
    
    stylePredictor: StylePredictor = StylePredictor()
    styleService: StylePredictionService = StylePredictionService(stylePredictor, fight_style_csv_path)

    predictionResource: PredictionResource = PredictionResource(styleService)
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
