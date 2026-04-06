from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
import csv
import re
import unicodedata

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.Fighter import Fighter
from data_model.FighterComposition import FighterComposition
from data.clients.KalshiClient import KalshiClient


class FrontEndService:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        self._events_csv = project_root / "resources" / "initial_data" / "events.csv"
        self._events_info_csv = project_root / "resources" / "initial_data" / "events-info.csv"
        self._fights_csv = project_root / "resources" / "initial_data" / "fights.csv"
        self._training_csv = project_root / "resources" / "clean_data" / "training_data.csv"
        self._kalshi_client = KalshiClient()
        self._fighter_id_by_name: Optional[Dict[str, str]] = None

    def getNextFights(self) -> List[EventInfo]:
        events_by_id = self._load_event_dates()
        upcoming_ids = {
            event_id
            for event_id, event_date in events_by_id.items()
            if event_date >= date.today()
        }
        # Some rows may not have full fight data yet so they are treated as upcoming
        rows = self._load_event_info_rows()
        upcoming = []
        for row in rows:
            if row.event_id in upcoming_ids or not row.fight_id:
                upcoming.append(row)
        return upcoming

    def getLastFights(self) -> List[EventInfo]:
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

    def getEventById(self, event_id: str) -> Optional[Event]:
        for event in self.getAllEvents():
            if event.event_id == event_id:
                return event
        return None

    def getNextFightsWithEvents(self) -> List[Tuple[EventInfo, Optional[Event]]]:
        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        return [
            (info, events_by_id.get(info.event_id))
            for info in self.getNextFights()
        ]

    def getLastFightsWithEvents(self) -> List[Tuple[EventInfo, Optional[Event]]]:
        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        return [
            (info, events_by_id.get(info.event_id))
            for info in self.getLastFights()
        ]

    def loadEventInfo(self, event_id: str) -> Optional[EventInfo]:
        for row in self._load_event_info_rows():
            if row.event_id == event_id:
                return row
        return None

    def loadEventInfoRows(self) -> List[EventInfo]:
        return self._load_event_info_rows()
    
    def getAllFighters(self) -> List[Fighter]:
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
        for fighter in self.getAllFighters():
            if fighter.id == fighter_id:
                return fighter
        return None

    def reloadData(self) -> None:
        return

    def _load_event_dates(self) -> Dict[str, date]:
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
    
    @staticmethod
    def calculateEV(odds_of_winning: float, betting_odds: float, unit: float = 100):
        if betting_odds is None or betting_odds == 0:
            return None
        payoutMultiplier = 100 / betting_odds
        winningPayout = unit * payoutMultiplier
        odds_of_losing = 1 - odds_of_winning
        losingPayout = -1 * unit
        return odds_of_winning * winningPayout - odds_of_losing * losingPayout

    def getKalshiMarketMap(self) -> Dict[str, dict]:
        try:
            markets = self._kalshi_client.getLatest()
        except Exception:
            return {}
        market_map: Dict[str, dict] = {}
        for market in markets:
            fighter = (market.get("fighter") or "").strip()
            odds = market.get("yes_money")
            fight_date = market.get("fight_date")
            if not fighter or odds is None:
                continue
            key = self._normalize_name(fighter)
            if not key:
                continue
            if key not in market_map:
                market_map[key] = {
                    "odds": float(odds),
                    "fight_date": fight_date,
                }
        return market_map

    def getKalshiMarketForFighter(self, fighter_name: str, market_map: Dict[str, dict]) -> Optional[dict]:
        if not fighter_name:
            return None
        key = self._normalize_name(fighter_name)
        if key in market_map:
            return market_map[key]
        last_name = key.split(" ")[-1]
        for name, market in market_map.items():
            if last_name and (name == last_name or name.endswith(f" {last_name}")):
                return market
        return None

    @staticmethod
    def _normalize_name(value: str) -> str:
        if not value:
            return ""
        text = unicodedata.normalize("NFKD", value)
        text = "".join(ch for ch in text if ch.isalnum() or ch.isspace())
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text

    def getFighterIdByName(self, fighter_name: str) -> Optional[str]:
        if not fighter_name:
            return None
        if self._fighter_id_by_name is None:
            mapping: Dict[str, str] = {}
            with self._fights_csv.open("r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = (row.get("fighter") or "").strip()
                    fighter_id = (row.get("fighter_id") or "").strip()
                    if name and fighter_id and name.lower() not in mapping:
                        mapping[name.lower()] = fighter_id
            self._fighter_id_by_name = mapping
        key = fighter_name.strip().lower()
        if key in self._fighter_id_by_name:
            return self._fighter_id_by_name[key]
        last_name = key.split(" ")[-1]
        for name, fighter_id in self._fighter_id_by_name.items():
            if last_name and last_name in name:
                return fighter_id
        return None

    @staticmethod
    def _parse_event_date(value: str) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%B %d, %Y").date()
        except ValueError:
            return None

    @staticmethod
    def _nullable_str(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _nullable_int(value: Optional[str]) -> Optional[int]:
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
        if value is None:
            return 0.0
        cleaned = value.strip()
        if cleaned in {"", "---"}:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
