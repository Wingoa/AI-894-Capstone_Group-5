import csv
from cache.BaseCsvCache import BaseCsvCache
from data_model.Event import Event

class EventCache(BaseCsvCache[str, Event]):
    FIELDS = ["event_id", "event_name", "event_date", "event_location", "event_url"]

    def key_of(self, value: Event) -> str:
        return value["event_id"]

    def _load_from_csv(self, csv_path) -> None:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                event_id = (row.get("event_id") or "").strip()
                if not event_id:
                    continue
                self._data[event_id] = Event(
                    event_id=event_id,
                    event_name=(row.get("event_name") or "").strip(),
                    event_date=(row.get("event_date") or "").strip(),
                    event_location=(row.get("event_location") or "").strip(),
                    event_url=(row.get("event_url") or "").strip(),
                )

    def append_to_csv(self, value: Event) -> None:
        # append-only persist (no rewrite)
        with self._lock:
            file_has_rows = False
            try:
                with open(self._csv_path, "r", newline="", encoding="utf-8") as f:
                    file_has_rows = f.read(1) != ""
            except FileNotFoundError:
                pass

            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                if not file_has_rows:
                    writer.writeheader()
                writer.writerow({
                    "event_id": value["event_id"],
                    "event_name": value["event_name"],
                    "event_date": value["event_date"],
                    "event_location": value["event_location"],
                    "event_url": value["event_url"],
                })
