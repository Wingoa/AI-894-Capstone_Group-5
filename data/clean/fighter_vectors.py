import pandas as pd
import os
import numpy as np

DATA_DIR = "../resources/clean_data/"
OUTPUT_DIR = "../resources/fighter_vectors/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define the feature columns 
FEATURE_COLS = [
    'sig_str_per_min', 'td_att_per_min', 'td_success_per_min', 'ctrl_sec_per_min',
    'kd_per_min', 'distance_str_per_min', 'clinch_str_per_min', 'ground_str_per_min',
    'sub_att_per_min', 'distance_strike_ratio', 'clinch_strike_ratio', 'ground_strike_ratio',
    'head_target_ratio', 'body_target_ratio', 'leg_target_ratio'
]

def create_fighter_profiles(training_data: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    profiles = []

    # Process each fight into per-fight numeric stats
    for fight_id in training_data['fight_id'].unique():

        fight_rows = training_data[training_data['fight_id'] == fight_id]

        if len(fight_rows) < 2:
            continue

        # estimate fight duration from max control seconds (fallback to 5 minutes)
        max_ctrl = fight_rows['ctrl_seconds'].fillna(0).max()
        duration = max(max_ctrl / 60, 5.0)

        for _, row in fight_rows.iterrows():
            profile = {
                'fighter': row['fighter'],
                'fighter_id': row['fighter_id'],
                'fight_id': row['fight_id'],
                'event_date': pd.to_datetime(row['event_date']),
                'weight_class': row.get('weight_class', None),
                'outcome': row.get('outcome', None),
            }

            profile['sig_str_per_min'] = row.get('sig_str_landed', 0) / duration if pd.notna(row.get('sig_str_landed', 0)) else 0
            profile['td_att_per_min'] = row.get('td_attempted', 0) / duration if pd.notna(row.get('td_attempted', 0)) else 0
            profile['td_success_per_min'] = row.get('td_landed', 0) / duration if pd.notna(row.get('td_landed', 0)) else 0
            profile['ctrl_sec_per_min'] = row.get('ctrl_seconds', 0) / duration if pd.notna(row.get('ctrl_seconds', 0)) else 0
            profile['kd_per_min'] = row.get('kd', 0) / duration if pd.notna(row.get('kd', 0)) else 0
            profile['distance_str_per_min'] = row.get('distance_landed', 0) / duration if pd.notna(row.get('distance_landed', 0)) else 0
            profile['clinch_str_per_min'] = row.get('clinch_landed', 0) / duration if pd.notna(row.get('clinch_landed', 0)) else 0
            profile['ground_str_per_min'] = row.get('ground_landed', 0) / duration if pd.notna(row.get('ground_landed', 0)) else 0
            profile['sub_att_per_min'] = row.get('sub_att', 0) / duration if pd.notna(row.get('sub_att', 0)) else 0

            sig_landed = row.get('sig_str_landed', 0) if pd.notna(row.get('sig_str_landed', 0)) and row.get('sig_str_landed', 0) > 0 else 0

            if sig_landed > 0:
                profile['distance_strike_ratio'] = row.get('distance_landed', 0) / sig_landed if pd.notna(row.get('distance_landed', 0)) else 0
                profile['clinch_strike_ratio'] = row.get('clinch_landed', 0) / sig_landed if pd.notna(row.get('clinch_landed', 0)) else 0
                profile['ground_strike_ratio'] = row.get('ground_landed', 0) / sig_landed if pd.notna(row.get('ground_landed', 0)) else 0
                profile['head_target_ratio'] = row.get('head_landed', 0) / sig_landed if pd.notna(row.get('head_landed', 0)) else 0
                profile['body_target_ratio'] = row.get('body_landed', 0) / sig_landed if pd.notna(row.get('body_landed', 0)) else 0
                profile['leg_target_ratio'] = row.get('leg_landed', 0) / sig_landed if pd.notna(row.get('leg_landed', 0)) else 0
            else:
                profile['distance_strike_ratio'] = 0
                profile['clinch_strike_ratio'] = 0
                profile['ground_strike_ratio'] = 0
                profile['head_target_ratio'] = 0
                profile['body_target_ratio'] = 0
                profile['leg_target_ratio'] = 0

            profiles.append(profile)

    fight_level_df = pd.DataFrame(profiles).sort_values(['fighter_id', 'event_date']).reset_index(drop=True)

    per_fight_profiles = []

    # For each fighter, compute SMA over prior N fights for every fight they had
    for fighter_id in fight_level_df['fighter_id'].unique():
        fighter_fights = fight_level_df[fight_level_df['fighter_id'] == fighter_id].sort_values('event_date').reset_index(drop=True)

        for idx in range(len(fighter_fights)):
            current = fighter_fights.loc[idx]
            # use only prior fights (exclude the current fight)
            start = max(0, idx - window)
            prior = fighter_fights.iloc[start:idx]

            if prior.shape[0] == 0:
                # no prior data; skip or include with defaults (here we skip)
                continue

            agg = {
                'fighter': current['fighter'],
                'fighter_id': current['fighter_id'],
                'fight_id': current['fight_id'],
                'event_date': current['event_date'],
                'weight_class': current['weight_class'],
                'outcome': current.get('outcome', None),
            }

            outcomes = prior['outcome'].values
            agg['win_rate'] = outcomes.mean()
            agg['total_fights'] = len(outcomes)

            # current streak computed from prior fights
            streak = 0
            if len(outcomes) > 0:
                most_recent = outcomes[-1]
                for o in reversed(outcomes):
                    if o == most_recent:
                        streak += 1
                    else:
                        break
                if most_recent == 0:
                    streak = -streak

            agg['current_streak'] = streak

            for col in FEATURE_COLS:
                agg[col] = prior[col].mean()

            per_fight_profiles.append(agg)

    return pd.DataFrame(per_fight_profiles).sort_values(['fighter', 'event_date']).reset_index(drop=True)

def main():
    print("=" * 14)
    print("FIGHTER PROFILE BUILDER (LATEST PER FIGHTER)")
    print("=" * 14)

    print("\nLoading training data...")
    training_data = pd.read_csv(os.path.join(DATA_DIR, "training_data.csv"))
    training_data['event_date'] = pd.to_datetime(training_data['event_date'])
    print(f"\t{len(training_data)} fight records")

    # compute latest vectors as of the last available date in the data
    cutoff = training_data['event_date'].max()
    print(f"\nComputing latest vectors with end_date = {cutoff.date()}")
    latest = latest_vectors(start_date=None, end_date=cutoff, training_data_path=training_data, window=10, include_no_history=False)

    out_path = os.path.join(OUTPUT_DIR, 'fighter_vectors_all.csv')
    latest = latest.sort_values('fighter')
    latest.to_csv(out_path, index=False)
    print(f"\nWrote latest vectors: {out_path} ({len(latest)} rows × {len(latest.columns)} cols)")

    print("\n" + "=" * 14)
    print("COMPLETE!")

def latest_vectors(start_date=None, end_date=None, training_data_path: str = os.path.join(DATA_DIR, "training_data.csv"), window: int = 10, include_no_history: bool = False, fill_value=None, fighter_id: str=None) -> pd.DataFrame: 
    # - If `start_date` is None, uses full history before `end_date`.
    # - If `end_date` is None, uses all history up to latest available.
    # - `include_no_history` includes fighters with no prior fights (filled with `fill_value`).
    
    if isinstance(training_data_path, str):
        td = pd.read_csv(training_data_path)
    else:
        td = training_data_path.copy()

    td['event_date'] = pd.to_datetime(td['event_date'])
    end = pd.to_datetime(end_date) if end_date is not None else None
    start = pd.to_datetime(start_date) if start_date is not None else None

    # If a single fighter is requested, filter early to reduce work
    if fighter_id is not None:
        td = td[td['fighter_id'] == fighter_id]

    # Keep only fights that have two rows (two fighters)
    fight_counts = td.groupby('fight_id').size()
    valid_fights = fight_counts[fight_counts >= 2].index
    td = td[td['fight_id'].isin(valid_fights)].copy()

    if td.empty:
        return pd.DataFrame([])

    # compute duration (minutes) per fight in a vectorized way
    max_ctrl = td.groupby('fight_id')['ctrl_seconds'].max().fillna(0)
    durations = (max_ctrl / 60.0).clip(lower=5.0)
    td['duration_min'] = td['fight_id'].map(durations)

    # per-minute features
    td['sig_str_per_min'] = td['sig_str_landed'].fillna(0) / td['duration_min']
    td['td_att_per_min'] = td['td_attempted'].fillna(0) / td['duration_min']
    td['td_success_per_min'] = td['td_landed'].fillna(0) / td['duration_min']
    td['ctrl_sec_per_min'] = td['ctrl_seconds'].fillna(0) / td['duration_min']
    td['kd_per_min'] = td['kd'].fillna(0) / td['duration_min']
    td['distance_str_per_min'] = td['distance_landed'].fillna(0) / td['duration_min']
    td['clinch_str_per_min'] = td['clinch_landed'].fillna(0) / td['duration_min']
    td['ground_str_per_min'] = td['ground_landed'].fillna(0) / td['duration_min']
    td['sub_att_per_min'] = td['sub_att'].fillna(0) / td['duration_min']

    # strike-target ratios (guard against zero sig landed)
    sig_landed = td['sig_str_landed'].fillna(0)
    mask = sig_landed > 0
    td['distance_strike_ratio'] = 0.0
    td['clinch_strike_ratio'] = 0.0
    td['ground_strike_ratio'] = 0.0
    td['head_target_ratio'] = 0.0
    td['body_target_ratio'] = 0.0
    td['leg_target_ratio'] = 0.0

    td.loc[mask, 'distance_strike_ratio'] = td.loc[mask, 'distance_landed'].fillna(0) / sig_landed[mask]
    td.loc[mask, 'clinch_strike_ratio'] = td.loc[mask, 'clinch_landed'].fillna(0) / sig_landed[mask]
    td.loc[mask, 'ground_strike_ratio'] = td.loc[mask, 'ground_landed'].fillna(0) / sig_landed[mask]
    td.loc[mask, 'head_target_ratio'] = td.loc[mask, 'head_landed'].fillna(0) / sig_landed[mask]
    td.loc[mask, 'body_target_ratio'] = td.loc[mask, 'body_landed'].fillna(0) / sig_landed[mask]
    td.loc[mask, 'leg_target_ratio'] = td.loc[mask, 'leg_landed'].fillna(0) / sig_landed[mask]

    # Build fight-level dataframe with only the columns we need
    fight_level_df = td[['fighter', 'fighter_id', 'fight_id', 'event_date', 'weight_class', 'outcome'] + FEATURE_COLS].copy()

    # Apply global date window filter (vectorized)
    prior_df = fight_level_df
    if end is not None:
        prior_df = prior_df[prior_df['event_date'] < end]
    if start is not None:
        prior_df = prior_df[prior_df['event_date'] >= start]

    fighters_all = fight_level_df['fighter_id'].unique()
    fighters_with_history = prior_df['fighter_id'].unique()

    results = []

    # Aggregate for fighters that have history in the window
    for fighter, group in prior_df.groupby('fighter_id'):
        group = group.sort_values('event_date')
        most_recent_row = group.iloc[-1]
        outcomes = group['outcome'].values
        agg = {
            'fighter': most_recent_row['fighter'],
            'fighter_id': fighter,
            'event_date': end,
            'weight_class': most_recent_row.get('weight_class', None),
        }
        agg['win_rate'] = outcomes.mean()
        agg['total_fights'] = len(outcomes)
        # streak
        streak = 0
        if len(outcomes) > 0:
            most_recent = outcomes[-1]
            for o in reversed(outcomes):
                if o == most_recent:
                    streak += 1
                else:
                    break
            if most_recent == 0:
                streak = -streak
        agg['current_streak'] = streak

        # feature means
        means = group[FEATURE_COLS].mean()
        for col in FEATURE_COLS:
            agg[col] = means.get(col, fill_value)

        results.append(agg)

    # Optionally append fighters with no history in the window
    if include_no_history:
        missing = set(fighters_all) - set(fighters_with_history)
        for fid in missing:
            results.append({
                'fighter_id': fid,
                'fighter': None,
                'event_date': end,
                'weight_class': None,
                'win_rate': fill_value,
                'total_fights': 0,
                'current_streak': 0,
                **{col: fill_value for col in FEATURE_COLS}
            })

    return pd.DataFrame(results).reset_index(drop=True)


if __name__ == "__main__":
    main()