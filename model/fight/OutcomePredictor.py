from fight.OutcomeNet import OutcomeNet
from fight.OutcomeVectorCombiner import combine_features
from fight.OutcomeModelTrainer32 import OutcomeNet32
from typing import List

import torch
import joblib
import numpy as np


class OutcomePredictor:

    MODEL_WEIGHT_PATH = "./fight/outcome_artifacts_32/outcome_model.pt"
    SCALER_PATH = "./fight/outcome_artifacts_32/scaler.pkl"
    MAP_LOCATION = "cuda" if torch.cuda.is_available() else "cpu"
    
    def __init__(self):
        self._model = self._recreate_model()
        self._scaler = self._load_scaler()
        print("Successfully reloaded StyleNet model")

    def _recreate_model(self):
        model = OutcomeNet32()
        model.load_state_dict(torch.load(self.MODEL_WEIGHT_PATH, map_location=self.MAP_LOCATION))
        model.eval()
        return model
    
    def _load_scaler(self):
        return joblib.load(self.SCALER_PATH)
    
    def predict(self, fighter_a_features: dict, fighter_b_features: dict):
        # Combine fighter features
        combined_features = combine_features(fighter_a_features, fighter_b_features)
        print(f"Combined features: {combined_features}")
        return self._predict(combined_features)
    
    def _predict(self, features: List):
        X_raw = np.array(features).reshape(1, -1)
        X_scaled = self._scaler.transform(X_raw)

        with torch.no_grad():
            logits = self._model(torch.tensor(X_scaled, dtype=torch.float32))
            probs = torch.sigmoid(logits)

        print("Logits: ", logits.numpy().tolist())
        print("Probabilities: ", probs.numpy().tolist())
        return probs.numpy().tolist()