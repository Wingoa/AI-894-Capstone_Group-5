import pandas as pd
import os

DATA_DIR = "../resources/clean_data/"
OUTPUT_DIR = "../resources/fighter_vectors/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define the feature columns we want to calculate for each fighter profile
FEATURE_COLS = [
    'sig_str_per_min', 'td_att_per_min', 'td_success_per_min', 'ctrl_sec_per_min',
    'kd_per_min', 'distance_str_per_min', 'clinch_str_per_min', 'ground_str_per_min',
    'sub_att_per_min', 'distance_strike_ratio', 'clinch_strike_ratio', 'ground_strike_ratio',
    'head_target_ratio', 'body_target_ratio', 'leg_target_ratio'
]

def create_fighter_profiles(training_data: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    profiles = []
    
    # Process each fight
    for fight_id in training_data['fight_id'].unique():

        fight_rows = training_data[training_data['fight_id'] == fight_id]

        if len(fight_rows) < 2:
            continue
        
        # Get max control time to estimate fight duration
        max_ctrl = fight_rows['ctrl_seconds'].fillna(0).max()
        duration = max(max_ctrl / 60, 5.0)
        
        # Calculate per-minute stats
        for _, row in fight_rows.iterrows():

            profile = {
                'fighter': row['fighter'],
                'fighter_id': row['fighter_id'],
                'fight_id': row['fight_id'],
                'event_date': pd.to_datetime(row['event_date']),
                'weight_class': row['weight_class'],
                'outcome': row['outcome'],
            }
            
            profile['sig_str_per_min'] = row['sig_str_landed'] / duration if pd.notna(row['sig_str_landed']) else 0
            profile['td_att_per_min'] = row['td_attempted'] / duration if pd.notna(row['td_attempted']) else 0
            profile['td_success_per_min'] = row['td_landed'] / duration if pd.notna(row['td_landed']) else 0
            profile['ctrl_sec_per_min'] = row['ctrl_seconds'] / duration if pd.notna(row['ctrl_seconds']) else 0
            profile['kd_per_min'] = row['kd'] / duration if pd.notna(row['kd']) else 0
            profile['distance_str_per_min'] = row['distance_landed'] / duration if pd.notna(row['distance_landed']) else 0
            profile['clinch_str_per_min'] = row['clinch_landed'] / duration if pd.notna(row['clinch_landed']) else 0
            profile['ground_str_per_min'] = row['ground_landed'] / duration if pd.notna(row['ground_landed']) else 0
            profile['sub_att_per_min'] = row['sub_att'] / duration if pd.notna(row['sub_att']) else 0
            
            sig_landed = row['sig_str_landed'] if pd.notna(row['sig_str_landed']) and row['sig_str_landed'] > 0 else 0
           
            if sig_landed > 0:
                profile['distance_strike_ratio'] = row['distance_landed'] / sig_landed if pd.notna(row['distance_landed']) else 0
                profile['clinch_strike_ratio'] = row['clinch_landed'] / sig_landed if pd.notna(row['clinch_landed']) else 0
                profile['ground_strike_ratio'] = row['ground_landed'] / sig_landed if pd.notna(row['ground_landed']) else 0
                profile['head_target_ratio'] = row['head_landed'] / sig_landed if pd.notna(row['head_landed']) else 0
                profile['body_target_ratio'] = row['body_landed'] / sig_landed if pd.notna(row['body_landed']) else 0
                profile['leg_target_ratio'] = row['leg_landed'] / sig_landed if pd.notna(row['leg_landed']) else 0
            else:
                profile['distance_strike_ratio'] = 0
                profile['clinch_strike_ratio'] = 0
                profile['ground_strike_ratio'] = 0
                profile['head_target_ratio'] = 0
                profile['body_target_ratio'] = 0
                profile['leg_target_ratio'] = 0
            
            profiles.append(profile)
    
    fight_level_df = pd.DataFrame(profiles).sort_values(['fighter_id', 'event_date'])
    
    aggregated = []

    # Each fighter gets a profile based on their last 10 fights
    for fighter_id in fight_level_df['fighter_id'].unique():
        fighter_fights = fight_level_df[fight_level_df['fighter_id'] == fighter_id]
        last_fight = fighter_fights.iloc[-1]
        last_n_fights = fighter_fights.iloc[-window:]
        
        agg_profile = {
            'fighter': last_fight['fighter'],
            'fighter_id': last_fight['fighter_id'],
            'event_date': last_fight['event_date'],
            'weight_class': last_fight['weight_class'],
        }
        
        # Add outcome statistics
        outcomes = last_n_fights['outcome'].values
        agg_profile['win_rate'] = outcomes.mean()
        agg_profile['total_fights'] = len(outcomes)
        
        # Calculate current streak
        streak = 0
        if len(outcomes) > 0:
            most_recent = outcomes[-1]
            for outcome in reversed(outcomes):
                if outcome == most_recent:
                    streak += 1
                else:
                    break
            if most_recent == 0:
                streak = -streak

        agg_profile['current_streak'] = streak
        
        for col in FEATURE_COLS:
            agg_profile[col] = last_n_fights[col].mean()
        
        aggregated.append(agg_profile)
    
    return pd.DataFrame(aggregated).sort_values('fighter')

def main():

    print("=" * 14)
    print("FIGHTER PROFILE BUILDER")
    print("=" * 14)
    
    print("\nLoading training data...")
    training_data = pd.read_csv(os.path.join(DATA_DIR, "training_data.csv"))
    print(f"\t{len(training_data)} fight records")
    
    print("\nCreating fighter profiles (10-fight rolling average)")
    all_profiles = create_fighter_profiles(training_data, window=10)
    print(f"\t{len(all_profiles)} unique fighters")
    
    print("\nSplitting train/test")
    cutoff = pd.to_datetime("2025-01-01") # To simulate testing training on past data 
    train = all_profiles[all_profiles['event_date'] < cutoff].reset_index(drop=True)
    test = all_profiles[all_profiles['event_date'] >= cutoff].reset_index(drop=True)
    
    print(f"\tTrain: {len(train)} fighters")
    print(f"\tTest:  {len(test)} fighters")
    
    print("\nSaving outputs...")
    outputs = {
        'fighter_vectors_train.csv': train,
        'fighter_vectors_test.csv': test,
        'fighter_vectors_all.csv': all_profiles,
    }
    
    for filename, df in outputs.items():
        path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(path, index=False)
        print(f"\t{filename} ({len(df)} rows × {len(df.columns)} cols)")
    
    print("\n" + "=" * 14)
    print("COMPLETE!")

if __name__ == "__main__":
    main()
