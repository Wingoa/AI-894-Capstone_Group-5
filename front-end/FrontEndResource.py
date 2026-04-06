from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import csv
import re
import unicodedata
import json
import math
import os
import urllib.request
import urllib.error
import urllib.parse
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
PREDICTION_SERVICE_URL = os.getenv("PREDICTION_SERVICE_URL", "http://localhost:8001").rstrip("/")

# Allow importing project modules when running from front-end directory; this way, we can reuse data models and services without needing to duplicate code or set up a separate package
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.Fighter import Fighter
from data_model.FighterComposition import FighterComposition
from FrontEndService import FrontEndService

app = FastAPI(title="UFC Fighter Optimizer Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
service = FrontEndService()

@app.get("/", response_class=HTMLResponse)
# Route: render the dashboard with roster default view.
def homepage(request: Request) -> HTMLResponse:
    """
    Landing page — shows the Fighter Roster screen.
    Loads all fighters and upcoming events.
    No fighter comparison data is populated.
    """
    fighters    = service.getAllFighters()
    next_fights = _build_next_fights_with_odds(service.getNextFightsWithEvents())
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":      request,
        "active_screen": "roster",
        # ── Roster (Fighter.name, Fighter.id, Fighter.fight_ids, Fighter.composition → derived fields)
        "fighters":     [_fighter_to_template(f) for f in fighters],
        # ── Events (EventInfo + Event joined)
        "next_fights":  next_fights,
        "last_fights":  [_event_to_template(info, event) for info, event in last_fights],
        # ── Null out all comparison / simulation fields
        **_empty_comparison(),
    })

@app.get("/compare", response_class=HTMLResponse)
# Route: render fighter comparison with selected fighters.
def compare(request: Request, red: str = "", blue: str = "") -> HTMLResponse:
    fighter_red  = service.getFighter(red)  if red  else None
    fighter_blue = service.getFighter(blue) if blue else None
    fighters     = service.getAllFighters()
    next_fights  = _build_next_fights_with_odds(service.getNextFightsWithEvents())
    last_fights  = service.getLastFightsWithEvents()

    composition_red  = _composition_to_dict(fighter_red.composition  if fighter_red  else None)
    composition_blue = _composition_to_dict(fighter_blue.composition if fighter_blue else None)
    win_probability  = None
    hth_stats: List[dict] = []
    matchup_stats: dict = {}
    
    if fighter_red and fighter_blue:
        win_probability = _compute_win_probability(fighter_red, fighter_blue)
        hth_stats       = _build_hth_stats(fighter_red, fighter_blue)
        matchup_stats   = _build_matchup_stats(fighter_red, fighter_blue)

    return templates.TemplateResponse(request, "index.html", {
        "request":      request,
        "active_screen": "comparison",
        # Fighter profile data (name, id, fight_ids, derived fields)
        "fighter_red":   _fighter_to_template(fighter_red)  if fighter_red  else None,
        "fighter_blue":  _fighter_to_template(fighter_blue) if fighter_blue else None,
        # Composition (FighterComposition normalised 0–1)
        # Keys: striking(=boxing), muay_thai, wrestling, grappling, pace
        "composition_red":  composition_red,
        "composition_blue": composition_blue,
        # Matchup outputs
        "win_probability": win_probability,
        "hth_stats":       hth_stats,
        "matchup_stats":   matchup_stats,
        # Simulation sliders seeded from FighterComposition
        "sim_defaults":    _sim_defaults(fighter_red),
        # Roster
        "fighters": [_fighter_to_template(f) for f in fighters],
        # Events
        "next_fights": next_fights,
        "last_fights":  [_event_to_template(i, e) for i, e in last_fights],
        # Model outputs (empty until model is connected)
        "shap_features": [],
        "sim_narrative": None,
        "sim_outcome":   None,
        "coaching_recs": [],
        # Style matchup screen data
        "heatmap_data":  _build_heatmap_data(),
        "top_patterns":  _build_top_patterns(),
    })

@app.get("/matchup", response_class=HTMLResponse)
# Route: render style matchup screen.
def matchup(request: Request) -> HTMLResponse:
    fighters    = service.getAllFighters()
    next_fights = _build_next_fights_with_odds(service.getNextFightsWithEvents())
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":       request,
        "active_screen": "matchup",
        "fighters":      [_fighter_to_template(f) for f in fighters],
        "next_fights":   next_fights,
        "last_fights":   [_event_to_template(i, e) for i, e in last_fights],
        "heatmap_data":  _build_heatmap_data(),
        "top_patterns":  _build_top_patterns(),
        **_empty_comparison(),
    })

