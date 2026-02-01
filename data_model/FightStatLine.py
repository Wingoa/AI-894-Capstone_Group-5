from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class FightStatLine:
    fight_id: str
    fighter_id: str
    fighter: str
    kd: Optional[int]
    sig_str: str
    sig_str_pct: str
    total_str: str
    td: str
    td_pct: str
    sub_att: Optional[int]
    rev: Optional[int]
    ctrl: str
    head: str
    body: str
    leg: str
    distance: str
    clinch: str
    ground: str