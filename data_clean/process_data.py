import pandas as pd
import os
import re
from typing import Tuple, Optional

DATA_DIR = "../resources/initial_data/"
OUTPUT_DIR = "../resources/clean_data/"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_stat_string(stat_str: str) -> Tuple[Optional[float], Optional[float]]:
    if not stat_str or stat_str == "---":
        return None, None
    match = re.match(r"(\d+)\s+of\s+(\d+)", str(stat_str).strip())
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None

def parse_control_time(ctrl_str: str) -> Optional[float]:
    if not ctrl_str or ctrl_str == "---":
        return None
    match = re.match(r"(\d+):(\d+)", str(ctrl_str).strip())
    if match:
        minutes, seconds = int(match.group(1)), int(match.group(2))
        return float(minutes * 60 + seconds)
    return None

def calculate_success_rate(landed: Optional[float], attempted: Optional[float]) -> Optional[float]:
    if landed is None or attempted is None or attempted == 0:
        return None
    return landed / attempted

def clean_fights_data(fights: pd.DataFrame) -> pd.DataFrame:
    df = fights.copy()
    df = df.dropna(subset=['fight_id', 'fighter_id', 'fighter'])
    
    df[['sig_str_landed', 'sig_str_attempted']] = df['sig_str'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['total_str_landed', 'total_str_attempted']] = df['total_str'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['td_landed', 'td_attempted']] = df['td'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['head_landed', 'head_attempted']] = df['head'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['body_landed', 'body_attempted']] = df['body'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['leg_landed', 'leg_attempted']] = df['leg'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['distance_landed', 'distance_attempted']] = df['distance'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['clinch_landed', 'clinch_attempted']] = df['clinch'].apply(lambda x: pd.Series(parse_stat_string(x)))
    df[['ground_landed', 'ground_attempted']] = df['ground'].apply(lambda x: pd.Series(parse_stat_string(x)))
    
    df['ctrl_seconds'] = df['ctrl'].apply(parse_control_time)
    df['kd'] = pd.to_numeric(df['kd'], errors='coerce')
    df['sub_att'] = pd.to_numeric(df['sub_att'], errors='coerce')
    df['rev'] = pd.to_numeric(df['rev'], errors='coerce')
    
    string_cols = ['sig_str', 'sig_str_pct', 'total_str', 'td', 'td_pct', 
                   'head', 'body', 'leg', 'distance', 'clinch', 'ground', 'ctrl']
    df = df.drop(columns=string_cols)
    
    return df

def normalize_fight_features(df: pd.DataFrame) -> pd.DataFrame:
    df_normalized = df.copy()
    
    for fight_id in df_normalized['fight_id'].unique():
        fight_rows = df_normalized[df_normalized['fight_id'] == fight_id]
        max_ctrl = fight_rows['ctrl_seconds'].max()
        if pd.notna(max_ctrl) and max_ctrl > 0:
            fight_duration_min = max(max_ctrl / 60, 5.0)
        else:
            fight_duration_min = 15.0
        
        mask = df_normalized['fight_id'] == fight_id
        df_normalized.loc[mask, 'sig_str_per_min'] = df_normalized.loc[mask, 'sig_str_landed'] / fight_duration_min
        df_normalized.loc[mask, 'td_per_min'] = df_normalized.loc[mask, 'td_landed'] / fight_duration_min
        df_normalized.loc[mask, 'ctrl_pct'] = ((df_normalized.loc[mask, 'ctrl_seconds'] / (fight_duration_min * 60)) * 100).clip(0, 100)
    
    df_normalized['sig_str_accuracy'] = df_normalized.apply(
        lambda row: calculate_success_rate(row['sig_str_landed'], row['sig_str_attempted']), axis=1
    )
    df_normalized['td_success'] = df_normalized.apply(
        lambda row: calculate_success_rate(row['td_landed'], row['td_attempted']), axis=1
    )
    
    return df_normalized

def merge_with_event_info(fights_clean: pd.DataFrame, events_info: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    events_info_full = events_info.merge(events[['event_id', 'event_date']], on='event_id')
    events_info_full['event_date'] = pd.to_datetime(events_info_full['event_date'])
    
    fights_with_outcome = []
    
    for _, row in events_info_full.iterrows():
        fight_id = row['fight_id']
        if pd.isna(fight_id) or fight_id == '':
            continue
        
        winner = row['winner_name']
        loser = row['loser_name']
        event_date = row['event_date']
        weight_class = row['weight_class']
        
        fight_stats = fights_clean[fights_clean['fight_id'] == fight_id]
        
        for _, fighter_row in fight_stats.iterrows():
            fighter_name = fighter_row['fighter']
            outcome = 1 if fighter_name == winner else (0 if fighter_name == loser else None)
            
            if outcome is not None:
                fighter_row_with_outcome = fighter_row.copy()
                fighter_row_with_outcome['outcome'] = outcome
                fighter_row_with_outcome['event_date'] = event_date
                fighter_row_with_outcome['weight_class'] = weight_class
                fights_with_outcome.append(fighter_row_with_outcome)
    
    return pd.DataFrame(fights_with_outcome)

def save_processed_data(df: pd.DataFrame, filename: str):
    output_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")
    return output_path

def main():
    print("Loading raw data...")
    fights = pd.read_csv(os.path.join(DATA_DIR, "fights.csv"))
    events = pd.read_csv(os.path.join(DATA_DIR, "events.csv"))
    events_info = pd.read_csv(os.path.join(DATA_DIR, "events-info.csv"))
    
    print(f"Loaded: {len(fights)} fights, {len(events)} events, {len(events_info)} event-info records")
    
    print("\nCleaning fight data...")
    fights_clean = clean_fights_data(fights)
    
    print("Normalizing features...")
    fights_norm = normalize_fight_features(fights_clean)
    
    print("Merging with event outcomes...")
    training_data = merge_with_event_info(fights_norm, events_info, events)
    
    training_data['event_date'] = pd.to_datetime(training_data['event_date'])
    cutoff_date = pd.to_datetime("2025-01-01")
    train_set = training_data[training_data['event_date'] < cutoff_date]
    test_set = training_data[training_data['event_date'] >= cutoff_date]
    
    print(f"\nTrain: {len(train_set)} | Test: {len(test_set)}")
    
    save_processed_data(fights_clean, "fights_cleaned.csv")
    save_processed_data(fights_norm, "fights_normalized.csv")
    save_processed_data(training_data, "training_data.csv")
    save_processed_data(train_set, "train_set.csv")
    save_processed_data(test_set, "test_set.csv")
    
    print("\nComplete")

if __name__ == "__main__":
    main()