@app.get("/events", response_class=HTMLResponse)
# Route: render events screen.
def events(request: Request) -> HTMLResponse:
    """
    Events screen.
    Shows all upcoming and past EventInfo rows joined with their parent Event.
    EventInfo fields used: winner_name, loser_name, weight_class, method,
                           round, time, fight_url
    Event fields used:     event_name, event_date, event_location, event_url
    """
    fighters    = service.getAllFighters()
    next_fights = _build_next_fights_with_odds(service.getNextFightsWithEvents())
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":       request,
        "active_screen": "events",
        "fighters":      [_fighter_to_template(f) for f in fighters],
        "next_fights":   next_fights,
        "last_fights":   [_event_to_template(i, e) for i, e in last_fights],
        "heatmap_data":  _build_heatmap_data(),
        "top_patterns":  _build_top_patterns(),
        **_empty_comparison(),
    })

@app.get("/nextFights", response_model=List[EventInfo])
# API: return upcoming fights list.
def getNextFights() -> List[EventInfo]:
    return service.getNextFights()

@app.get("/lastFights", response_model=List[EventInfo])
# API: return past fights list.
def getLastFights() -> List[EventInfo]:
    return service.getLastFights()

@app.get("/fighter/all", response_model=List[Fighter])
# API: return all fighters.
def getAllFighters() -> List[Fighter]:
    return service.getAllFighters()

@app.get("/fighter/{fighter_id}", response_model=Fighter)
# API: return fighter by id.
def getFighter(fighter_id: str):
    fighter = service.getFighter(fighter_id)
    if not fighter:
        raise HTTPException(
            status_code=404,
            detail=f"No fighter found with id '{fighter_id}'"
        )
    return fighter

# Helpers
# Helper: convert Fighter to template dict.
def _fighter_to_template(fighter: Optional[Fighter]) -> Optional[dict]:
    """
    Convert Fighter dataclass → plain dict for Jinja.
    Derives archetype and primary_styles from FighterComposition since
    Fighter has no division/country/archetype fields yet.
    """
    if fighter is None:
        return None

    archetype, primary_styles, secondary_styles = _derive_style_labels(
        fighter.composition
    )

    return {
        # Fighter dataclass fields
        "id":        fighter.id,
        "name":      fighter.name,
        "fight_ids": fighter.fight_ids,           # List[str] — length used as record proxy
        # Derived from FighterComposition
        "archetype":          archetype,
        "primary_styles":     primary_styles,
        "secondary_styles":   secondary_styles,
        "exploitability_score": _exploitability_score(fighter.composition),
        "primary_style":      archetype,          # used for data-style filter attribute
    }


# Helper: normalize composition for UI charts.
def _composition_to_dict(composition: Optional[FighterComposition]) -> Optional[dict]:
    """
    Convert FighterComposition to plain dict for Jinja/tojson.
    Map 'boxing' to 'striking' to match the UI label.
    All values normalized for the radar chart.
    """
    if composition is None:
        return None
    max_val = max(
        composition.pace,
        composition.boxing,
        composition.muay_thai,
        composition.wrestling,
        composition.grappling,
        1.0   # floor to avoid division by zero
    )
    return {
        "striking":  round(composition.boxing     / max_val, 3),
        "muay_thai": round(composition.muay_thai  / max_val, 3),
        "wrestling": round(composition.wrestling  / max_val, 3),
        "grappling": round(composition.grappling  / max_val, 3),
        "pace":      round(composition.pace       / max_val, 3),
    }


# Helper: map event info into UI-friendly dict.
def _event_to_template(info: EventInfo, event: Optional[Event]=None,) -> dict:
    """
    Convert EventInfo to plain dict for Jinja.
    EventInfo uses winner_name/loser_name — mapped to red/blue for the UI.
    fight_id is used as red_id so the Analyze button links to /compare?red=...
    (swap for actual fighter IDs once EventInfo carries them).
    """
    return {
        # Event-level fields — fall back to event_id if Event not joined
        "event_name": event.event_name     if event else info.event_id,
        "date":       event.event_date     if event else "—",
        "location":   event.event_location if event else "—",
        "event_url":  event.event_url      if event else None,
        # Fight-level fields from EventInfo
        "red_fighter":  info.winner_name,
        "blue_fighter": info.loser_name,
        "red_id":       info.fight_id or "",   # fight_id used as nav key for now
        "blue_id":      "",                    # EventInfo has no blue fighter_id yet
        "weight_class": info.weight_class,
        "method":       info.method   or "—",
        "round":        info.round,            # Optional[int]
        "time":         info.time     or "—",
        "fight_url":    info.fight_url or None,
    }

