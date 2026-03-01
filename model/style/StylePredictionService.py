import csv
from datetime import date, datetime
from typing import Dict, Optional, TYPE_CHECKING
from data_model.FighterStyle import FighterStyle

if TYPE_CHECKING:
    from style.StylePredictor import StylePredictor

class StylePredictionService:

    def __init__(
        self,
        style_predictor: "StylePredictor",
        fight_style_csv_path: str,
        fighter_vector_csv_path: str = "../resources/fighter_vectors/fighter_vectors_all.csv",
    ):
        self.style_predictor = style_predictor
        self.fight_style_csv_path = fight_style_csv_path
        self.fighter_vector_csv_path = fighter_vector_csv_path
    
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

    def getFightVectorByDate(self, fighter_id: str, as_of_date: str) -> Optional[Dict]:
        target_date = self._parse_date(as_of_date)
        if target_date is None:
            return None

        best_row: Optional[Dict] = None
        best_date: Optional[date] = None

        with open(self.fighter_vector_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("fighter_id") != fighter_id:
                    continue

                event_date = self._parse_date(row.get("event_date", ""))
                if event_date is None or event_date > target_date:
                    continue

                if best_date is None or event_date > best_date:
                    best_date = event_date
                    best_row = row

        return best_row
    

    def _getFightStyleVectorFromCsv(self, fighter_id: str) -> Dict:
        with open(self.fight_style_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["fighter_id"] == fighter_id:
                    return row
        return None

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if value is None:
            return None

        cleaned = value.strip()
        if not cleaned:
            return None

        for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y"):
            try:
                return datetime.strptime(cleaned, date_format).date()
            except ValueError:
                continue
        return None
    

