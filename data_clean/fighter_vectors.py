import pandas as pd
import os
from typing import Optional, Tuple

DATA_DIR = "../resources/clean_data/"
OUTPUT_DIR = "../resources/fighter_vectors/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

NUMERIC_COLS = [
    'sig_str_per_min', 'td_att_per_min', 'td_success_per_min', 'ctrl_sec_per_min',
    'kd_per_min', 'distance_str_per_min', 'clinch_str_per_min', 'ground_str_per_min',
    'sub_att_per_min', 'distance_strike_ratio', 'clinch_strike_ratio', 'ground_strike_ratio',
    'head_target_ratio', 'body_target_ratio', 'leg_target_ratio'
]

def categorize_outcome_type(method: str) -> Optional[str]:
    if pd.isna(method) or method == "" or method == "---":
        return None
    
    m = str(method).lower().strip()
    
    if 'submission' in m or 'sub' in m:
        return 'submission'
    if 'ko/tko' in m or 'knockout' in m or 'tko' in m:
        return 'knockout_kick' if 'kick' in m else 'knockout_strike'
    if 'dec' in m or 'decision' in m:
        return 'decision'
    if 'dww' in m or 'dq' in m or 'nc' in m:
        return 'other'
    
    return 'other'

def create_fight_vectors(training_data: pd.DataFrame) -> pd.DataFrame:
    df = training_data.copy()
    required = ['fight_id', 'fighter', 'fighter_id', 'event_date', 'outcome', 'weight_class']
    if not all(col in df.columns for col in required):
        raise ValueError(f"Missing: {required}")
    
    vectors = []
    for fight_id in df['fight_id'].unique():
        fight_rows = df[df['fight_id'] == fight_id].copy()
        if len(fight_rows) < 2:
            continue
        
        max_ctrl = fight_rows['ctrl_seconds'].apply(lambda x: x if pd.notna(x) else 0).max()
        duration = max(max_ctrl / 60, 5.0)
        
        for _, row in fight_rows.iterrows():
            v = {
                'fight_id': row['fight_id'],
                'fighter': row['fighter'],
                'fighter_id': row['fighter_id'],
                'event_date': row['event_date'],
                'outcome': row['outcome'],
                'weight_class': row['weight_class'],
            }
            
            v['sig_str_per_min'] = row['sig_str_landed'] / duration if pd.notna(row['sig_str_landed']) else None
            v['td_att_per_min'] = row['td_attempted'] / duration if pd.notna(row['td_attempted']) else None
            v['td_success_per_min'] = row['td_landed'] / duration if pd.notna(row['td_landed']) else None
            v['ctrl_sec_per_min'] = row['ctrl_seconds'] / duration if pd.notna(row['ctrl_seconds']) else None
            v['kd_per_min'] = row['kd'] / duration if pd.notna(row['kd']) else None
            v['distance_str_per_min'] = row['distance_landed'] / duration if pd.notna(row['distance_landed']) else None
            v['clinch_str_per_min'] = row['clinch_landed'] / duration if pd.notna(row['clinch_landed']) else None
            v['ground_str_per_min'] = row['ground_landed'] / duration if pd.notna(row['ground_landed']) else None
            v['sub_att_per_min'] = row['sub_att'] / duration if pd.notna(row['sub_att']) else None
            
            sig_landed = row['sig_str_landed'] if pd.notna(row['sig_str_landed']) else 0
            if sig_landed > 0:
                v['distance_strike_ratio'] = row['distance_landed'] / sig_landed if pd.notna(row['distance_landed']) else None
                v['clinch_strike_ratio'] = row['clinch_landed'] / sig_landed if pd.notna(row['clinch_landed']) else None
                v['ground_strike_ratio'] = row['ground_landed'] / sig_landed if pd.notna(row['ground_landed']) else None
                v['head_target_ratio'] = row['head_landed'] / sig_landed if pd.notna(row['head_landed']) else None
                v['body_target_ratio'] = row['body_landed'] / sig_landed if pd.notna(row['body_landed']) else None
                v['leg_target_ratio'] = row['leg_landed'] / sig_landed if pd.notna(row['leg_landed']) else None
            else:
                v['distance_strike_ratio'] = None
                v['clinch_strike_ratio'] = None
                v['ground_strike_ratio'] = None
                v['head_target_ratio'] = None
                v['body_target_ratio'] = None
                v['leg_target_ratio'] = None
            
            vectors.append(v)
    
    result = pd.DataFrame(vectors)
    result['event_date'] = pd.to_datetime(result['event_date'])
    return result.sort_values(['fighter', 'event_date']).reset_index(drop=True)

def add_outcome_types(training_data: pd.DataFrame, events_info: pd.DataFrame) -> pd.DataFrame:
    df = training_data.copy()
    outcome_map = {
        row['fight_id']: categorize_outcome_type(row['method'])
        for _, row in events_info.iterrows()
        if pd.notna(row['fight_id']) and row['fight_id'] != ""
    }
    df['outcome_type'] = df['fight_id'].map(outcome_map).fillna('unknown')
    return df