# Helper: enrich upcoming fights with odds/EV.
def _build_next_fights_with_odds(
    next_fights: List[Tuple[EventInfo, Optional[Event]]],
) -> List[dict]:
    """
    Enrich upcoming fights with Kalshi odds and model-based EV.
    """
    market_map = service.getKalshiMarketMap()
    enriched: List[dict] = []
    for info, event in next_fights:
        fight = _event_to_template(info, event)
        red_name = fight["red_fighter"]
        blue_name = fight["blue_fighter"]

        red_id = service.getFighterIdByName(red_name)
        blue_id = service.getFighterIdByName(blue_name)
        if red_id:
            fight["red_id"] = red_id
        if blue_id:
            fight["blue_id"] = blue_id

        red_market = service.getKalshiMarketForFighter(red_name, market_map)
        blue_market = service.getKalshiMarketForFighter(blue_name, market_map)
        red_odds = red_market.get("odds") if red_market else None
        blue_odds = blue_market.get("odds") if blue_market else None
        fight["red_odds"] = red_odds
        fight["blue_odds"] = blue_odds

        market_date = None
        if red_market and red_market.get("fight_date"):
            market_date = red_market.get("fight_date")
        elif blue_market and blue_market.get("fight_date"):
            market_date = blue_market.get("fight_date")
        if market_date:
            original_date = fight.get("date")
            try:
                market_dt = datetime.fromisoformat(str(market_date)).date()
                fight["date"] = market_dt.strftime("%B %d, %Y")
                try:
                    event_dt = datetime.strptime(str(original_date or ""), "%B %d, %Y").date()
                except ValueError:
                    event_dt = None
                if event_dt and event_dt != market_dt:
                    fight["location"] = "TBD"
            except ValueError:
                fight["date"] = str(market_date)

        outcome = None
        if red_id and blue_id:
            outcome = _get_outcome_prediction(red_id, blue_id)

        red_ev = None
        blue_ev = None
        if outcome:
            red_prob = outcome.get("prob_red")
            blue_prob = outcome.get("prob_blue")
            if red_prob is not None and red_odds not in (None, 0):
                red_ev = FrontEndService.calculateEV(float(red_prob), float(red_odds))
            if blue_prob is not None and blue_odds not in (None, 0):
                blue_ev = FrontEndService.calculateEV(float(blue_prob), float(blue_odds))

        fight["red_ev"] = round(red_ev, 2) if red_ev is not None else None
        fight["blue_ev"] = round(blue_ev, 2) if blue_ev is not None else None
        enriched.append(fight)
    return enriched
    
# Helper: blank comparison payload for non-compare screens.
def _empty_comparison() -> dict:
    """
    Return null values for all comparison / simulation template variables.
    Used by routes that don't show the comparison screen.
    """
    return {
        "fighter_red":      None,
        "fighter_blue":     None,
        "composition_red":  None,
        "composition_blue": None,
        "win_probability":  None,
        "hth_stats":        [],
        "matchup_stats":    {},
        "sim_defaults":     _sim_defaults(None),
        "shap_features":    [],
        "sim_narrative":    None,
        "sim_outcome":      None,
        "coaching_recs":    [],
    }

# Helper: derive archetype and style tags.
def _derive_style_labels(c: FighterComposition,) -> Tuple[str, List[str], List[str]]:
    """
    Derive human-readable style labels from raw FighterComposition scores.

    FighterComposition fields used: boxing, muay_thai, wrestling, grappling, pace

    Returns:
        archetype       — single label for the dominant dimension
        primary_styles  — dimensions scoring >= 70% of the max
        secondary_styles— dimensions scoring >= 40% but < 70% of the max
    """
    scores: Dict[str, float] = {
        "Striking":  c.boxing,
        "Muay Thai": c.muay_thai,
        "Wrestling": c.wrestling,
        "Grappling": c.grappling,
        "Pace":      c.pace,
    }
    max_val   = max(scores.values(), default=1.0) or 1.0
    top_key   = max(scores, key=lambda k: scores[k])

    primary   = [k for k, v in scores.items() if v >= max_val * 0.70]
    secondary = [k for k, v in scores.items()
                 if max_val * 0.40 <= v < max_val * 0.70]

    archetype_map = {
        "Striking":  "Pressure Striker",
        "Muay Thai": "Muay Thai Specialist",
        "Wrestling": "Dominant Wrestler",
        "Grappling": "Submission Hunter",
        "Pace":      "High-Pace Fighter",
    }
    return archetype_map.get(top_key, top_key), primary, secondary

