from dataclasses import dataclass
from typing import Iterator

@dataclass(frozen=True)
class Event:
    event_id: str
    event_name: str
    event_date: str
    event_location: str
    event_url: str

    def __iter__(self) -> Iterator[str]:
        yield self.event_id
        yield self.event_name
        yield self.event_date
        yield self.event_location
        yield self.event_url

    def getEventId(self) -> str:
        return self.event_id