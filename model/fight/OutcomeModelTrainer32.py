from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


# ----------------------------
# CONFIG
# ----------------------------
@dataclass
class Config:
    csv_path: str = "./outcome_training_vectors_2.csv"
    label_col: str = "y"
    out_dir: str = "./outcome_artifacts_32"

    test_size: float = 0.2
    random_state: int = 42

    batch_size: int = 256
    epochs: int = 15
    lr: float = 1e-3
    weight_decay: float = 1e-3
    grad_clip: float = 1.0

    hidden: int = 128
    dropout: float = 0.20

    device: str = "cuda" if torch.cuda.is_available() else "cpu"


CFG = Config()


# ----------------------------
# Canonical per-fighter order
# ----------------------------
FEATURE_ORDER: List[str] = [
    "wrestling",
    "grappling",
    "muay_thai",
    "boxing",
    "pace",
    "td_success",
    "ctrl_share",
    "n_fights_norm",
]

D_FIGHTER = len(FEATURE_ORDER)
D_MATCHUP = D_FIGHTER * 4  # A, B, A-B, A*B = 32


# ----------------------------
# Single-input 32-feature model
# ----------------------------
class OutcomeNet32(nn.Module):
    def __init__(self, d_input: int = 32, hidden: int = 128, dropout: float = 0.20):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_input, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ----------------------------
# Dataset
# ----------------------------
class FightDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


# ----------------------------
# Helpers
# ----------------------------
def load_and_validate(csv_path: str, label_col: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found in CSV.")

    required_A = [f"{c}_A" for c in FEATURE_ORDER]
    required_B = [f"{c}_B" for c in FEATURE_ORDER]
    missing = [c for c in (required_A + required_B) if c not in df.columns]
    if missing:
        raise ValueError(
            "Missing required columns. "
            f"Expected _A/_B suffixed columns for {FEATURE_ORDER}. "
            f"Missing: {missing[:10]}{'...' if len(missing) > 10 else ''}"
        )

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=[label_col]).copy()

    numeric_cols = required_A + required_B
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    df[label_col] = pd.to_numeric(df[label_col], errors="coerce").fillna(0.0)

    df = df[(df[label_col] == 0) | (df[label_col] == 1)].copy()
    return df


def build_matchup_matrix(
    df: pd.DataFrame,
    scaler: StandardScaler | None = None,
) -> Tuple[np.ndarray, np.ndarray, StandardScaler]:
    A_cols = [f"{c}_A" for c in FEATURE_ORDER]
    B_cols = [f"{c}_B" for c in FEATURE_ORDER]

    XA = df[A_cols].to_numpy(dtype=np.float32)
    XB = df[B_cols].to_numpy(dtype=np.float32)

    X_diff = XA - XB
    X_mul = XA * XB

    X_raw = np.hstack([XA, XB, X_diff, X_mul]).astype(np.float32)
    y = df[CFG.label_col].to_numpy(dtype=np.float32)

    if scaler is None:
        scaler = StandardScaler()
        scaler.fit(X_raw)

    X = scaler.transform(X_raw).astype(np.float32)

    scaled_flat = X[0]
    raw_flat = X_raw[0]

    # for i, (raw_val, scaled_val) in enumerate(zip(raw_flat, scaled_flat)):
    #     print(i, raw_val, scaled_val)

    feature_names = (
        [f"{c}_A" for c in FEATURE_ORDER]
        + [f"{c}_B" for c in FEATURE_ORDER]
        + [f"{c}_A_minus_B" for c in FEATURE_ORDER]
        + [f"{c}_A_times_B" for c in FEATURE_ORDER]
    )

    for name, raw_val, scaled_val in zip(feature_names, raw_flat, scaled_flat):
        print(f"{name}: raw={raw_val}, scaled={scaled_val}")

    return X, y, scaler


@torch.no_grad()
def evaluate(model: OutcomeNet32, dl: DataLoader, device: str) -> dict:
    model.eval()
    loss_fn = nn.BCEWithLogitsLoss()

    all_probs = []
    all_y = []
    total_loss = 0.0
    n = 0

    for X, y in dl:
        X, y = X.to(device), y.to(device)
        logits = model(X)
        loss = loss_fn(logits, y)

        total_loss += loss.item() * X.size(0)
        n += X.size(0)

        probs = torch.sigmoid(logits).cpu().numpy().reshape(-1)
        all_probs.append(probs)
        all_y.append(y.cpu().numpy().reshape(-1))

    probs = np.concatenate(all_probs) if all_probs else np.array([])
    ytrue = np.concatenate(all_y) if all_y else np.array([])

    metrics = {"loss": total_loss / max(1, n)}
    if len(ytrue) > 0 and len(np.unique(ytrue)) > 1:
        metrics["auc"] = float(roc_auc_score(ytrue, probs))
        metrics["logloss"] = float(log_loss(ytrue, np.clip(probs, 1e-6, 1 - 1e-6)))
    else:
        metrics["auc"] = float("nan")
        metrics["logloss"] = float("nan")

    metrics["acc"] = float(accuracy_score(ytrue, (probs >= 0.5).astype(np.float32)))
    return metrics


