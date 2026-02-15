import torch.nn as nn
import torch.nn.functional as F

class StyleNet(nn.Module):
    def __init__(self, d_in: int, hidden: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_in, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(0.15),

            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(0.15),

            nn.Linear(hidden, hidden // 2),
            nn.LayerNorm(hidden // 2),
            nn.GELU(),

            nn.Linear(hidden // 2, 4)
        )

    def forward(self, x):
        logits = self.net(x)
        comp = F.softmax(logits, dim=-1)  # [B,4], sums to 1
        return comp