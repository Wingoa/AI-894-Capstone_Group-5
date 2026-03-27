# train_outcome_net.py
# Trains OutcomeNet from a single CSV of fight-level rows.
#
# EXPECTED CSV SCHEMA (one row per fight):
#   - fight_id (optional)
#   - label column: y (1 if Fighter A wins, 0 if Fighter A loses)
#   - Fighter A feature columns prefixed with "A_"
#   - Fighter B feature columns prefixed with "B_"
#
# Example required columns:
#   y,
#   A_wrestling, A_grappling, A_muay_thai, A_boxing, A_pace, A_sig_accuracy, A_td_success,
#   A_ctrl_share, A_age, A_reach, A_n_fights_norm, A_days_since_last_log,
#   B_wrestling, ... same set for B_
#
# Outputs:
#   - outcome_model.pt
#   - scaler.pkl
#   - metadata.json (feature order, split details, metrics)

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

from OutcomeNet import OutcomeNet


# ----------------------------
# CONFIG
# ----------------------------
@dataclass
class Config:
    csv_path: str = "./outcome_training_vectors.csv"
    label_col: str = "y"                  # 1 if A wins, 0 if A loses
    out_dir: str = "./outcome_artifacts"

    test_size: float = 0.2
    random_state: int = 42

    batch_size: int = 256
    epochs: int = 40
    lr: float = 1e-3
    weight_decay: float = 1e-3
    grad_clip: float = 1.0

    hidden: int = 128
    dropout: float = 0.20

    device: str = "cuda" if torch.cuda.is_available() else "cpu"

CFG = Config()


# ----------------------------
# Canonical per-fighter order
# (must match the columns in the CSV with A_/B_ prefixes)
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


# ----------------------------
# Dataset
# ----------------------------
class FightDataset(Dataset):
    def __init__(self, XA: np.ndarray, XB: np.ndarray, y: np.ndarray):
        self.XA = torch.tensor(XA, dtype=torch.float32)
        self.XB = torch.tensor(XB, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int):
        return self.XA[idx], self.XB[idx], self.y[idx]


# ----------------------------
# Helpers
# ----------------------------
def load_and_validate(csv_path: str, label_col: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found in CSV.")

    # Check required A_/B_ columns
    required_A = [f"{c}_A" for c in FEATURE_ORDER]
    required_B = [f"{c}_B" for c in FEATURE_ORDER]
    missing = [c for c in (required_A + required_B) if c not in df.columns]
    if missing:
        raise ValueError(
            "Missing required columns. "
            f"Expected _A/_B suffixed columns for {FEATURE_ORDER}. "
            f"Missing: {missing[:10]}{'...' if len(missing)>10 else ''}"
        )

    # Clean: replace inf, fill NaNs
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=[label_col])  # label must exist
    df[required_A + required_B] = df[required_A + required_B].fillna(0.0)

    # Force numeric
    df[required_A + required_B] = df[required_A + required_B].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    df[label_col] = pd.to_numeric(df[label_col], errors="coerce").fillna(0.0)

    # Ensure labels are 0/1
    df = df[(df[label_col] == 0) | (df[label_col] == 1)].copy()
    return df


def build_arrays(df: pd.DataFrame, scaler: StandardScaler | None = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    A_cols = [f"{c}_A" for c in FEATURE_ORDER]
    B_cols = [f"{c}_B" for c in FEATURE_ORDER]

    XA_raw = df[A_cols].to_numpy(dtype=np.float32)
    XB_raw = df[B_cols].to_numpy(dtype=np.float32)
    y = df[CFG.label_col].to_numpy(dtype=np.float32)

    # Fit scaler on both sides together to ensure identical scaling
    if scaler is None:
        scaler = StandardScaler()
        scaler.fit(np.vstack([XA_raw, XB_raw]))

    XA = scaler.transform(XA_raw).astype(np.float32)
    XB = scaler.transform(XB_raw).astype(np.float32)
    return XA, XB, y, scaler


@torch.no_grad()
def evaluate(model: OutcomeNet, dl: DataLoader, device: str) -> dict:
    model.eval()
    loss_fn = nn.BCEWithLogitsLoss()

    all_probs = []
    all_y = []
    total_loss = 0.0
    n = 0

    for XA, XB, y in dl:
        XA, XB, y = XA.to(device), XB.to(device), y.to(device)
        logits = model(XA, XB)
        loss = loss_fn(logits, y)
        total_loss += loss.item() * XA.size(0)
        n += XA.size(0)

        probs = torch.sigmoid(logits).cpu().numpy().reshape(-1)
        all_probs.append(probs)
        all_y.append(y.cpu().numpy().reshape(-1))

    probs = np.concatenate(all_probs) if all_probs else np.array([])
    ytrue = np.concatenate(all_y) if all_y else np.array([])

    metrics = {"loss": total_loss / max(1, n)}
    if len(np.unique(ytrue)) > 1:
        metrics["auc"] = float(roc_auc_score(ytrue, probs))
    else:
        metrics["auc"] = float("nan")
    metrics["acc"] = float(accuracy_score(ytrue, (probs >= 0.5).astype(np.float32)))
    metrics["logloss"] = float(log_loss(ytrue, np.clip(probs, 1e-6, 1 - 1e-6)))
    return metrics


# ----------------------------
# Train Script
# ----------------------------
def main():
    os.makedirs(CFG.out_dir, exist_ok=True)

    # 1) Load & validate
    df = load_and_validate(CFG.csv_path, CFG.label_col)
    print(f"Loaded {len(df)} fights from {CFG.csv_path}")

    # 2) Split
    train_df, test_df = train_test_split(df, test_size=CFG.test_size, random_state=CFG.random_state, stratify=df[CFG.label_col])
    print(f"Train: {len(train_df)} | Test: {len(test_df)}")

    # 3) Scale
    XA_train, XB_train, y_train, scaler = build_arrays(train_df, scaler=None)
    XA_test,  XB_test,  y_test,  _      = build_arrays(test_df, scaler=scaler)

    # 4) Dataloaders
    train_dl = DataLoader(FightDataset(XA_train, XB_train, y_train), batch_size=CFG.batch_size, shuffle=True)
    test_dl  = DataLoader(FightDataset(XA_test,  XB_test,  y_test),  batch_size=CFG.batch_size, shuffle=False)

    # 5) Model
    torch.manual_seed(CFG.random_state)
    model = OutcomeNet(d_fighter=D_FIGHTER, hidden=CFG.hidden, dropout=CFG.dropout).to(CFG.device)
    opt = torch.optim.AdamW(model.parameters(), lr=CFG.lr, weight_decay=CFG.weight_decay)
    loss_fn = nn.BCEWithLogitsLoss()

    best_test_loss = float("inf")
    best_state = None

    # 6) Train loop
    for epoch in range(1, CFG.epochs + 1):
        model.train()
        running = 0.0
        n = 0

        for XA, XB, y in train_dl:
            XA, XB, y = XA.to(CFG.device), XB.to(CFG.device), y.to(CFG.device)

            opt.zero_grad(set_to_none=True)
            logits = model(XA, XB)
            loss = loss_fn(logits, y)
            loss.backward()

            if CFG.grad_clip:
                torch.nn.utils.clip_grad_norm_(model.parameters(), CFG.grad_clip)

            opt.step()
            running += loss.item() * XA.size(0)
            n += XA.size(0)

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

    # 7) Save artifacts
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
        "matchup_vector": ["fA", "fB", "fA-fB", "fA*fB"],
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