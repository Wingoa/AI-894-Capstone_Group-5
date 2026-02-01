from dataclasses import dataclass

@dataclass(frozen=True)
class FighterComposition:
    pace: float
    boxing: float
    muay_thai: float
    wrestling: float
    grappling: float