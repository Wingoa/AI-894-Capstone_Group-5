import csv
from typing import Dict
from data_model.FighterStyle import FighterStyle
from style.StylePredictor import StylePredictor

class StylePredictionService:

    def __init__(self, style_predictor: StylePredictor, fight_style_csv_path: str):
        self.style_predictor = style_predictor
        self.fight_style_csv_path = fight_style_csv_path
    
    def getFighterStyle(self, fighter_id: str) -> FighterStyle:
        # 1. Check if an up to date FightStyle exists
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
    

