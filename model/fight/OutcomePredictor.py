from fight.OutcomeVectorCombiner import combine_features
from fight.OutcomeModelTrainer32 import OutcomeNet32
from fight.OutcomeModelTrainer32Retrain import OutcomeNet32 as OutcomeNet32Retrain
from typing import List

import torch
import joblib
import numpy as np
from pathlib import Path

FEATURE_ORDER: List[str] = [
    "wrestling",
    "grappling",
    "muay_thai",
    "boxing",
    "pace",
    "td_success",
    "ctrl_share",
    "n_fights_norm",
]


class OutcomePredictor:

    MAP_LOCATION = "cuda" if torch.cuda.is_available() else "cpu"
    
    def __init__(self):
        print(f"Numpy Version {np.__version__}")
        self._model_path, self._scaler_path, self._artifact_tag = self._resolve_artifacts()
        self._model = self._recreate_model()
        self._scaler = self._load_scaler()
        print("Successfully reloaded Outcome model")

    def _resolve_artifacts(self):
        fight_dir = Path(__file__).resolve().parent
        candidates = [
            ("outcome_artifacts_32_2", "32"),
            ("outcome_artifacts_32", "32"),
            ("outcome_artifacts_32_retrain", "32_retrain"),
            ("outcome_artifacts", "32"),
            ("metadata", "32"),
        ]
        for dirname, tag in candidates:
            candidate = fight_dir / dirname
            model_path = candidate / "outcome_model.pt"
            scaler_path = candidate / "scaler.pkl"
            if model_path.exists() and scaler_path.exists():
                return str(model_path), str(scaler_path), tag
        raise FileNotFoundError("No outcome_model.pt/scaler.pkl artifacts found.")

    def _recreate_model(self):
        if self._artifact_tag == "32_retrain":
            model = OutcomeNet32Retrain()
        else:
            model = OutcomeNet32()
        model.load_state_dict(torch.load(self._model_path, map_location=self.MAP_LOCATION))
        model.eval()
        return model
    
    def _load_scaler(self):
        return joblib.load(self._scaler_path)
    
    def predict(self, fighter_a_features: dict, fighter_b_features: dict):
        # Combine fighter features
        combined_features = combine_features(fighter_a_features, fighter_b_features)
        print(f"Combined features: {combined_features}")
        return self._predict(combined_features)
    
    def _predict(self, features: List):
        X_raw = np.array(features).reshape(1, -1)
        X_scaled = self._scaler.transform(X_raw)

        print("Max abs scaled value:", np.abs(X_scaled).max())
        with torch.no_grad():
            logits = self._model(torch.tensor(X_scaled, dtype=torch.float32))
            probs = torch.sigmoid(logits)

        print("Logits: ", logits.numpy().tolist())
        print("Probabilities: ", probs.numpy().tolist())
        return probs.numpy().tolist()
