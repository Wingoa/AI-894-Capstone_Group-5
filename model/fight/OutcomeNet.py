# outcome_net.py
from __future__ import annotations

import torch
import torch.nn as nn


class OutcomeNet(nn.Module):
    """
    Predicts P(Fighter A wins) from two per-fighter vectors fA and fB.

    Inputs:
      fA: [B, d]
      fB: [B, d]

    Matchup feature construction (fixed, interpretable):
      z = [fA, fB, (fA - fB), (fA * fB)]  -> [B, 4d]

    Output:
      logits: [B, 1]  (use torch.sigmoid(logits) for probability)
    """
    def __init__(self, d_fighter: int, hidden: int = 128, dropout: float = 0.20):
        super().__init__()
        d_in = 4 * d_fighter

        self.net = nn.Sequential(
            nn.Linear(d_in, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(dropout),

            nn.Linear(hidden, hidden // 2),
            nn.LayerNorm(hidden // 2),
            nn.GELU(),

            nn.Linear(hidden // 2, 1)
        )

    def forward(self, fA: torch.Tensor, fB: torch.Tensor) -> torch.Tensor:
        if fA.ndim != 2 or fB.ndim != 2:
            raise ValueError(f"Expected fA and fB to be 2D tensors; got {fA.shape=} {fB.shape=}")
        if fA.shape != fB.shape:
            raise ValueError(f"fA and fB must have the same shape; got {fA.shape=} {fB.shape=}")

        diff = fA - fB
        inter = fA * fB
        z = torch.cat([fA, fB, diff, inter], dim=-1)
        return self.net(z)


# -------------------------
# Optional helpers
# -------------------------
def outcome_probability(logits: torch.Tensor) -> torch.Tensor:
    """Convert logits -> probabilities."""
    return torch.sigmoid(logits)


def outcome_loss(logits: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """
    Stable binary classification loss.
    y should be shape [B] or [B,1] with values 0/1.
    """
    if y.ndim == 1:
        y = y.unsqueeze(1)
    return nn.BCEWithLogitsLoss()(logits, y.float())