"""
This class serves to clean fight vectors from fight_vectors_dated to be exactly what the OutcomeModel needs

#    fighterA = {
#     "wrestling": 0.35,
#     "grappling": 0.25,
#     "muay_thai": 0.20,
#     "boxing": 0.20,
#     "pace": 4.1,
#     "td_success": 0.42,
#     "ctrl_share": 0.33,
#     "n_fights_norm": 0.8
# }
#
#       A. Get fight vector by date
#       B. Get wrestling, grappling, muay thai, boxing from StyleNet
#       C. Calculate Pace
#           1. sig strike att per min + td att per min
#       E. Calculate ctrl share
#           1. ctrl time per min

"""

import csv
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List
from style.StylePredictor import StylePredictor
from datetime import datetime, timedelta

FIGHT_VECTOR_CSV = "../resources/fighter_vectors/fight_vectors_dated.csv"

OUTCOME_FIGHT_VECTOR_CSV = "../resources/fighter_vectors/outcome_fighter_vectors_all.csv"

FIGHT_CSV = "../resources/initial_data/fights_dedupe.csv"
EVENT_CSV = "../resources/initial_data/events.csv"
EVENT_INFO_CSV = "../resources/initial_data/events-info.csv"

style_predictor = StylePredictor()

feature_cols = [
    "sig_str_per_min",
    "td_att_per_min",
    "td_success_per_min",
    "ctrl_sec_per_min",
    "kd_per_min",
    "distance_str_per_min",
    "clinch_str_per_min",
    "ground_str_per_min",
    "sub_att_per_min",
    "distance_strike_ratio",
    "clinch_strike_ratio",
    "ground_strike_ratio",
    "head_target_ratio",
    "body_target_ratio",
    "leg_target_ratio",
]

event_data = None
event_info_data = None
def loadData():
    # Populate module-level variables and be tolerant of occasional malformed lines in CSVs
    global event_data, event_info_data
    event_data = pd.read_csv(EVENT_CSV, on_bad_lines='skip', engine='python')
    event_data["event_date"] = pd.to_datetime(event_data["event_date"])
    event_info_data = pd.read_csv(EVENT_INFO_CSV, on_bad_lines='skip', engine='python')

def addDayToDate(date_str: str):
    # Convert string → datetime
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

    # Add one day
    new_date = date_obj + timedelta(days=1)

    # Convert back to string
    return new_date.strftime("%Y-%m-%d")

def getEventIdByDate(date: str):
    date_parsed = pd.to_datetime(date)
    matches = event_data.loc[event_data["event_date"] == date_parsed, "event_id"]
    if matches.empty:
        raise ValueError(f"No event found for date {date}")
    return matches.iloc[0]

def getFightId(fighter: str, date: str):
    event_id = getEventIdByDate(date)
    matches = event_info_data.loc[
        (event_info_data["event_id"] == event_id) &
        (
            (event_info_data["winner_name"] == fighter) |
            (event_info_data["loser_name"] == fighter)
        ),
        "fight_id"
    ]
    if matches.empty:
        raise ValueError(f"No fight_id found for fighter {fighter} on event {event_id} ({date})")
    return matches.iloc[0]

def calculatePace(sig_strike_per_min: float, td_att_per_min: float):
    return sig_strike_per_min + td_att_per_min

def normalizeNumberOfFights(fights: int):
    return min(int(fights), 10) / 10

def getStyleVector(fighter_vector: dict):
    # Gather features for style predictor
    df = pd.DataFrame([fighter_vector])
    features = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=np.float32).tolist()

    # Calculate style vector
    return style_predictor.predict(features[0])[0]

def dedupe_csv(input_path: str, output_path: str) -> None:
    seen = set()

    with open(input_path, newline="", encoding="utf-8") as infile, \
         open(output_path, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        header = next(reader)
        writer.writerow(header)

        for row in reader:
            row_tuple = tuple(row)
            if row_tuple not in seen:
                seen.add(row_tuple)
                writer.writerow(row)


def generateOutcomeVectorTrainingData():
    loadData()
    counter = 1
    with open(FIGHT_VECTOR_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)   # rows as dictionaries
        for row in reader:
            fighter = row["fighter"]
            fighter_id = row["fighter_id"]
            date = addDayToDate(row["event_date"])
            try:
                # Calculate style vector
                style = getStyleVector(row)
                print(style)

                outcome_vector = {}
                outcome_vector["fighter"] = fighter
                outcome_vector["fighter_id"] = fighter_id
                outcome_vector["fight_id"] = getFightId(fighter, date)
                outcome_vector["event_date"] = date
                outcome_vector["muay_thai"] = style[0]
                outcome_vector["boxing"] = style[1]
                outcome_vector["wrestling"] = style[2]
                outcome_vector["grappling"] = style[3]
                outcome_vector["pace"] = calculatePace(float(row["sig_str_per_min"]), float(row["td_att_per_min"]))
                outcome_vector["td_success"] = row["td_success_per_min"]
                outcome_vector["ctrl_share"] = row["ctrl_sec_per_min"]
                outcome_vector["n_fights_norm"] = normalizeNumberOfFights(row["total_fights"])
                outcome_vector["won"] = 1 if row["win"] == "True" else 0

                pd.DataFrame([outcome_vector]).to_csv("test.csv", mode="a", index=False, header=False)
                print(f"{counter}. Saved DF for {fighter} on {date}: {outcome_vector}")
            except Exception as e:
                print(f"Encountered exception when calculating outcome vector for {fighter} on {date}: {e}")
            counter = counter + 1


    dedupe_csv("test.csv", "outcome_vectors.csv")

if __name__ == "__main__":
    generateOutcomeVectorTrainingData()