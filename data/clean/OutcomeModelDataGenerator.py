

#  1. Find metadata
#  2. Loop through all fights and collect the necessary fight vector for each 
#        fighter of the following format:
#
#    fighterA = {
#     "wrestling": 0.35,
#     "grappling": 0.25,
#     "muay_thai": 0.20,
#     "boxing": 0.20,
#     "pace": 4.1,
#     "sig_accuracy": 0.48,
#     "td_success": 0.42,
#     "ctrl_share": 0.33,
#     "age": 29,
#     "reach": 72,
#     "n_fights_norm": 0.8,
#     "days_since_last_log": np.log1p(120)
# }
#
#       A. Get fight vector by date
#       B. Get wrestling, grappling, muay thai, boxing from StyleNet
#       C. Calculate Pace
#           1. sig strike att per min + td att per min
#       D. Calculate accuracy
#           1. sig strike percentage
#       E. Calculate ctrl share
#           1. ctrl time per min

import csv
import pandas as pd
from fighter_vectors import latest_vectors
from datetime import datetime, timedelta

FIGHT_CSV = "../../resources/initial_data/fights.csv"
EVENT_CSV = "../../resources/initial_data/events.csv"
EVENT_INFO_CSV = "../../resources/initial_data/events-info.csv"

TRAINING_CSV = "../../resources/clean_data/training_data.csv"

def getEventInfo(fight_id: str):
    with open(EVENT_INFO_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["fight_id"] == fight_id:
                return row

def getEvent(event_id: str):
    with open(EVENT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["event_id"] == event_id:
                return row
            
def subtractDay(date_str: str):
    # Convert string to datetime
    date_obj = datetime.strptime(date_str, "%B %d, %Y")

    # Subtract one day
    new_date = date_obj - timedelta(days=1)

    # Convert back to string if needed
    return new_date.strftime("%B %d, %Y")

def isDateOld(date_str: str):
    date_obj = datetime.strptime(date_str, "%B %d, %Y")
    return date_obj.year < 2015


df = pd.read_csv(EVENT_INFO_CSV)

unique_values = df["method"].unique()

print(f"Unique fight outcomes: {unique_values}")


counter = 0
with open(FIGHT_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)   # rows as dictionaries
    for row in reader:
        counter = counter + 1
        try:
            fight_id = row["fight_id"]
            fighter_id = row["fighter_id"]
            fighter = row["fighter"]
            event_info = getEventInfo(fight_id)
            event = getEvent(event_info["event_id"])
            date = event["event_date"]
            if (isDateOld(date)):
                print(f"Date {date} is too far in the past, not processing for fighter {fighter}")
                continue
            print(f"{counter}. Getting fight vector for {fighter} on {date}")
            method = event_info["method"]
            if method == "CNC":
                print(f"Fight was no contest, refusing to further process")
                continue
                
            vector = latest_vectors(None, subtractDay(date), training_data_path=TRAINING_CSV, fighter_id=fighter_id)
            if vector.empty:
                print("Fighter had no prior experience, refusing to further process")
                continue

            winner_name = event_info["winner_name"]
            vector["win"] = winner_name == fighter

            vector.to_csv("test.csv", mode="a", index=False, header=False)

        except Exception as e:
            print(f"Encountered exception: {e}")