def aggregate_fighter_vectors_sma(fight_vectors: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    rows = []
    for fighter_id in fight_vectors['fighter_id'].unique():
        fighter_data = fight_vectors[fight_vectors['fighter_id'] == fighter_id].copy()
        fighter_data = fighter_data.sort_values('event_date').reset_index(drop=True)
        
        for idx in range(len(fighter_data)):
            current = fighter_data.iloc[idx]
            start = max(0, idx - window + 1)
            window_data = fighter_data.iloc[start:idx + 1]
            
            vector = {
                'fighter': current['fighter'],
                'fighter_id': current['fighter_id'],
                'fight_id': current['fight_id'],
                'event_date': current['event_date'],
                'weight_class': current['weight_class'],
                'outcome': current['outcome'],
            }
            
            for col in NUMERIC_COLS:
                vector[f'{col}_sma'] = window_data[col].mean()
            
            rows.append(vector)
    
    result = pd.DataFrame(rows)
    return result.sort_values(['fighter', 'event_date']).reset_index(drop=True)

def aggregate_fighter_vectors_ema(fight_vectors: pd.DataFrame, span: int = 10) -> pd.DataFrame:
    rows = []
    for fighter_id in fight_vectors['fighter_id'].unique():
        fighter_data = fight_vectors[fight_vectors['fighter_id'] == fighter_id].copy()
        fighter_data = fighter_data.sort_values('event_date').reset_index(drop=True)
        
        for idx in range(len(fighter_data)):
            current = fighter_data.iloc[idx]
            window_data = fighter_data.iloc[:idx + 1]
            
            vector = {
                'fighter': current['fighter'],
                'fighter_id': current['fighter_id'],
                'fight_id': current['fight_id'],
                'event_date': current['event_date'],
                'weight_class': current['weight_class'],
                'outcome': current['outcome'],
            }
            
            for col in NUMERIC_COLS:
                ema = window_data[col].ewm(span=span, min_periods=2).mean().iloc[-1]
                vector[f'{col}_ema'] = ema
            
            rows.append(vector)
    
    result = pd.DataFrame(rows)
    return result.sort_values(['fighter', 'event_date']).reset_index(drop=True)

def create_train_test_split(df: pd.DataFrame, cutoff: str = "2025-01-01") -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df['event_date'] = pd.to_datetime(df['event_date'])
    cutoff_date = pd.to_datetime(cutoff)
    
    train = df[df['event_date'] < cutoff_date].reset_index(drop=True)
    test = df[df['event_date'] >= cutoff_date].reset_index(drop=True)
    
    return train, test

def save_outputs(fight_vectors, sma_df, ema_df, sma_train, sma_test, ema_train, ema_test):
    outputs = {
        'fight_vectors.csv': fight_vectors,
        'fighter_vectors_sma.csv': sma_df,
        'fighter_vectors_ema.csv': ema_df,
        'fighter_vectors_sma_train.csv': sma_train,
        'fighter_vectors_sma_test.csv': sma_test,
        'fighter_vectors_ema_train.csv': ema_train,
        'fighter_vectors_ema_test.csv': ema_test,
    }
    
    for filename, df in outputs.items():
        path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(path, index=False)
        print(f"  {filename}: {len(df)} rows × {len(df.columns)} cols")

def main():
    print("=" * 14)
    print("FIGHTER VECTOR PREPROCESSING")
    print("=" * 14)
    
    print("\n[1] Loading data...")
    training_data = pd.read_csv(os.path.join(DATA_DIR, "training_data.csv"))
    events_info = pd.read_csv("../resources/initial_data/events-info.csv")
    
    print("[2] Adding outcome types...")
    training_data = add_outcome_types(training_data, events_info)
    print(f"  Types: {training_data['outcome_type'].value_counts().to_dict()}")
    
    print("[3] Creating fight vectors...")
    fight_vectors = create_fight_vectors(training_data)
    print(f"  {len(fight_vectors)} vectors, {fight_vectors['fighter_id'].nunique()} fighters")
    
    print("[4] Aggregating with SMA...")
    sma_df = aggregate_fighter_vectors_sma(fight_vectors, window=10)
    print(f"  {len(sma_df)} rows × {len(sma_df.columns)} cols")
    
    print("[5] Aggregating with EMA...")
    ema_df = aggregate_fighter_vectors_ema(fight_vectors, span=10)
    print(f"  {len(ema_df)} rows × {len(ema_df.columns)} cols")
    
    print("[6] Creating train/test splits...")
    sma_train, sma_test = create_train_test_split(sma_df)
    ema_train, ema_test = create_train_test_split(ema_df)
    print(f"  SMA: {len(sma_train)}|{len(sma_test)}, EMA: {len(ema_train)}|{len(ema_test)}")
    
    print("[7] Saving outputs...")
    save_outputs(fight_vectors, sma_df, ema_df, sma_train, sma_test, ema_train, ema_test)
    
    print("\n" + "=" * 14)
    print("COMPLETE")
    print("=" * 14 + "\n")

if __name__ == "__main__":
    main()
