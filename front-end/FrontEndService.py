from __future__ import annotations
# from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
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
        # API URLs: Execution Service for upcoming fights, Prediction Service for fighter styles/predictions
        self._execution_api_url = os.getenv("EXECUTION_SERVICE_URL", "http://localhost:8002").rstrip("/")
        self._prediction_service_url = os.getenv("PREDICTION_SERVICE_URL", "http://localhost:8002").rstrip("/")

    def getLastFights(self) -> List[EventInfo]:
        # Return completed fights (past events with fight_id present)
        try: 
            resp = self._get_with_fallback(["/latest", "/lastFights"], timeout=10)
            if resp is None:
                return []
            
            # Parse JSON response into EventInfo objects
            last_fights_data = resp.json()
            if not last_fights_data:
                return []
            # Handle both list and dict responses
            if isinstance(last_fights_data, dict):
                last_fights_data = [last_fights_data]
            event_info_list = []
            for item in last_fights_data:
                event_info=EventInfo(
                    event_id=item.get("event_id", ""),
                    fight_id=item.get("fight_id"),
                    winner_name=item.get("winner_name", ""),
                    loser_name=item.get("loser_name", ""),
                    weight_class=item.get("weight_class", ""),
                    method=item.get("method"),
                    round=item.get("round"),
                    time=item.get("time"),
                    fight_url=item.get("fight_url"),  
                )
                event_info_list.append(event_info)
            return event_info_list
        except Exception:
            return []
    
    def getAllEvents(self) -> List[Event]:
        # Return all events
        try:
            last_fights = self.getLastFights()
            events_dict: Dict[str, Event] = {}
            
            # Reconstruct Event objects from EventInfo using event_id as the primary identifier
            for info in last_fights:
                if info.event_id not in events_dict:
                    events_dict[info.event_id] = Event(
                        event_id=info.event_id,
                        event_name=info.event_id,
                        event_date="",
                        event_location="",
                        event_url=""
                    )
            return sorted(
                events_dict.values(),
                key=lambda e: self._parse_event_date(e.event_date) or date.min,
                reverse=True,
            )
        except Exception:
            return []

    def getNextFights(self) -> Optional[List[dict]]:
        # Call the data API /event/next endpoint and normalize the response
        try:
            resp = self._get_with_fallback(["/event/next", "/nextFights"], timeout=2.5)
            if resp is None:
                return None
            payload = resp.json()
        except Exception:
            return None
        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        # Build name->id map supporting either dicts (from API) or Fighter objects
        all_fighters = {}
        for f in self.getAllFighters():
            try:
                if isinstance(f, dict):
                    name = f.get("name")
                    fid = f.get("id")
                else:
                    name = getattr(f, "name", None)
                    fid = getattr(f, "id", None)
                if name:
                    all_fighters[name] = fid or ""
            except Exception:
                continue
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
                "red_fighter": fight.get("fighter_a") or "",
                "blue_fighter": fight.get("fighter_b") or "",
                "fighter_a_odds": fight.get("fighter_a_odds", -1),
                "fighter_b_odds": fight.get("fighter_b_odds", -1),
                "red_id": all_fighters.get(fight.get("fighter_a"), ""),
                "blue_id": all_fighters.get(fight.get("fighter_b"), ""),
                "weight_class": fight.get("weight_class") or "",
                "method": fight.get("method"),
                "round": fight.get("round"),
                "time": fight.get("time"),
                "fight_url": fight.get("fight_url"),
            })
        return normalized

    def getLastFightsWithEvents(self) -> List[Tuple[EventInfo, Optional[Event]]]:
        # Return past fights paired with event metadata
        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        return [
            (info, events_by_id.get(info.event_id))
            for info in self.getLastFights()
        ]
    
    def getAllFighters(self) -> List[Fighter]:
        try:
            paths = ["/fighter", "/fighter/all"]
            print(f"FrontEndService: execution_url={self._execution_api_url}, trying paths={paths}")
            resp = self._get_with_fallback(paths, timeout=10)
            if resp is None:
                return []
            # Debug: log raw response text to diagnose empty payloads
            try:
                raw = resp.text
            except Exception:
                raw = "<no-text>"
            print(f"FrontEndService.getAllFighters: url={resp.url}, status={resp.status_code}, len={len(raw)}")
            try:
                fighters_data = resp.json()
                # Log structure details
                print(f"FrontEndService.getAllFighters: parsed type={type(fighters_data)}, count={len(fighters_data) if hasattr(fighters_data, '__len__') else 'n/a'}")
                if isinstance(fighters_data, (list, tuple)) and len(fighters_data) > 0:
                    sample = fighters_data[0]
                    print(f"FrontEndService.getAllFighters: sample_keys={list(sample.keys()) if isinstance(sample, dict) else type(sample)}")
            except Exception as e:
                import traceback
                print("FrontEndService.getAllFighters: JSON parse error:", e)
                traceback.print_exc()
                return []
            
            if not fighters_data:
                return []
            
            fighters = []
            for f_data in fighters_data:
                # Handle both Fighter objects and plain dicts
                if isinstance(f_data, dict):
                    comp_data = f_data.get("composition", {}) or {}
                    # Defensive per-item construction so one bad record doesn't abort everything
                    try:
                        fighters.append(Fighter(
                            name=f_data.get("name", ""),
                            id=f_data.get("id", ""),
                            composition=FighterComposition(
                                pace=float(comp_data.get("pace", 0.0)),
                                boxing=float(comp_data.get("boxing", 0.0)),
                                muay_thai=float(comp_data.get("muay_thai", 0.0)),
                                wrestling=float(comp_data.get("wrestling", 0.0)),
                                grappling=float(comp_data.get("grappling", 0.0)),
                                stats=comp_data.get("stats", {})
                            ),
                            fight_ids=f_data.get("fight_ids", [])
                        ))
                    except Exception:
                        # skip malformed entries
                        continue
            
            return sorted(fighters, key=lambda fighter: fighter.name)
        except Exception:
            return []

    def getFighter(self, fighter_id: str) -> Optional[Fighter]:
        try:
            resp = requests.get(f"{self._execution_api_url}/fighter/{fighter_id}", timeout=10)
            resp.raise_for_status()
            f_data = resp.json()
            # Support both `id` and legacy `fighter_id` keys from the data API
            fid = f_data.get("id") or f_data.get("fighter_id") or f_data.get("fighterId") or ""

            # Attempt to get fresh style from prediction service; if it fails, fall back to composition provided by
            # the execution service's aggregated roster (`/fighter`) which contains precomputed compositions.
            try:
                fighter_style = self.getFighterStyle(fighter_id)
                comp = FighterComposition(
                    pace=float(getattr(fighter_style, "pace", 0.0)),
                    boxing=float(getattr(fighter_style, "boxing", 0.0)),
                    muay_thai=float(getattr(fighter_style, "muayThai", 0.0)),
                    wrestling=float(getattr(fighter_style, "wrestling", 0.0)),
                    grappling=float(getattr(fighter_style, "grappling", 0.0)),
                    stats=getattr(fighter_style, "stats", {}) or {},
                )
            except Exception:
                # Fallback to roster composition if available
                comp = None
                try:
                    roster = self.getAllFighters()
                    for entry in roster:
                        try:
                            if isinstance(entry, dict) and entry.get("id") == fighter_id:
                                c = entry.get("composition", {}) or {}
                                comp = FighterComposition(
                                    pace=float(c.get("pace", 0.0)),
                                    boxing=float(c.get("boxing", 0.0)),
                                    muay_thai=float(c.get("muay_thai", 0.0)),
                                    wrestling=float(c.get("wrestling", 0.0)),
                                    grappling=float(c.get("grappling", 0.0)),
                                    stats=c.get("stats", {}) or {},
                                )
                                break
                        except Exception:
                            continue

                except Exception:
                    comp = FighterComposition(0.0, 0.0, 0.0, 0.0, 0.0, {})

            # If still missing, default to zeros
            if comp is None:
                comp = FighterComposition(0.0, 0.0, 0.0, 0.0, 0.0, {})

            return Fighter(
                name=f_data.get("name", ""),
                id=fid,
                composition=comp,
                fight_ids=f_data.get("fight_ids", []),
            )
        except Exception:
            return None

    def _get_with_fallback(self, paths: List[str], timeout: float) -> Optional[requests.Response]:
        for path in paths:
            try:
                resp = requests.get(f"{self._execution_api_url}{path}", timeout=timeout)
                if resp.status_code == 200:
                    return resp
            except Exception:
                continue
        return None

    def getFighterStyle(self, fighter_id: str) -> FighterStyle:
        # Query the Prediction Service for fighter style weights.
        resp = requests.get(f"{self._prediction_service_url}/style/{fighter_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Defensive handling: some responses may omit 'pace' or 'stats'. Provide safe defaults.
        try:
            muay = float(data.get("muayThai", 0.0))
        except Exception:
            muay = 0.0
        try:
            box = float(data.get("boxing", 0.0))
        except Exception:
            box = 0.0
        try:
            wrest = float(data.get("wrestling", 0.0))
        except Exception:
            wrest = 0.0
        try:
            grap = float(data.get("grappling", 0.0))
        except Exception:
            grap = 0.0
        try:
            pace = float(data.get("pace", 0.0))
        except Exception:
            pace = 0.0
        stats = data.get("stats", {}) or {}
        return FighterStyle(data.get("fighter_id", fighter_id), data.get("fighter", ""), muay, box, wrest, grap, pace, stats)

    def predictFight(self, fighter_a_id: str, fighter_b_id: str):
        # Query the Prediction Service for a fight outcome prediction.
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
    
    @staticmethod
    def _parse_event_date(value: str) -> Optional[date]:
        # Parse a human-readable event date string
        if not value:
            return None
        try:
            return datetime.strptime(value, "%B %d, %Y").date()
        except ValueError:
            return None