# Helper: estimate exploitability from composition.
def _exploitability_score(c: FighterComposition) -> int:
    """
    Estimate how one-dimensional / exploitable a fighter is (0–99).

    Uses FighterComposition fields: boxing, muay_thai, wrestling, grappling, pace.

    Logic: a fighter who is extremely dominant in one dimension and weak in
    others is more exploitable (higher score) than a well-rounded fighter.
    Ratio of max-dimension to average-across-all drives the score.

    TODO: replace with your model's exploitability output once available.
    """
    scores = [c.boxing, c.muay_thai, c.wrestling, c.grappling, c.pace]
    max_val = max(scores, default=1.0) or 1.0
    avg_val = (sum(scores) / len(scores)) if scores else 1.0
    if avg_val == 0:
        return 0
    return min(99, int((max_val / avg_val) * 20))


# ═════════════════════════════════════════════════════════════════════════════
# SIMULATION HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def _sim_defaults(fighter: Optional[Fighter]) -> dict:
    """
    Seed the simulation sliders from a fighter's real FighterComposition values.

    Mapping (raw score → slider range):
        td     ← wrestling  / 10   (slider range 1–12)
        str    ← boxing     / 10   (slider range 1–10)
        pace   ← pace       / 10   (slider range 1–10)
        clinch ← muay_thai  / 10   (slider range 1–10)
        def    ← 5.0 fixed         (no defensive stat in FighterComposition yet)

    Division by 10 is a rough normalisation since composition scores are raw
    averages (e.g. boxing ≈ sig_str_accuracy × 100 ≈ 0–100).
    Revisit these divisors once you normalise your NMF output.
    """
    if fighter is None or fighter.composition is None:
        return {"td": 5.0, "str": 4.0, "pace": 5.0, "def": 5.0, "clinch": 4.0}

    c = fighter.composition
    return {
        "td":     round(min(12.0, max(1.0, c.wrestling  / 10)), 1),
        "str":    round(min(10.0, max(1.0, c.boxing     / 10)), 1),
        "pace":   round(min(10.0, max(1.0, c.pace       / 10)), 1),
        "clinch": round(min(10.0, max(1.0, c.muay_thai  / 10)), 1),
        "def":    5.0,
    }


# ═════════════════════════════════════════════════════════════════════════════
# MATCHUP HELPERS
# ═════════════════════════════════════════════════════════════════════════════

# Helper: map probability to confidence label.
def _prob_confidence(prob: float) -> str:
    """
    Convert model probability into a simple confidence label.
    """
    edge = abs(prob - 0.5)
    if edge >= 0.20:
        return "HIGH"
    if edge >= 0.10:
        return "MEDIUM"
    return "LOW"

# Helper: call prediction service for win odds.
def _get_outcome_prediction(red_id: str, blue_id: str) -> Optional[dict]:
    """
    Call the PredictionService /outcome endpoint for win probabilities.
    Returns dict with prob_red/prob_blue or None on failure.
    """
    if not red_id or not blue_id:
        return None
    try:
        import requests

        url = f"{PREDICTION_SERVICE_URL}/outcome"
        params = {"fighter_a_id": red_id, "fighter_b_id": blue_id}
        # Increase timeout to allow for model loading/latency in deployed envs
        resp = requests.get(url, params=params, timeout=5.0)
        if resp.status_code != 200:
            print(f"Prediction call failed: {resp.status_code} {resp.text}")
            return None
        data = resp.json()
        prob_red = float(data.get("fighter_a_prob", 0.0))
        prob_blue = float(data.get("fighter_b_prob", 0.0))
        if math.isnan(prob_red) or math.isnan(prob_blue):
            print("Prediction returned NaN probabilities")
            return None
        return {"prob_red": prob_red, "prob_blue": prob_blue}
    except Exception as e:
        print(f"Exception calling prediction service: {e}")
        return None