# ----------------------------
# Train Script
# ----------------------------
def main():
    os.makedirs(CFG.out_dir, exist_ok=True)

    df = load_and_validate(CFG.csv_path, CFG.label_col)
    print(f"Loaded {len(df)} fights from {CFG.csv_path}")
    print(df["n_fights_norm_A"].describe())

    train_df, test_df = train_test_split(
        df,
        test_size=CFG.test_size,
        random_state=CFG.random_state,
        stratify=df[CFG.label_col],
    )
    print(f"Train: {len(train_df)} | Test: {len(test_df)}")

    X_train, y_train, scaler = build_matchup_matrix(train_df, scaler=None)
    X_test, y_test, _ = build_matchup_matrix(test_df, scaler=scaler)

    print(f"Training matrix shape: {X_train.shape}")
    print(f"Expected matchup width: {D_MATCHUP}")

    train_dl = DataLoader(FightDataset(X_train, y_train), batch_size=CFG.batch_size, shuffle=True)
    test_dl = DataLoader(FightDataset(X_test, y_test), batch_size=CFG.batch_size, shuffle=False)

    torch.manual_seed(CFG.random_state)
    model = OutcomeNet32(d_input=D_MATCHUP, hidden=CFG.hidden, dropout=CFG.dropout).to(CFG.device)
    opt = torch.optim.AdamW(model.parameters(), lr=CFG.lr, weight_decay=CFG.weight_decay)
    loss_fn = nn.BCEWithLogitsLoss()

    best_test_loss = float("inf")
    best_state = None

    for epoch in range(1, CFG.epochs + 1):
        model.train()
        running = 0.0
        n = 0

        for X, y in train_dl:
            X, y = X.to(CFG.device), y.to(CFG.device)

            opt.zero_grad(set_to_none=True)
            logits = model(X)
            loss = loss_fn(logits, y)
            loss.backward()

            if CFG.grad_clip:
                torch.nn.utils.clip_grad_norm_(model.parameters(), CFG.grad_clip)

            opt.step()
            running += loss.item() * X.size(0)
            n += X.size(0)

        train_loss = running / max(1, n)
        test_metrics = evaluate(model, test_dl, CFG.device)

        if test_metrics["loss"] < best_test_loss:
            best_test_loss = test_metrics["loss"]
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}

        if epoch % 5 == 0 or epoch == 1:
            print(
                f"epoch {epoch:03d} | train_loss={train_loss:.4f} | "
                f"test_loss={test_metrics['loss']:.4f} | "
                f"AUC={test_metrics['auc']:.3f} | ACC={test_metrics['acc']:.3f} | "
                f"logloss={test_metrics['logloss']:.4f}"
            )

    if best_state is not None:
        model.load_state_dict(best_state)

    model_path = os.path.join(CFG.out_dir, "outcome_model.pt")
    scaler_path = os.path.join(CFG.out_dir, "scaler.pkl")
    meta_path = os.path.join(CFG.out_dir, "metadata.json")

    torch.save(model.state_dict(), model_path)
    joblib.dump(scaler, scaler_path)

    metadata = {
        "csv_path": CFG.csv_path,
        "label_col": CFG.label_col,
        "feature_order": FEATURE_ORDER,
        "d_fighter": D_FIGHTER,
        "d_matchup": D_MATCHUP,
        "matchup_vector_order": (
            [f"{c}_A" for c in FEATURE_ORDER]
            + [f"{c}_B" for c in FEATURE_ORDER]
            + [f"{c}_A_minus_B" for c in FEATURE_ORDER]
            + [f"{c}_A_times_B" for c in FEATURE_ORDER]
        ),
        "train_config": {
            "test_size": CFG.test_size,
            "epochs": CFG.epochs,
            "batch_size": CFG.batch_size,
            "lr": CFG.lr,
            "weight_decay": CFG.weight_decay,
            "hidden": CFG.hidden,
            "dropout": CFG.dropout,
            "random_state": CFG.random_state,
        },
        "best_test_loss": best_test_loss,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved model:  {model_path}")
    print(f"Saved scaler: {scaler_path}")
    print(f"Saved meta:   {meta_path}")


if __name__ == "__main__":
    main()