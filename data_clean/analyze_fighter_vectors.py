import pandas as pd
import os

OUTPUT_DIR = "../resources/fighter_vectors/"

def check_file(path: str, name: str):
    df = pd.read_csv(path)
    missing_pct = df.isnull().sum().sum() / df.size * 100
    
    print(f"{name:40} | {len(df):6} rows | {len(df.columns):3} cols | {missing_pct:5.1f}% missing")
    return df

def validate_splits():
    for method in ['sma', 'ema']:
        train = pd.read_csv(os.path.join(OUTPUT_DIR, f'fighter_vectors_{method}_train.csv'))
        test = pd.read_csv(os.path.join(OUTPUT_DIR, f'fighter_vectors_{method}_test.csv'))
        
        train_win = train['outcome'].mean() * 100
        test_win = test['outcome'].mean() * 100
        
        print(f"\n{method.upper()} Split:")
        print(f"  Train: {len(train)} rows ({train_win:.1f}% win rate)")
        print(f"  Test:  {len(test)} rows ({test_win:.1f}% win rate)")

def validate_metrics(df, suffix):
    per_min_cols = [f'sig_str_per_min_{suffix}', f'td_att_per_min_{suffix}', f'kd_per_min_{suffix}']
    ratio_cols = [f'distance_strike_ratio_{suffix}', f'clinch_strike_ratio_{suffix}', f'ground_strike_ratio_{suffix}']
    
    print(f"\n{suffix.upper()} Metric Ranges:")
    for col in per_min_cols:
        if col in df.columns:
            valid = df[col].dropna()
            if (valid < 0).any():
                print(f"  {col}: NEGATIVE VALUES DETECTED")
            else:
                print(f"  {col}: [{valid.min():.2f}, {valid.max():.2f}]")
    
    for col in ratio_cols:
        if col in df.columns:
            valid = df[col].dropna()
            if ((valid < 0) | (valid > 1)).any():
                print(f"  {col}: OUT OF RANGE [0,1]")
            else:
                print(f"  {col}: [{valid.min():.2f}, {valid.max():.2f}]")

def main():
    print("==============")
    print("FIGHTER VECTOR VALIDATION")
    print("==============\n")
    
    if not os.path.exists(OUTPUT_DIR):
        print(f"ERROR: {OUTPUT_DIR} not found")
        return
    
    files = [
        'fighter_vectors_sma_train.csv', 'fighter_vectors_sma_test.csv',
        'fighter_vectors_ema_train.csv', 'fighter_vectors_ema_test.csv',
    ]
    
    missing = [f for f in files if not os.path.exists(os.path.join(OUTPUT_DIR, f))]
    if missing:
        print(f"Missing files: {missing}")
        return
    
    print(f"{'File':<40} | {'Rows':>6} | {'Cols':>3} | {'Missing':>7}")
    print("="*70)
    
    for filename in files:
        check_file(os.path.join(OUTPUT_DIR, filename), filename)
    
    validate_splits()
    
    sma_train = pd.read_csv(os.path.join(OUTPUT_DIR, 'fighter_vectors_sma_train.csv'))
    ema_train = pd.read_csv(os.path.join(OUTPUT_DIR, 'fighter_vectors_ema_train.csv'))
    
    validate_metrics(sma_train, 'sma')
    validate_metrics(ema_train, 'ema')
    
    print("\n==============")
    print("READY FOR MODEL TRAINING")
    print("==============\n")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