# Helper: compute win probabilities for a matchup.
def _compute_win_probability(red: Fighter, blue: Fighter,) -> dict:
    """
    Compute win probability for the red fighter vs blue fighter.

        features = build_feature_vector(red.composition, blue.composition)
        prob_red = model.predict_proba([features])[0][1]
        return {
            "red_pct":    round(prob_red * 100),
            "blue_pct":   round((1 - prob_red) * 100),
            "auc":        "0.74",
            "confidence": "HIGH",
        }

    FighterComposition fields available for feature engineering:
        red.composition.pace, boxing, muay_thai, wrestling, grappling
        blue.composition.pace, boxing, muay_thai, wrestling, grappling
    """
    outcome = _get_outcome_prediction(red.id, blue.id)
    if outcome:
        prob_red = max(0.0, min(1.0, outcome["prob_red"]))
        red_pct = max(1, min(99, round(prob_red * 100)))
        return {
            "red_pct":    red_pct,
            "blue_pct":   100 - red_pct,
            "auc":        "OutcomeNet32",
            "confidence": _prob_confidence(prob_red),
            "model":      "Outcome Model",
        }

    return {
        "red_pct":    50,
        "blue_pct":   50,
        "auc":        "N/A",
        "confidence": "PENDING",
        "model":      "Model Pending",
    }

# Helper: build head-to-head stats rows.
def _build_hth_stats(red: Fighter, blue: Fighter) -> List[dict]:
    """
    Build head-to-head stat rows for the comparison screen.

    Each row needs: label, red (display value), blue (display value),
                    red_pct (0–100 bar width), blue_pct (0–100 bar width).

    All values come directly from FighterComposition:
        pace, boxing (→ Striking), muay_thai, wrestling, grappling

    red_pct / blue_pct normalise each metric so the larger of the two = 100%,
    giving proportional bar widths rather than raw values.
    """
    rc, bc = red.composition, blue.composition

    def norm(a: float, b: float) -> Tuple[int, int]:
        """Scale both values so max(a, b) = 100%."""
        m = max(a, b, 0.001)
        return round(a / m * 100), round(b / m * 100)

    rows = []
    for label, r_val, b_val in [
        ("Pace Score",      rc.pace,      bc.pace),
        ("Striking (Boxing)", rc.boxing,  bc.boxing),
        ("Muay Thai Ratio", rc.muay_thai, bc.muay_thai),
        ("Wrestling TD %",  rc.wrestling, bc.wrestling),
        ("Grappling Score", rc.grappling, bc.grappling),
    ]:
        r_pct, b_pct = norm(r_val, b_val)
        rows.append({
            "label":    label,
            "red":      round(r_val, 1),
            "blue":     round(b_val, 1),
            "red_pct":  r_pct,
            "blue_pct": b_pct,
        })
    return rows

# Helper: build matchup summary chips.
def _build_matchup_stats(red: Fighter, blue: Fighter) -> dict:
    """
    Build summary chip data for the comparison screen.
    All values derived from FighterComposition.

    str_acc_diff        ← red.boxing  - blue.boxing
    td_success_rate     ← red.wrestling  (red corner's raw wrestling score)
    sub_attempts        ← red.grappling / 10  (scaled estimate)
    exploitability_score← _exploitability_score(red.composition)
    exploitability_label← "High" / "Moderate" based on score
    """
    rc, bc = red.composition, blue.composition
    exploit = _exploitability_score(rc)
    return {
        "str_acc_diff":         round(rc.boxing - bc.boxing, 1),
        "td_success_rate":      round(rc.wrestling, 1),
        "sub_attempts":         round(rc.grappling / 10, 1),
        "exploitability_score": exploit,
        "exploitability_label": "High" if exploit > 50 else "Moderate",
    }

# ═════════════════════════════════════════════════════════════════════════════
# HEATMAP / PATTERN DATA
# ═════════════════════════════════════════════════════════════════════════════

STYLE_BUCKETS = ["Striker", "Muay Thai", "Wrestler", "Grappler"]

# Helper: normalize names for matching.
def _normalize_name(value: str) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if ch.isalnum() or ch.isspace())
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text

# Helper: pick dominant style bucket.
def _style_bucket_from_composition(comp: FighterComposition) -> str:
    scores = {
        "Striker":  comp.boxing,
        "Muay Thai": comp.muay_thai,
        "Wrestler": comp.wrestling,
        "Grappler": comp.grappling,
    }
    return max(scores, key=scores.get)

