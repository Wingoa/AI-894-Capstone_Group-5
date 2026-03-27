import csv
import pandas as pd
import numpy as np
from typing import Dict
from data_model.FighterStyle import FighterStyle
from style.StylePredictor import StylePredictor
from style.FightVectorCleaner import feature_cols, calculatePace, normalizeNumberOfFights

class StylePredictionService:

    def __init__(self, style_predictor: StylePredictor, fight_style_csv_path: str):
        self.style_predictor = style_predictor
        self.fight_style_csv_path = fight_style_csv_path
    
    def getFighterStyle(self, fighter_id: str) -> FighterStyle:
        # 1. Check if an up to date FightStyle exists
        # TODO Change to api call
        fightVector = self._getFightStyleVectorFromCsv(fighter_id)

        # 2. If not recalculate (TODO)
        if fightVector != None:
            # 1. Get relevant fight data
            # 2. Use the StylePredictor
            pass

        # 3. Package the dict as the FightStyle object
        if fightVector != None:
            return FighterStyle(fightVector["fighter_id"], fightVector["fighter"], fightVector["MuayThai"], fightVector["Boxing"], fightVector["Wrestling"], fightVector["Grappling"])
        return None
    

    def _getFightStyleVectorFromCsv(self, fighter_id: str) -> Dict:
        with open(self.fight_style_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["fighter_id"] == fighter_id:
                    return row
        return None
    
    def getStyleVector(self, fighter_vector: dict):
        # Gather features for style predictor
        df = pd.DataFrame([fighter_vector])
        features = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=np.float32).tolist()

        # Calculate style vector
        return self.style_predictor.predict(features[0])[0]

    def createOutcomeVectorForPrediction(self, fighter_vector: dict):
        style = self.getStyleVector(fighter_vector)
        outcome_vector = {}
        outcome_vector["fighter"] = fighter_vector["fighter"]
        outcome_vector["fighter_id"] = fighter_vector["fighter_id"]
        outcome_vector["muay_thai"] = style[0]
        outcome_vector["boxing"] = style[1]
        outcome_vector["wrestling"] = style[2]
        outcome_vector["grappling"] = style[3]
        outcome_vector["pace"] = calculatePace(float(fighter_vector["sig_str_per_min"]), float(fighter_vector["td_att_per_min"]))
        outcome_vector["td_success"] = fighter_vector["td_success_per_min"]
        outcome_vector["ctrl_share"] = fighter_vector["ctrl_sec_per_min"]
        outcome_vector["n_fights_norm"] = normalizeNumberOfFights(fighter_vector["total_fights"])
        return outcome_vector
    

