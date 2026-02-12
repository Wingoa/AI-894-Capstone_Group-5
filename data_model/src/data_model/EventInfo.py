from dataclasses import dataclass
from typing import Optional, Iterator

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

    def __iter__(self) -> Iterator[object]:
        yield self.event_id
        yield self.fight_id
        yield self.winner_name
        yield self.loser_name
        yield self.weight_class
        yield self.method
        yield self.round
        yield self.time
        yield self.fight_url

    def getEventId(self) -> str:
        return self.event_id
    
    def getFightId(self) -> str:
        return self.fight_id

