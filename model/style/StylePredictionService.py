import csv
import pandas as pd
import numpy as np
from typing import Dict
from data_model.FighterStyle import FighterStyle
from style.StylePredictor import StylePredictor
from style.FightVectorCleaner import feature_cols, calculatePace, normalizeNumberOfFights
from client.DataApiClient import DataApiClient
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

class StylePredictionService:

    def __init__(self, style_predictor: StylePredictor, data_api_client: DataApiClient, fight_style_csv_path: str):
        self.style_predictor = style_predictor
        self.data_api_client = data_api_client
        self.fight_style_csv_path = fight_style_csv_path
        self._clearStyleCache()
    
    def getFighterStyle(self, fighter_id: str) -> FighterStyle:
        # 1. Check if an up to date FightStyle exists
        fightVector = self._getFightStyleVectorFromCsv(fighter_id)

        data = self.data_api_client.getFighterVector(fighter_id)

        muayThai = None
        boxing = None
        wrestling = None
        grappling = None
        pace = calculatePace(float(data["sig_str_per_min"]), float(data["td_att_per_min"]))

        # 2. If not recalculate
        if self._shouldRecalculateStyle(fightVector):
            print(f"Recalculating fight style vector for {fighter_id}")
            # Use the StylePredictor
            fightVector = self.getStyleVector(data)
            muayThai = fightVector[0]
            boxing = fightVector[1]
            wrestling = fightVector[2]
            grappling = fightVector[3]

            csvData = {
                "fighter_id": fighter_id,
                "fighter": data["fighter"],
                "event_date": date.today().isoformat(),
                "weight_class": data["weight_class"],
                "MuayThai": muayThai,
                "Boxing": boxing,
                "Wrestling": wrestling,
                "Grappling": grappling
            }
            self._saveToCSV(csvData)
        else:
            muayThai = fightVector["MuayThai"]
            boxing = fightVector["Boxing"]
            wrestling = fightVector["Wrestling"]
            grappling = fightVector["Grappling"]

        print(data)
        # 3. Package the dict as the FightStyle object
        return FighterStyle(fighter_id, data["fighter"], muayThai, boxing, wrestling, grappling, pace, data) if fightVector != None else None
    
    def _shouldRecalculateStyle(self, fightVector: dict) -> bool:
        if fightVector == None:
            return True
        date = fightVector["event_date"]
        return self._isStyleOld(date)
    
    def _isStyleOld(self, date: str) -> bool:
        check_date = datetime.strptime(date, "%Y-%m-%d").date()
        # Calculate the date two months ago
        two_months_ago = datetime.now().date() - relativedelta(months=2)

        # Compare
        is_older = check_date < two_months_ago
        return is_older
    
    def _shouldRemove(self, row) -> bool:
        return self._isStyleOld(row["event_date"])
    
    def _clearStyleCache(self):
        # Load the file
        df = pd.read_csv(self.fight_style_csv_path)
        # Keep rows where event_date is older than 2 months
        df = df[~df.apply(self._shouldRemove, axis=1)]
        print(f"Loading {len(df)} fighter styles to the style prediction cache")
        # Save the updated DataFrame back to the CSV
        df.to_csv(self.fight_style_csv_path, index=False)

    def _getFightStyleVectorFromCsv(self, fighter_id: str) -> Dict:
        with open(self.fight_style_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["fighter_id"] == fighter_id:
                    return row
        return None
    
    def _saveToCSV(self, data: dict):
        # Wrap in a list to create a single-row DataFrame
        df = pd.DataFrame([data])
        # Save to CSV
        df.to_csv(self.fight_style_csv_path, index=False)
    
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
    

