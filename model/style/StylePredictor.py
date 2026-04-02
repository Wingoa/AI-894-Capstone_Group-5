from style.StyleNet import StyleNet
from typing import List
from pathlib import Path

import torch
import joblib
import numpy as np


class StylePredictor:

    MAP_LOCATION = "cuda" if torch.cuda.is_available() else "cpu"
    
    def __init__(self):
        metadata_dir = Path(__file__).resolve().parent / "metadata"
        self._model_path = str(metadata_dir / "style_model.pt")
        self._scaler_path = str(metadata_dir / "scaler.pkl")
        self._model = self._recreate_model()
        self._scaler = self._load_scaler()
        print("Successfully reloaded StyleNet model")

    def _recreate_model(self):
        model = StyleNet(d_in=15)
        model.load_state_dict(torch.load(self._model_path, map_location=self.MAP_LOCATION))
        model.eval()
        return model
    
    def _load_scaler(self):
        return joblib.load(self._scaler_path)
    
    def predict(self, features: List):
        X_raw = np.array(features).reshape(1, -1)
        X_scaled = self._scaler.transform(X_raw)

        with torch.no_grad():
            comp = self._model(torch.tensor(X_scaled, dtype=torch.float32))
        return comp.numpy().tolist()
