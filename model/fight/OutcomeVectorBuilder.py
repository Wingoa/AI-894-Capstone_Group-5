"""
This class serves to combine the data from outcome_vectors into single rows of fight data:

[Fa,Fb,Fa-Fb,Fa*Fb]
"""

import pandas as pd

df = pd.read_csv("../../resources/fighter_vectors/outcome_vectors.csv")

# Drop fights that happened over 10 years ago
df = df[pd.to_datetime(df["event_date"]) >= (pd.Timestamp.today() - pd.DateOffset(years=10))]

# Drop fights where fighters had too little data
df = df[df["n_fights_norm"] >= 0.2]

# Explicit feature vectors
feature_cols = [
    "muay_thai",
    "boxing",
    "wrestling",
    "grappling",
    "pace",
    "td_success",
    "ctrl_share",
    "n_fights_norm",
]

df[feature_cols] = df[feature_cols].apply(pd.to_numeric, errors="coerce")

df["fighter_idx"] = df.groupby("fight_id").cumcount()

# Keep only fights with exactly 2 rows
df = df.groupby("fight_id").filter(lambda g: len(g) == 2)

# Pivot the dataset
match_df = df.pivot(
    index="fight_id",
    columns="fighter_idx",
    values=feature_cols    
)

# Flatten column names
match_df.columns = [
    f"{col}_A" if idx == 0 else f"{col}_B"
    for col, idx in match_df.columns
]
match_df = match_df.reset_index()

# Add matchup features (difference and product)
match_df = match_df.fillna(0)

for col in feature_cols:
    match_df[f"{col}_diff"] = match_df[f"{col}_A"] - match_df[f"{col}_B"]
    match_df[f"{col}_inter"] = match_df[f"{col}_A"] * match_df[f"{col}_B"]

# Create the label
win_df = df[["fight_id", "fighter_idx", "win"]].pivot(
    index="fight_id",
    columns="fighter_idx",
    values="win"
)
match_df["y"] = (win_df[0] == 1).astype(int).values

match_df.to_csv("test.csv", mode="a", index=False, header=True)