@lru_cache(maxsize=1)
# Cache: map fighter_id to style bucket.
def _fighter_style_bucket_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for fighter in service.getAllFighters():
        if fighter and fighter.composition:
            mapping[fighter.id] = _style_bucket_from_composition(fighter.composition)
    return mapping

@lru_cache(maxsize=1)
# Cache: map (fight_id,name) to fighter_id.
def _fight_id_name_to_fighter_id() -> Tuple[Dict[Tuple[str, str], str], Dict[str, str]]:
    mapping: Dict[Tuple[str, str], str] = {}
    name_only: Dict[str, str] = {}
    fights_csv = PROJECT_ROOT / "resources" / "initial_data" / "fights.csv"
    if not fights_csv.exists():
        return mapping, name_only
    with fights_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fight_id = (row.get("fight_id") or "").strip()
            fighter_id = (row.get("fighter_id") or "").strip()
            fighter_name = (row.get("fighter") or "").strip()
            if not fighter_id or not fighter_name:
                continue
            norm_name = _normalize_name(fighter_name)
            if fight_id:
                mapping[(fight_id, norm_name)] = fighter_id
            if norm_name and norm_name not in name_only:
                name_only[norm_name] = fighter_id
    return mapping, name_only

# Helper: resolve fighter_id from fight+name.
def _lookup_fighter_id(fight_id: str, fighter_name: str) -> Optional[str]:
    mapping, name_only = _fight_id_name_to_fighter_id()
    norm = _normalize_name(fighter_name)
    if fight_id and (fight_id, norm) in mapping:
        return mapping[(fight_id, norm)]
    return name_only.get(norm)

# Helper: aggregate style-vs-style results.
def _compute_style_matchups() -> Tuple[List[str], List[List[float]], List[List[int]]]:
    styles = STYLE_BUCKETS
    idx = {style: i for i, style in enumerate(styles)}
    wins = [[0.0 for _ in styles] for _ in styles]
    total = [[0 for _ in styles] for _ in styles]

    style_map = _fighter_style_bucket_map()
    info_csv = PROJECT_ROOT / "resources" / "initial_data" / "events-info.csv"
    if not info_csv.exists():
        return styles, wins, total

    with info_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fight_id = (row.get("fight_id") or "").strip()
            winner = (row.get("winner_name") or "").strip()
            loser = (row.get("loser_name") or "").strip()
            if not winner or not loser:
                continue
            winner_id = _lookup_fighter_id(fight_id, winner)
            loser_id = _lookup_fighter_id(fight_id, loser)
            if not winner_id or not loser_id:
                continue
            winner_style = style_map.get(winner_id)
            loser_style = style_map.get(loser_id)
            if not winner_style or not loser_style:
                continue
            i = idx[winner_style]
            j = idx[loser_style]
            if i == j:
                total[i][j] += 1
                wins[i][j] += 0.5
            else:
                total[i][j] += 1
                total[j][i] += 1
                wins[i][j] += 1

    return styles, wins, total

# Helper: build heatmap matrix for UI.
def _build_heatmap_data() -> dict:
    """
    Style-vs-style win rate matrix.
    Rows and columns correspond to the 4 FighterComposition dimensions.
    """
    styles, wins, total = _compute_style_matchups()
    data: List[List[int]] = []
    for r in range(len(styles)):
        row: List[int] = []
        for c in range(len(styles)):
            if total[r][c] > 0:
                row.append(round((wins[r][c] / total[r][c]) * 100))
            else:
                row.append(50)
        data.append(row)
    return {
        "styles": styles,
        "data": data,
    }

# Helper: build top matchup patterns.
def _build_top_patterns() -> List[dict]:
    """
    Top exploitable style matchup patterns.
    Each dict has label, win_rate (int), fight_count (int).
    Sorted by win_rate descending, returns top 3.
    """
    styles, wins, total = _compute_style_matchups()
    patterns: List[dict] = []
    min_fights = 10
    for i, row_style in enumerate(styles):
        for j, col_style in enumerate(styles):
            if i == j:
                continue
            fight_count = total[i][j]
            if fight_count < min_fights:
                continue
            win_rate = round((wins[i][j] / fight_count) * 100)
            patterns.append({
                "label": f"{row_style} vs {col_style}",
                "win_rate": win_rate,
                "fight_count": fight_count,
            })
    patterns.sort(key=lambda p: p["win_rate"], reverse=True)
    return patterns[:3]
