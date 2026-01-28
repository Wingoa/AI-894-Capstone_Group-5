from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import csv
import os
import BaseCsvCache

# assumes BaseCsvCache is already defined exactly as earlier:
# class BaseCsvCache(ABC, Generic[K, T]): ...


@dataclass(frozen=True)
class EventFightInfo:
    event_id: str
    fight_id: Optional[str]
    winner_name: str
    loser_name: str
    weight_class: str
    method: Optional[str]
    round: Optional[int]
    time: Optional[str]
    fight_url: Optional[str]


class EventInfoCache(BaseCsvCache[str, List[EventFightInfo]]):
    """
    Key: event_id
    Value: list of EventFightInfo rows for that event
    """

    FIELDS = [
        "event_id",
        "fight_id",
        "winner_name",
        "loser_name",
        "weight_class",
        "method",
        "round",
        "time",
        "fight_url",
    ]

    def key_of(self, value: List[EventFightInfo]) -> str:
        if not value:
            raise ValueError("Cannot cache an empty list of EventFightInfo")
        return value[0].event_id

    # Like FightCache, we store list-per-key, so provide a line-level upsert.
    def upsert_line(self, info: EventFightInfo) -> None:
        """
        Add/append a single EventFightInfo into the event_id bucket.
        """
        self.load()
        with self._lock:
            self._data.setdefault(info.event_id, []).append(info)

    def get_event(self, event_id: str) -> List[EventFightInfo]:
        """
        Convenience: returns [] if event_id not found.
        """
        self.load()
        with self._lock:
            return list(self._data.get(event_id, []))

    def _load_from_csv(self, csv_path: str) -> None:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            fieldnames = set(reader.fieldnames or [])
            missing = set(self.FIELDS) - fieldnames
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            for row in reader:
                event_id = (row.get("event_id") or "").strip()
                if not event_id:
                    continue
                info = self._row_to_info(row)
                self._data.setdefault(event_id, []).append(info)

    def append_to_csv(self, value: List[EventFightInfo]) -> None:
        """
        Append a batch of EventFightInfo rows to the CSV (append-only).
        """
        self.load()
        with self._lock:
            file_exists = os.path.exists(self._csv_path)
            file_empty = (not file_exists) or (os.path.getsize(self._csv_path) == 0)

            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                if file_empty:
                    writer.writeheader()

                for info in value:
                    writer.writerow(self._info_to_row(info))

    def append_line_to_csv(self, info: EventFightInfo) -> None:
        """
        Convenience: append a single EventFightInfo row to the CSV (append-only).
        """
        self.load()
        with self._lock:
            file_exists = os.path.exists(self._csv_path)
            file_empty = (not file_exists) or (os.path.getsize(self._csv_path) == 0)

            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                if file_empty:
                    writer.writeheader()
                writer.writerow(self._info_to_row(info))

    def saveAll(self, events: List[Dict]) -> None:
        for event in events:
            print(f"Saving event info {event} to EventInfoCache")
            self.save(event)

    # -------- helpers --------

    @staticmethod
    def _clean_str(v) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s and s.lower() != "nan" else None

    @staticmethod
    def _clean_int(v) -> Optional[int]:
        s = EventInfoCache._clean_str(v)
        if s is None:
            return None
        try:
            return int(float(s))
        except ValueError:
            return None

    @classmethod
    def _row_to_info(cls, row: Dict) -> EventFightInfo:
        return EventFightInfo(
            event_id=cls._clean_str(row.get("event_id")) or "",
            fight_id=cls._clean_str(row.get("fight_id")),
            winner_name=cls._clean_str(row.get("winner_name")) or "",
            loser_name=cls._clean_str(row.get("loser_name")) or "",
            weight_class=cls._clean_str(row.get("weight_class")) or "",
            method=cls._clean_str(row.get("method")),
            round=cls._clean_int(row.get("round")),
            time=cls._clean_str(row.get("time")),
            fight_url=cls._clean_str(row.get("fight_url")),
        )

    @staticmethod
    def _info_to_row(info: EventFightInfo) -> Dict[str, object]:
        return {
            "event_id": info.event_id,
            "fight_id": info.fight_id or "",
            "winner_name": info.winner_name,
            "loser_name": info.loser_name,
            "weight_class": info.weight_class,
            "method": info.method or "",
            "round": "" if info.round is None else info.round,
            "time": info.time or "",
            "fight_url": info.fight_url or "",
        }
