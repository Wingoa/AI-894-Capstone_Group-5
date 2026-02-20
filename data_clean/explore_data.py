import pandas as pd
import os

DATA_DIR = "../resources/initial_data/"

def load_data():
    fights = pd.read_csv(os.path.join(DATA_DIR, "fights.csv"))
    events = pd.read_csv(os.path.join(DATA_DIR, "events.csv"))
    events_info = pd.read_csv(os.path.join(DATA_DIR, "events-info.csv"))
    return fights, events, events_info

def explore_fights(fights):
    print("=" * 14)
    print("FIGHTS DATA")
    print("=" * 14)
    print(f"Shape: {fights.shape}")
    print(f"Columns: {fights.columns.tolist()}")
    print(f"Missing values:\n{fights.isnull().sum()}")
    print(f"\nFirst rows:\n{fights.head()}")
    return fights

def explore_events(events):
    print("\n" + "=" * 14)
    print("EVENTS DATA")
    print("=" * 14)
    print(f"Shape: {events.shape}")
    print(f"Missing values:\n{events.isnull().sum()}")
    print(f"Date range: {events['event_date'].min()} to {events['event_date'].max()}")
    return events

def explore_events_info(events_info):
    print("\n" + "=" * 14)
    print("EVENTS-INFO DATA")
    print("=" * 14)
    print(f"Shape: {events_info.shape}")
    print(f"Missing values:\n{events_info.isnull().sum()}")
    print(f"Weight classes: {events_info['weight_class'].unique()[:10]}")
    return events_info

if __name__ == "__main__":

    fights, events, events_info = load_data()

    explore_fights(fights)
    explore_events(events)
    explore_events_info(events_info)

    print("\nComplete!")
