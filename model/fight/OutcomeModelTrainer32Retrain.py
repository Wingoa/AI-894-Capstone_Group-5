from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


# ----------------------------
# CONFIG
# ----------------------------
@dataclass
class Config:
    csv_path: str = "./outcome_training_vectors.csv"
    label_col: str = "y"
    out_dir: str = "./outcome_artifacts_32_retrain"

    test_size: float = 0.15
    val_size: float = 0.15
    random_state: int = 42

    batch_size: int = 128
    epochs: int = 100
    patience: int = 10

    lr: float = 5e-4
    weight_decay: float = 3e-3
    grad_clip: float = 1.0

    hidden: int = 64
    dropout: float = 0.30

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
# Model
# ----------------------------
class OutcomeNet32(nn.Module):
    def __init__(self, d_input: int = 32, hidden: int = 64, dropout: float = 0.30):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_input, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(hidden, hidden),
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
    return X, y, scaler


@torch.no_grad()
def evaluate(model: nn.Module, dl: DataLoader, device: str) -> dict:
    model.eval()
    loss_fn = nn.BCEWithLogitsLoss()

    all_logits = []
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
        all_logits.append(logits.cpu().numpy().reshape(-1))
        all_y.append(y.cpu().numpy().reshape(-1))

    probs = np.concatenate(all_probs) if all_probs else np.array([])
    logits = np.concatenate(all_logits) if all_logits else np.array([])
    ytrue = np.concatenate(all_y) if all_y else np.array([])

    metrics = {
        "loss": total_loss / max(1, n),
        "mean_abs_logit": float(np.mean(np.abs(logits))) if len(logits) else float("nan"),
    }

    if len(ytrue) > 0:
        metrics["acc"] = float(accuracy_score(ytrue, (probs >= 0.5).astype(np.float32)))
    else:
        metrics["acc"] = float("nan")

    if len(ytrue) > 0 and len(np.unique(ytrue)) > 1:
        metrics["auc"] = float(roc_auc_score(ytrue, probs))
        metrics["logloss"] = float(log_loss(ytrue, np.clip(probs, 1e-6, 1 - 1e-6)))
    else:
        metrics["auc"] = float("nan")
        metrics["logloss"] = float("nan")

    return metrics


def make_loaders(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> Tuple[DataLoader, DataLoader, DataLoader, StandardScaler]:
    X_train, y_train, scaler = build_matchup_matrix(train_df, scaler=None)
    X_val, y_val, _ = build_matchup_matrix(val_df, scaler=scaler)
    X_test, y_test, _ = build_matchup_matrix(test_df, scaler=scaler)

    print(f"Train matrix shape: {X_train.shape}")
    print(f"Val matrix shape:   {X_val.shape}")
    print(f"Test matrix shape:  {X_test.shape}")
    print(f"Scaler expects:     {scaler.n_features_in_} features")

    train_dl = DataLoader(FightDataset(X_train, y_train), batch_size=CFG.batch_size, shuffle=True)
    val_dl = DataLoader(FightDataset(X_val, y_val), batch_size=CFG.batch_size, shuffle=False)
    test_dl = DataLoader(FightDataset(X_test, y_test), batch_size=CFG.batch_size, shuffle=False)

    return train_dl, val_dl, test_dl, scaler


# ----------------------------
# Train Script
# ----------------------------
def main():
    os.makedirs(CFG.out_dir, exist_ok=True)

    # 1) Load & validate
    df = load_and_validate(CFG.csv_path, CFG.label_col)
    print(f"Loaded {len(df)} fights from {CFG.csv_path}")

    # 2) Split into train / temp
    train_df, temp_df = train_test_split(
        df,
        test_size=(CFG.val_size + CFG.test_size),
        random_state=CFG.random_state,
        stratify=df[CFG.label_col],
    )

    # 3) Split temp into val / test
    relative_test_size = CFG.test_size / (CFG.val_size + CFG.test_size)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=relative_test_size,
        random_state=CFG.random_state,
        stratify=temp_df[CFG.label_col],
    )

    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

    # 4) Build loaders and scaler
    train_dl, val_dl, test_dl, scaler = make_loaders(train_df, val_df, test_df)

    # 5) Model
    torch.manual_seed(CFG.random_state)
    model = OutcomeNet32(
        d_input=D_MATCHUP,
        hidden=CFG.hidden,
        dropout=CFG.dropout,
    ).to(CFG.device)

    opt = torch.optim.AdamW(
        model.parameters(),
        lr=CFG.lr,
        weight_decay=CFG.weight_decay,
    )
    loss_fn = nn.BCEWithLogitsLoss()

    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0
    epochs_without_improvement = 0

    # 6) Train loop
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
        val_metrics = evaluate(model, val_dl, CFG.device)

        improved = val_metrics["loss"] < best_val_loss - 1e-5
        if improved:
            best_val_loss = val_metrics["loss"]
            best_epoch = epoch
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epoch % 5 == 0 or epoch == 1:
            print(
                f"epoch {epoch:03d} | "
                f"train_loss={train_loss:.4f} | "
                f"val_loss={val_metrics['loss']:.4f} | "
                f"val_auc={val_metrics['auc']:.3f} | "
                f"val_acc={val_metrics['acc']:.3f} | "
                f"val_logloss={val_metrics['logloss']:.4f} | "
                f"mean|logit|={val_metrics['mean_abs_logit']:.2f}"
            )

        if epochs_without_improvement >= CFG.patience:
            print(f"Early stopping at epoch {epoch} (best epoch: {best_epoch})")
            break

    # 7) Restore best model
    if best_state is not None:
        model.load_state_dict(best_state)

    # 8) Final test evaluation
    test_metrics = evaluate(model, test_dl, CFG.device)
    print(
        f"FINAL TEST | "
        f"loss={test_metrics['loss']:.4f} | "
        f"auc={test_metrics['auc']:.3f} | "
        f"acc={test_metrics['acc']:.3f} | "
        f"logloss={test_metrics['logloss']:.4f} | "
        f"mean|logit|={test_metrics['mean_abs_logit']:.2f}"
    )

    # 9) Save artifacts
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
        "train_config": asdict(CFG),
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "final_test_metrics": test_metrics,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved model:  {model_path}")
    print(f"Saved scaler: {scaler_path}")
    print(f"Saved meta:   {meta_path}")


if __name__ == "__main__":
    main()