from dataclasses import dataclass
from typing import Optional, Iterator

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

    def __iter__(self) -> Iterator[object]:
        yield self.fight_id
        yield self.fighter_id
        yield self.fighter
        yield self.kd
        yield self.sig_str
        yield self.sig_str_pct
        yield self.total_str
        yield self.td
        yield self.td_pct
        yield self.sub_att
        yield self.rev
        yield self.ctrl
        yield self.head
        yield self.body
        yield self.leg
        yield self.distance
        yield self.clinch
        yield self.ground

    def getFightId(self) -> str:
        return self.fight_id