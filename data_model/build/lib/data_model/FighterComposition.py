from dataclasses import dataclass
from typing import Iterator

@dataclass(frozen=True)
class FighterComposition:
    pace: float
    boxing: float
    muay_thai: float
    wrestling: float
    grappling: float

    def __iter__(self) -> Iterator[str]:
        yield self.pace
        yield self.boxing
        yield self.muay_thai
        yield self.wrestling
        yield self.grappling