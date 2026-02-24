from dataclasses import dataclass
from typing import List, Iterator
import datetime

@dataclass(frozen=True)
class FighterStyle:
    fighter_id: str
    fighter: str
    muayThai: float
    boxing: float
    wrestling: float
    grappling: float

    def __iter__(self) -> Iterator[str]:
        yield self.fighter_id
        yield self.fighter
        yield self.muayThai
        yield self.boxing
        yield self.wrestling
        yield self.grappling