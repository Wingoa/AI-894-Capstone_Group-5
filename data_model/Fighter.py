from dataclasses import dataclass
from typing import List
from FighterComposition import FighterComposition

@dataclass(frozen=True)
class Fighter:
    name: str
    id: str
    composition: FighterComposition
    fight_ids: List[str]