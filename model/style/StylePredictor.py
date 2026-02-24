from style.StyleNet import StyleNet
from typing import List

import torch
import joblib
import numpy as np


class StylePredictor:

    MODEL_WEIGHT_PATH = "./style/metadata/style_model.pt"
    SCALER_PATH = "./style/metadata/scaler.pkl"
    MAP_LOCATION = "cuda" if torch.cuda.is_available() else "cpu"
    
    def __init__(self):
        self._model = self._recreate_model()
        self._scaler = self._load_scaler()
        print("Successfully reloaded StyleNet model")

    def _recreate_model(self):
        model = StyleNet(d_in=15)
        model.load_state_dict(torch.load(self.MODEL_WEIGHT_PATH, map_location=self.MAP_LOCATION))
        model.eval()
        return model
    
    def _load_scaler(self):
        return joblib.load(self.SCALER_PATH)
    
    def predict(self, features: List):
        X_raw = np.array(features).reshape(1, -1)
        X_scaled = self._scaler.transform(X_raw)

        with torch.no_grad():
            comp = self._model(torch.tensor(X_scaled, dtype=torch.float32))
        return comp.numpy().toList()