import csv
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
MODEL_DIR = REPO_ROOT / "model"
DATA_MODEL_SRC_DIR = REPO_ROOT / "data_model" / "src"

for path in (MODEL_DIR, DATA_MODEL_SRC_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from style.StylePredictionService import StylePredictionService


class StylePredictionServiceTest(unittest.TestCase):

    def _write_csv(self, fieldnames, rows):
        temp = tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8", delete=False)
        with temp:
            writer = csv.DictWriter(temp, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return temp.name

    def test_getFightVectorByDate_returns_latest_vector_on_or_before_date(self):
        style_csv = self._write_csv(
            ["fighter_id", "fighter", "MuayThai", "Boxing", "Wrestling", "Grappling"],
            [],
        )

        vector_csv = self._write_csv(
            ["fighter_id", "fighter", "event_date", "sig_str_per_min"],
            [
                {"fighter_id": "009c4420727149ea", "fighter": "AJ Dobson", "event_date": "2023-01-01", "sig_str_per_min": "2.0"},
                {"fighter_id": "009c4420727149ea", "fighter": "AJ Dobson", "event_date": "2024-06-15", "sig_str_per_min": "3.0"},
                {"fighter_id": "009c4420727149ea", "fighter": "AJ Dobson", "event_date": "2025-01-10", "sig_str_per_min": "4.0"},
                {"fighter_id": "5537efc6e496dd84", "fighter": "Aaron Pico", "event_date": "2024-01-01", "sig_str_per_min": "5.0"},
            ],
        )

        service = StylePredictionService(
            style_predictor=None,
            fight_style_csv_path=style_csv,
            fighter_vector_csv_path=vector_csv,
        )

        result = service.getFightVectorByDate("009c4420727149ea", "2024-12-31")
        print("DEBUG result:", result)

        self.assertIsNotNone(result)
        self.assertEqual("009c4420727149ea", result["fighter_id"])
        self.assertEqual("AJ Dobson", result["fighter"])
        self.assertEqual("2024-06-15", result["event_date"])

    def test_getFightVectorByDate_returns_none_when_no_prior_fight_exists(self):
        style_csv = self._write_csv(
            ["fighter_id", "fighter", "MuayThai", "Boxing", "Wrestling", "Grappling"],
            [],
        )

        vector_csv = self._write_csv(
            ["fighter_id", "fighter", "event_date", "sig_str_per_min"],
            [
                {"fighter_id": "009c4420727149ea", "fighter": "AJ Dobson", "event_date": "2024-06-15", "sig_str_per_min": "3.0"},
            ],
        )

        service = StylePredictionService(
            style_predictor=None,
            fight_style_csv_path=style_csv,
            fighter_vector_csv_path=vector_csv,
        )

        result = service.getFightVectorByDate("009c4420727149ea", "2024-01-01")
        self.assertIsNone(result)

    def test_getFightVectorByDate_returns_none_for_invalid_date_input(self):
        style_csv = self._write_csv(
            ["fighter_id", "fighter", "MuayThai", "Boxing", "Wrestling", "Grappling"],
            [],
        )

        vector_csv = self._write_csv(
            ["fighter_id", "fighter", "event_date", "sig_str_per_min"],
            [
                {"fighter_id": "009c4420727149ea", "fighter": "AJ Dobson", "event_date": "2024-06-15", "sig_str_per_min": "3.0"},
            ],
        )

        service = StylePredictionService(
            style_predictor=None,
            fight_style_csv_path=style_csv,
            fighter_vector_csv_path=vector_csv,
        )

        result = service.getFightVectorByDate("009c4420727149ea", "not-a-date")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
