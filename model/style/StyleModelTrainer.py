import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import torch
from torch.utils.data import Dataset, DataLoader

from StyleNet import StyleNet

CSV_PATH = "../../resources/fighter_vectors/fighter_vectors_all.csv"
BUCKETS = ["MuayThai", "Boxing", "Wrestling", "Grappling"]


# -----------------------------
# 1) Load
# -----------------------------
df = pd.read_csv(CSV_PATH)

# Sort by time if you want time-aware splits later
df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
df = df.sort_values("event_date")
print(f"CSV loaded, example row: {df}")


# -----------------------------
# 2) Choose input features X
#    (behavior-focused)
# -----------------------------
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

X_raw = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=np.float32)


# -----------------------------
# 3) Bootstrap soft labels Y (weak supervision)
# -----------------------------
def softmax_np(z: np.ndarray, temp: float = 1.0) -> np.ndarray:
    z = z / temp
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / (e.sum(axis=1, keepdims=True) + 1e-12)

# Work in standardized space so each term contributes comparably
scaler_for_targets = StandardScaler()
Xz = scaler_for_targets.fit_transform(X_raw)

# Map z-scored features into bucket scores
idx = {c:i for i,c in enumerate(feature_cols)}

boxing_score = (
    0.40 * Xz[:, idx["distance_strike_ratio"]] +
    0.40 * Xz[:, idx["head_target_ratio"]] +
    0.20 * Xz[:, idx["kd_per_min"]]
)

muaythai_score = (
    0.30 * Xz[:, idx["clinch_strike_ratio"]] +
    0.35 * Xz[:, idx["leg_target_ratio"]] +
    0.35 * Xz[:, idx["body_target_ratio"]]
)

wrestling_score = (
    0.45 * Xz[:, idx["td_att_per_min"]] +
    0.35 * Xz[:, idx["ctrl_sec_per_min"]] +
    0.20 * Xz[:, idx["td_success_per_min"]]
)

grappling_score = (
    0.45 * Xz[:, idx["sub_att_per_min"]] +
    0.35 * Xz[:, idx["ground_strike_ratio"]] +
    0.20 * Xz[:, idx["ground_str_per_min"]]
)

# pace_score = (
#     0.70 * Xz[:, idx["sig_str_per_min"]] +
#     0.30 * (
#         Xz[:, idx["distance_str_per_min"]] +
#         Xz[:, idx["clinch_str_per_min"]] +
#         Xz[:, idx["ground_str_per_min"]]
#     )
# )

scores = np.stack([muaythai_score, boxing_score, wrestling_score, grappling_score], axis=1)
Y = softmax_np(scores, temp=1.0).astype(np.float32)  # [N,4], sums to 1


# -----------------------------
# 4) Train/val split + scale X
# -----------------------------
X_train_raw, X_val_raw, Y_train, Y_val = train_test_split(
    X_raw, Y, test_size=0.2, random_state=42
)

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train_raw).astype(np.float32)
X_val = scaler.transform(X_val_raw).astype(np.float32)


# -----------------------------
# 5) Torch dataset
# -----------------------------
class DS(Dataset):
    def __init__(self, X, Y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.Y = torch.tensor(Y, dtype=torch.float32)
    def __len__(self): return len(self.X)
    def __getitem__(self, i): return self.X[i], self.Y[i]

train_dl = DataLoader(DS(X_train, Y_train), batch_size=128, shuffle=True)
val_dl = DataLoader(DS(X_val, Y_val), batch_size=256, shuffle=False)


# -----------------------------
# 6) Model: composition predictor
# -----------------------------

device = "cuda" if torch.cuda.is_available() else "cpu"
model = StyleNet(d_in=X_train.shape[1]).to(device)
print(X_train.shape[1])
opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)

def loss_fn(pred, y):
    # KL divergence-style loss for distributions (stable for soft labels)
    pred = pred.clamp(1e-6, 1.0)
    y = y.clamp(1e-6, 1.0)
    return (y * (torch.log(y) - torch.log(pred))).sum(dim=1).mean()


# -----------------------------
# 7) Train
# -----------------------------
for epoch in range(1, 61):
    model.train()
    tr = 0.0
    for xb, yb in train_dl:
        xb, yb = xb.to(device), yb.to(device)
        opt.zero_grad()
        pred = model(xb)
        loss = loss_fn(pred, yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        tr += loss.item() * xb.size(0)
    tr /= len(train_dl.dataset)

    model.eval()
    va = 0.0
    with torch.no_grad():
        for xb, yb in val_dl:
            xb, yb = xb.to(device), yb.to(device)
            pred = model(xb)
            va += loss_fn(pred, yb).item() * xb.size(0)
    va /= len(val_dl.dataset)

    if epoch % 5 == 0:
        print(f"epoch={epoch:02d} train={tr:.4f} val={va:.4f}")


# -----------------------------
# 8) Predict styles for all rows
# -----------------------------
model.eval()
X_all = scaler.transform(X_raw).astype(np.float32)
with torch.no_grad():
    comps = model(torch.tensor(X_all).to(device)).cpu().numpy()

out = df[["fighter_id", "fighter", "event_date", "weight_class"]].copy()
for i, b in enumerate(BUCKETS):
    out[b] = comps[:, i]

out.to_csv("../../resources/fighter_vectors/fighter_style_predictions-test.csv", index=False)
print("Wrote: ../../resources/fighter_vectors/fighter_style_predictions-test.csv")


# -----------------------------
# 9) Save model metadata
# -----------------------------
# torch.save(model.state_dict(), "./metadata/style_model.pt")
# joblib.dump(scaler, "./metadata/scaler.pkl")