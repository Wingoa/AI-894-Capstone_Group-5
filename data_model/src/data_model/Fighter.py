from dataclasses import dataclass
from typing import List, Iterator
from FighterComposition import FighterComposition

@dataclass(frozen=True)
class Fighter:
    name: str
    id: str
    composition: FighterComposition
    fight_ids: List[str]

    def __iter__(self) -> Iterator[str]:
        yield self.name
        yield self.id
        yield self.composition
        yield self.fight_ids