import pandas as pd
from typing import List

NMF_STYLE_FEATURES = [
    'sig_str_landed', 'sig_str_attempted', 'sig_str_accuracy', 'sig_str_per_min',
    'head_landed', 'head_attempted', 'body_landed', 'body_attempted',
    'leg_landed', 'leg_attempted', 'distance_landed', 'distance_attempted',
    'clinch_landed', 'clinch_attempted', 'td_landed', 'td_attempted',
    'td_success', 'td_per_min', 'sub_att', 'ctrl_seconds', 'ctrl_pct',
    'rev', 'ground_landed', 'ground_attempted', 'kd',
]

PREDICTION_MODEL_FEATURES = [
    'sig_str_per_min', 'sig_str_accuracy', 'head_landed', 'body_landed',
    'leg_landed', 'distance_landed', 'clinch_landed', 'td_per_min',
    'td_success', 'sub_att', 'ctrl_pct', 'rev', 'ground_landed', 'kd',
]

PREDICTION_TARGET = 'outcome'

def get_training_features(df: pd.DataFrame, for_style_modeling: bool = False) -> pd.DataFrame:
    features = NMF_STYLE_FEATURES if for_style_modeling else PREDICTION_MODEL_FEATURES
    available_features = [f for f in features if f in df.columns]
    feature_data = df[available_features].copy()
    feature_data = feature_data.dropna()
    return feature_data

def get_training_data_with_features(df: pd.DataFrame, for_style_modeling: bool = False) -> tuple:
    features = NMF_STYLE_FEATURES if for_style_modeling else PREDICTION_MODEL_FEATURES
    available_features = [f for f in features if f in df.columns]
    df_clean = df[available_features + ([PREDICTION_TARGET] if not for_style_modeling else [])].dropna()
    
    if for_style_modeling:
        return df_clean[available_features], None
    else:
        X = df_clean[available_features]
        y = df_clean[PREDICTION_TARGET]
        return X, y

def summary_statistics(df: pd.DataFrame) -> pd.DataFrame:
    print("\nFeature Summary:")
    print("=" * 80)
    stats = df.describe()
    print(stats)
    print(f"\nNon-null counts (out of {len(df)}):")
    print(df.count())
    return stats

if __name__ == "__main__":
    import os
    
    output_dir = "../resources/train_data/"
    training_file = os.path.join(output_dir, "training_data.csv")
    
    if os.path.exists(training_file):
        df = pd.read_csv(training_file)
        
        print("Prediction Model Features:")
        X, y = get_training_data_with_features(df, for_style_modeling=False)
        print(f"X shape: {X.shape}, y shape: {y.shape}")
        summary_statistics(X)
        
        print("\n" + "=" * 80)
        print("Style Modeling Features:")
        X_style, _ = get_training_data_with_features(df, for_style_modeling=True)
        print(f"X_style shape: {X_style.shape}")
        summary_statistics(X_style)
    else:
        print(f"Training file not found: {training_file}")
        print("Run process_data.py first")
