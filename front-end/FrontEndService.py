from __future__ import annotations
# from collections import defaultdict
from datetime import date, datetime
import time
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
from execution.FighterUtil import POPULAR_FIGHTERS


class FrontEndService:
    def __init__(self) -> None:
        prediction_url = os.getenv("PREDICTION_SERVICE_URL", "").strip()
        execution_url = os.getenv("EXECUTION_SERVICE_URL", "").strip()
        data_url = os.getenv("DATA_SERVICE_URL", "").strip() or os.getenv("DATA_URL", "").strip()

        self._prediction_service_url = (prediction_url or data_url or "http://localhost:8002").rstrip("/")
        self._data_api_url = (data_url or prediction_url or execution_url or "http://localhost:8002").rstrip("/")
        self._execution_api_url = execution_url.rstrip("/")
        # Configurable backend timeout (seconds)
        try:
            self._timeout = float(os.getenv("FRONTEND_API_TIMEOUT", "30"))
        except Exception:
            self._timeout = 30.0
        try:
            self._retries = int(os.getenv("FRONTEND_API_RETRIES", "2"))
        except Exception:
            self._retries = 2
        # Debug info: print resolved backend URLs to help diagnose deployment env issues
        try:
            print(f"FrontEndService configured URLs: data_api={self._data_api_url}, prediction={self._prediction_service_url}, execution={self._execution_api_url}, timeout={self._timeout}s")
        except Exception:
            pass

    def _get_json(self, url: str, *, timeout: float = 10.0, params: Optional[dict] = None):
        resp = requests.get(url, timeout=timeout, params=params)
        resp.raise_for_status()
        return resp.json()

    def _try_get_json(self, urls: List[str], *, timeout: float = None, params: Optional[dict] = None):
        last_error: Optional[Exception] = None
        tried = []
        for url in urls:
            if not url:
                continue
            tried.append(url)
            attempt = 0
            while attempt <= self._retries:
                try:
                    use_timeout = (timeout if timeout is not None else self._timeout)
                    return self._get_json(url, timeout=use_timeout, params=params)
                except Exception as exc:
                    # Decide whether to retry: only retry for 5xx server errors
                    is_server_error = False
                    try:
                        import requests as _req
                        if isinstance(exc, _req.HTTPError) and getattr(exc, "response", None) is not None:
                            status = getattr(exc.response, "status_code", None)
                            if status is not None and 500 <= int(status) < 600:
                                is_server_error = True
                    except Exception:
                        pass

                    try:
                        print(f"FrontEndService GET failed for {url}: {exc} (attempt {attempt+1}/{self._retries+1})")
                    except Exception:
                        pass

                    last_error = exc
                    attempt += 1
                    if attempt <= self._retries and is_server_error:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        try:
                            time.sleep(backoff)
                        except Exception:
                            pass
                        continue
                    break
        # All attempts failed — log summary and return None so callers can handle missing backend gracefully
        try:
            print(f"FrontEndService: all attempts failed for urls: {tried}")
        except Exception:
            pass
        return None

    def getLastFights(self) -> List[EventInfo]:
        # Return completed fights (past events with fight_id present)
        try: 
            last_fights_data = self._try_get_json(
                [
                    f"{self._execution_api_url}/lastFights" if self._execution_api_url else "",
                    f"{self._data_api_url}/latest",
                ],
                timeout=self._timeout,
            )
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
        # Prefer event metadata from the data API (/latest) which includes event_name/event_date
        try:
            latest = self._try_get_json(
                [
                    f"{self._execution_api_url}/lastFights" if self._execution_api_url else "",
                    f"{self._data_api_url}/latest",
                ],
                timeout=self._timeout,
            )
            if latest:
                if isinstance(latest, dict):
                    latest = [latest]
                events_dict: Dict[str, Event] = {}
                for item in latest:
                    eid = item.get("event_id") or ""
                    if not eid:
                        continue
                    if eid not in events_dict:
                        events_dict[eid] = Event(
                            event_id=eid,
                            event_name=(item.get("event_name") or eid),
                            event_date=(item.get("event_date") or ""),
                            event_location=(item.get("event_location") or ""),
                            event_url=(item.get("event_url") or ""),
                        )
                return sorted(
                    events_dict.values(),
                    key=lambda e: self._parse_event_date(e.event_date) or date.min,
                    reverse=True,
                )
        except Exception:
            pass

        # Fallback: reconstruct Event objects from last_fights when API not available
        try:
            last_fights = self.getLastFights()
            events_dict: Dict[str, Event] = {}

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
            payload = self._try_get_json(
                [
                    f"{self._execution_api_url}/nextFights" if self._execution_api_url else "",
                    f"{self._data_api_url}/event/next",
                ],
                timeout=self._timeout,
            )
        except Exception:
            return None

        # If backend requests failed, _try_get_json returns None — handle gracefully
        if not payload:
            try:
                print(f"FrontEndService.getNextFights: payload is None for data_api={self._data_api_url}")
            except Exception:
                pass
            return None
            
        events_by_id = {e.event_id: e for e in self.getAllEvents()}
        # all_fighters = {fighter.name: fighter.id for fighter in self.getAllFighters()}
        event_payload = payload.get("event") or {}
        fights = payload.get("fights") or []
        if not fights:
            return None

        normalized: List[dict] = []
        for fight in fights:
            event_id = fight.get("event_id") or ""
            event = events_by_id.get(event_id) if event_id else None
            
            normalized.append({
                "event_name": (event.event_name if event else event_payload.get("event_name")) or fight.get("event_name") or event_id,
                "date": (event.event_date if event else event_payload.get("event_date")) or fight.get("date") or "—",
                "location": (event.event_location if event else event_payload.get("event_location")) or fight.get("location") or "—",
                "event_url": (event.event_url if event else event_payload.get("event_url")) or fight.get("event_url"),
                "red_fighter": fight.get("fighter_a") or "",
                "blue_fighter": fight.get("fighter_b") or "",
                "fighter_a_odds": fight.get("fighter_a_odds", -1),
                "fighter_b_odds": fight.get("fighter_b_odds", -1),
                "red_id": fight.get("fighter_a_id") or "",
                "blue_id": fight.get("fighter_b_id") or "",
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
            fighters_data = self._try_get_json(
                [
                    f"{self._execution_api_url}/fighter/all" if self._execution_api_url else "",
                    f"{self._data_api_url}/fighter",
                ],
                timeout=self._timeout,
            )
            if not fighters_data:
                return []
            fighters = []
            for f_data in fighters_data:
                if not isinstance(f_data, dict):
                    continue
                fighter_id = f_data.get("id") or f_data.get("fighter_id") or ""
                fighters.append(Fighter(
                    name=f_data.get("name") or "",
                    id=fighter_id,
                    composition=FighterComposition(
                        pace=0.0,
                        boxing=0.0,
                        muay_thai=0.0,
                        wrestling=0.0,
                        grappling=0.0,
                        stats={},
                    ),
                    fight_ids=f_data.get("fight_ids") or [],
                ))
            return sorted(fighters, key=lambda f: f.name)
        except Exception as e:
            print(f"getAllFighters error: {e}")
            return []

    def getMeta(self) -> dict:
        # Return dataset metadata from the data API /meta endpoint
        try:
            meta = self._try_get_json(
                [
                    f"{self._execution_api_url}/meta" if self._execution_api_url else "",
                    f"{self._data_api_url}/meta",
                ],
                timeout=self._timeout,
            )
            return meta or {}
        except Exception:
            return {}

    def getPopularFighters(self) -> List[Fighter]:
        try:
            if self._execution_api_url:
                fighters_data = self._get_json(f"{self._execution_api_url}/fighter/popular", timeout=10)
                if fighters_data:
                    fighters = []
                    for f_data in fighters_data:
                        if isinstance(f_data, dict):
                            comp_data = f_data.get("composition", {})
                            fighters.append(Fighter(
                                name=f_data.get("name", ""),
                                id=f_data.get("id", ""),
                                composition=FighterComposition(
                                    pace=float(comp_data.get("pace", 0.0)),
                                    boxing=float(comp_data.get("boxing", 0.0)),
                                    muay_thai=float(comp_data.get("muay_thai", 0.0)),
                                    wrestling=float(comp_data.get("wrestling", 0.0)),
                                    grappling=float(comp_data.get("grappling", 0.0)),
                                    stats=comp_data.get("stats", {}),
                                ),
                                fight_ids=f_data.get("fight_ids", [])
                            ))
                    return sorted(fighters, key=lambda fighter: fighter.name)

            # Derive popular fighters from the bulk /fighter endpoint (1 call)
            # instead of N individual getFighter() calls that each hit /fighter/{id} + /style/{id}
            all_fighters = self.getAllFighters()
            popular_ids = set(POPULAR_FIGHTERS.keys())
            fighters = [f for f in all_fighters if f.id in popular_ids]
            return sorted(fighters, key=lambda fighter: fighter.name)
        except Exception:
            return []

    def getFighter(self, fighter_id: str) -> Optional[Fighter]:
        try:
            f_data = self._try_get_json(
                [
                    f"{self._execution_api_url}/fighter/{fighter_id}" if self._execution_api_url else "",
                    f"{self._data_api_url}/fighter/{fighter_id}",
                ],
                timeout=self._timeout,
            )

            if isinstance(f_data, dict) and "composition" in f_data:
                comp_data = f_data.get("composition", {}) or {}
                return Fighter(
                    name=f_data.get("name", ""),
                    id=f_data.get("id", fighter_id),
                    composition=FighterComposition(
                        pace=float(comp_data.get("pace", 0.0)),
                        boxing=float(comp_data.get("boxing", 0.0)),
                        muay_thai=float(comp_data.get("muay_thai", 0.0)),
                        wrestling=float(comp_data.get("wrestling", 0.0)),
                        grappling=float(comp_data.get("grappling", 0.0)),
                        stats=comp_data.get("stats", {}),
                    ),
                    fight_ids=f_data.get("fight_ids", [])
                )

            fighter_style = self.getFighterStyle(fighter_id)
            return Fighter(
                name=f_data.get("name", "") or fighter_style.fighter,
                id=f_data.get("fighter_id", fighter_id),
                composition=FighterComposition(
                    pace=float(fighter_style.pace),
                    boxing=float(fighter_style.boxing),
                    muay_thai=float(fighter_style.muayThai),
                    wrestling=float(fighter_style.wrestling),
                    grappling=float(fighter_style.grappling),
                    stats=fighter_style.stats,
                ),
                fight_ids=f_data.get("fight_ids", [])
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
        data = self._get_json(f"{self._prediction_service_url}/style/{fighter_id}", timeout=30)
        return FighterStyle(
            data["fighter_id"],
            data["fighter"],
            float(data["muayThai"]),
            float(data["boxing"]),
            float(data["wrestling"]),
            float(data["grappling"]),
            float(data.get("pace", 0.0)),
            data.get("stats", {}) or {},
        )

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
