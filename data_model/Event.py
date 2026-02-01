from dataclasses import dataclass

@dataclass(frozen=True)
class Event:
    event_id: str
    event_name: str
    event_date: str
    event_location: str
    event_url: str