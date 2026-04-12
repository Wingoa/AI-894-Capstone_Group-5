import csv
from typing import Dict
from fight.OutcomePredictor import OutcomePredictor
from style.StylePredictionService import StylePredictionService
from client.DataApiClient import DataApiClient

class OutcomePredictionService:

    def __init__(self, outcome_predictor: OutcomePredictor, style_service: StylePredictionService, data_api_client: DataApiClient):
        self.outcome_predictor = outcome_predictor
        self.style_service = style_service
        self.data_api_client = data_api_client

    def predictFightFromLatest(self, fighter_a_id: str, fighter_b_id: str) -> dict:
        # 1. Get an up to date FighterVector exists
        fighterVectorA = self._getFighterVector(fighter_a_id)
        fighterVectorB = self._getFighterVector(fighter_b_id)

        # 2. Make the prediction
        rawPrediction = self.outcome_predictor.predict(fighterVectorA, fighterVectorB)
        predictionA = rawPrediction[0][0]
        predictionB = 1 - predictionA

        prediction = {
            "fighter_a": fighterVectorA["fighter"],
            "fighter_a_id": fighterVectorA["fighter_id"],
            "fighter_a_prob": predictionA,
            "fighter_a_n_fights_norm": fighterVectorA["n_fights_norm"],
            "fighter_b": fighterVectorB["fighter"],
            "fighter_b_id": fighterVectorB["fighter_id"],
            "fighter_b_prob": predictionB,
            "fighter_b_n_fights_norm": fighterVectorB["n_fights_norm"],
        }

        return prediction
    
    def _getFighterVector(self, fighter_id: str):
        data = self.data_api_client.getFighterVector(fighter_id)
        # TODO Process the data if needed
        print(f"Latest fight vector for {fighter_id}: {data}")
        outcome_vector = self.style_service.createOutcomeVectorForPrediction(data)
        print(f"Latest OutcomeVector: {outcome_vector}")
        return outcome_vector

