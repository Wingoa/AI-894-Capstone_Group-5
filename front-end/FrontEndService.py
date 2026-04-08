from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
import csv
import os
import requests

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.Fighter import Fighter
from data_model.FighterComposition import FighterComposition
from data_model.FighterStyle import FighterStyle


class FrontEndService:
    def __init__(self) -> None:
        # Initialize CSV paths and API URLs
        project_root = Path(__file__).resolve().parent.parent
        self._events_csv = project_root / "resources" / "initial_data" / "events.csv"
        self._events_info_csv = project_root / "resources" / "initial_data" / "events-info.csv"
        self._fights_csv = project_root / "resources" / "initial_data" / "fights.csv"
        self._training_csv = project_root / "resources" / "clean_data" / "training_data.csv"
        
        # API URLs: Execution Service for upcoming fights, Prediction Service for fighter styles/predictions
        self._execution_api_url = os.getenv("EXECUTION_SERVICE_URL", "http://localhost:8003").rstrip("/")
        self._prediction_service_url = os.getenv("PREDICTION_SERVICE_URL", "http://localhost:8002").rstrip("/")

    def getNextFights(self) -> dict:
        """Get upcoming fights from the Execution Service."""
        resp = requests.get(f"{self._execution_api_url}/nextFights", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def getLastFights(self) -> List[EventInfo]:
        # Return completed fights (past events with fight_id present)
        events_by_id = self._load_event_dates()
        completed_ids = {
            event_id
            for event_id, event_date in events_by_id.items()
            if event_date < date.today()
        }
        rows = self._load_event_info_rows()
        completed = []
        for row in rows:
            if row.event_id in completed_ids and row.fight_id:
                completed.append(row)
        return completed
    
    def getAllEvents(self) -> List[Event]:
        # Load all events from the events CSV
        events: List[Event] = []
        with self._events_csv.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                event_id = (row.get("event_id") or "").strip()
                if not event_id:
                    continue
                events.append(Event(
                    event_id       = event_id,
                    event_name     = (row.get("event_name")     or "").strip(),
                    event_date     = (row.get("event_date")     or "").strip(),
                    event_location = (row.get("event_location") or "").strip(),
                    event_url      = (row.get("event_url")      or "").strip(),
                ))
        return sorted(
            events,
            key=lambda e: self._parse_event_date(e.event_date) or date.min,
            reverse=True,
        )

    def getNextFightsWithEvents(self) -> List[dict]:
        # Fetch upcoming fights from the data API and normalize them
        api_fights = self._get_next_fights_from_api()
        return api_fights or []

    def getLastFightsWithEvents(self) -> List[Tuple[EventInfo, Optional[Event]]]:
        # Return past fights paired with their event metadata
        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        return [
            (info, events_by_id.get(info.event_id))
            for info in self.getLastFights()
        ]

    def _get_next_fights_from_api(self) -> Optional[List[dict]]:
        # Call the data API /event/next endpoint and normalize the response
        try:
            resp = requests.get(f"{self._execution_api_url}/nextFights", timeout=2.5)
            if resp.status_code != 200:
                return None
            payload = resp.json()
        except Exception:
            return None

        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        fights = payload.get("fights") or []
        if not fights:
            return None

        normalized: List[dict] = []
        for fight in fights:
            event_id = fight.get("event_id") or ""
            event = events_by_id.get(event_id) if event_id else None
            
            normalized.append({
                "event_name": (event.event_name if event else fight.get("event_name")) or event_id,
                "date": (event.event_date if event else fight.get("date")) or "—",
                "location": (event.event_location if event else fight.get("location")) or "—",
                "event_url": event.event_url if event else fight.get("event_url"),
                "red_fighter": fight.get("red_fighter") or "",
                "blue_fighter": fight.get("blue_fighter") or "",
                "red_id": "",
                "blue_id": "",
                "weight_class": fight.get("weight_class") or "",
                "method": fight.get("method"),
                "round": fight.get("round"),
                "time": fight.get("time"),
                "fight_url": fight.get("fight_url"),
            })
        return normalized

    def loadEventInfo(self, event_id: str) -> Optional[EventInfo]:
        # Return the first EventInfo row matching event_id, if any
        for row in self._load_event_info_rows():
            if row.event_id == event_id:
                return row
        return None

    def loadEventInfoRows(self) -> List[EventInfo]:
        # Load all EventInfo rows from CSV
        return self._load_event_info_rows()
    
    def getAllFighters(self) -> List[Fighter]:
        # Build Fighter objects with composition and fight_id history
        fights_by_fighter: Dict[str, List[str]] = defaultdict(list)
        names_by_id: Dict[str, str] = {}
        with self._fights_csv.open("r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                fighter_id = (row.get("fighter_id") or "").strip()
                fighter_name = (row.get("fighter") or "").strip()
                fight_id = (row.get("fight_id") or "").strip()
                if not fighter_id or not fighter_name:
                    continue
                names_by_id[fighter_id] = fighter_name
                if fight_id:
                    fights_by_fighter[fighter_id].append(fight_id)
        composition_by_fighter = self._compute_fighter_compositions()
        fighters: List[Fighter] = []
        for fighter_id, fighter_name in names_by_id.items():
            fighters.append(
                Fighter(
                    name=fighter_name,
                    id=fighter_id,
                    composition=composition_by_fighter.get(
                        fighter_id,
                        FighterComposition(
                            pace=0.0,
                            boxing=0.0,
                            muay_thai=0.0,
                            wrestling=0.0,
                            grappling=0.0,
                        ),
                    ),
                    fight_ids=fights_by_fighter.get(fighter_id, []),
                )
            )
        return sorted(fighters, key=lambda fighter: fighter.name)

    def getFighter(self, fighter_id: str) -> Optional[Fighter]:
        # Find a fighter by id
        for fighter in self.getAllFighters():
            if fighter.id == fighter_id:
                return fighter
        return None

    def getFighterStyle(self, fighter_id: str) -> FighterStyle:
        """Query the Prediction Service for fighter style weights."""
        resp = requests.get(f"{self._prediction_service_url}/style/{fighter_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return FighterStyle(
            data["fighter_id"],
            data["fighter"],
            float(data["muayThai"]),
            float(data["boxing"]),
            float(data["wrestling"]),
            float(data["grappling"]),
        )

    def predictFight(self, fighter_a_id: str, fighter_b_id: str):
        """Query the Prediction Service for a fight outcome prediction."""
        queryParams = {
            "fighter_a_id": fighter_a_id,
            "fighter_b_id": fighter_b_id,
        }
        resp = requests.get(
            f"{self._prediction_service_url}/outcome",
            params=queryParams,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def _load_event_dates(self) -> Dict[str, date]:
        # Parse event dates from the events CSV into a dict
        event_dates: Dict[str, date] = {}
        with self._events_csv.open("r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                event_id = (row.get("event_id") or "").strip()
                date_str = (row.get("event_date") or "").strip()
                parsed_date = self._parse_event_date(date_str)
                if event_id and parsed_date:
                    event_dates[event_id] = parsed_date
        return event_dates

    def _load_event_info_rows(self) -> List[EventInfo]:
        # Load EventInfo rows from events-info CSV
        rows: List[EventInfo] = []
        with self._events_info_csv.open("r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                rows.append(
                    EventInfo(
                        event_id=(row.get("event_id") or "").strip(),
                        fight_id=self._nullable_str(row.get("fight_id")),
                        winner_name=(row.get("winner_name") or "").strip(),
                        loser_name=(row.get("loser_name") or "").strip(),
                        weight_class=(row.get("weight_class") or "").strip(),
                        method=self._nullable_str(row.get("method")),
                        round=self._nullable_int(row.get("round")),
                        time=self._nullable_str(row.get("time")),
                        fight_url=self._nullable_str(row.get("fight_url")),
                    )
                )
        return rows

    def _compute_fighter_compositions(self) -> Dict[str, FighterComposition]:
        # Aggregate training data into per-fighter composition scores
        aggregates: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {
                "count": 0.0,
                "pace_sum": 0.0,
                "boxing_sum": 0.0,
                "muay_thai_sum": 0.0,
                "wrestling_sum": 0.0,
                "grappling_sum": 0.0,
            }
        )

        with self._training_csv.open("r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                fighter_id = (row.get("fighter_id") or "").strip()
                if not fighter_id:
                    continue
                sig_str_per_min = self._float_or_zero(row.get("sig_str_per_min"))
                td_per_min = self._float_or_zero(row.get("td_per_min"))
                sig_str_accuracy = self._float_or_zero(row.get("sig_str_accuracy")) * 100.0
                td_success = self._float_or_zero(row.get("td_success")) * 100.0
                sub_att = self._float_or_zero(row.get("sub_att"))
                rev = self._float_or_zero(row.get("rev"))
                ctrl_pct = self._float_or_zero(row.get("ctrl_pct"))
                body_landed = self._float_or_zero(row.get("body_landed"))
                leg_landed = self._float_or_zero(row.get("leg_landed"))
                sig_str_landed = self._float_or_zero(row.get("sig_str_landed"))
                muay_thai_ratio = 0.0
                if sig_str_landed > 0:
                    muay_thai_ratio = ((body_landed + leg_landed) / sig_str_landed) * 100.0
                agg = aggregates[fighter_id]
                agg["count"] += 1.0
                agg["pace_sum"] += sig_str_per_min + td_per_min
                agg["boxing_sum"] += sig_str_accuracy
                agg["muay_thai_sum"] += muay_thai_ratio
                agg["wrestling_sum"] += td_success
                agg["grappling_sum"] += (sub_att * 10.0) + (rev * 10.0) + (ctrl_pct * 0.25)
        
        return {
            fighter_id: FighterComposition(
                pace      = agg["pace_sum"]       / max(agg["count"], 1.0),
                boxing    = agg["boxing_sum"]     / max(agg["count"], 1.0),
                muay_thai = agg["muay_thai_sum"]  / max(agg["count"], 1.0),
                wrestling = agg["wrestling_sum"]  / max(agg["count"], 1.0),
                grappling = agg["grappling_sum"]  / max(agg["count"], 1.0),
            )
            for fighter_id, agg in aggregates.items()
        }
    
    def calculateEV(odds_of_winning: float, betting_odds: float, unit: float = 100):
        # Calculate expected value for a bet given win probability and odds
        payoutMultiplier = 100 / betting_odds
        winningPayout = unit * payoutMultiplier
        odds_of_losing = 1 - odds_of_winning
        losingPayout = -1 * unit
        return odds_of_winning * winningPayout - odds_of_losing * losingPayout

    @staticmethod
    def _parse_event_date(value: str) -> Optional[date]:
        # Parse a human-readable event date string
        if not value:
            return None
        try:
            return datetime.strptime(value, "%B %d, %Y").date()
        except ValueError:
            return None

    @staticmethod
    def _nullable_str(value: Optional[str]) -> Optional[str]:
        # Strip a string or return None if empty
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _nullable_int(value: Optional[str]) -> Optional[int]:
        # Parse an int-like string or return None if empty/invalid
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            return None

    @staticmethod
    def _float_or_zero(value: Optional[str]) -> float:
        # Parse a float-like string, defaulting to 0.0
        if value is None:
            return 0.0
        cleaned = value.strip()
        if cleaned in {"", "---"}:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
