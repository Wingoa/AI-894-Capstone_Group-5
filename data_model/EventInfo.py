from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class EventInfo:
    event_id: str
    fight_id: Optional[str]
    winner_name: str
    loser_name: str
    weight_class: str
    method: Optional[str]
    round: Optional[int]
    time: Optional[str]
    fight_url: Optional[str]