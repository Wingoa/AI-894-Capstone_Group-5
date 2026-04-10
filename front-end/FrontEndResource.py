from __future__ import annotations
from pathlib import Path
import math
import os
import csv
import sys
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
PREDICTION_SERVICE_URL = os.getenv("PREDICTION_SERVICE_URL", "http://localhost:8002").rstrip("/")

# Allow importing project modules when running from front-end directory; this way, we can reuse data models and services without needing to duplicate code or set up a separate package
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_model.Event import Event
from data_model.EventInfo import EventInfo
from data_model.Fighter import Fighter
from data_model.FighterComposition import FighterComposition
from data_model.FighterStyle import FighterStyle
from FrontEndService import FrontEndService

app = FastAPI(title="UFC Fighter Optimizer Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
service = FrontEndService()

_STYLE_MATCHUP_CACHE: Dict[str, object] = {
    "mtimes": None,
    "heatmap": None,
    "patterns": None,
}

@app.get("/", response_class=HTMLResponse)
def homepage(request: Request) -> HTMLResponse:
    # Render the landing page with the roster screen active
    fighters    = service.getAllFighters()
    next_fights = service.getNextFightsWithEvents()
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":      request,
        "active_screen": "roster",
        # ── Roster (Fighter.name, Fighter.id, Fighter.fight_ids,
        #            Fighter.composition → derived fields)
        "fighters":     [_fighter_to_template(f) for f in fighters],
        # ── Events (API payload normalized in FrontEndService)
        "next_fights":  next_fights,
        "last_fights":  [_event_to_template(info, event) for info, event in last_fights],
        # ── Null out all comparison / simulation fields
        **_empty_comparison(),
        "readme_md": _load_readme_md(),
    })

@app.get("/compare", response_class=HTMLResponse)
def compare(request: Request, red: str = "", blue: str = "") -> HTMLResponse:
    # Render the comparison screen for the selected fighters
    fighter_red  = service.getFighter(red)  if red  else None
    fighter_blue = service.getFighter(blue) if blue else None
    fighters     = service.getAllFighters()
    next_fights  = service.getNextFightsWithEvents()
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
        "readme_md": _load_readme_md(),
    })


@app.get("/matchup", response_class=HTMLResponse)
def matchup(request: Request) -> HTMLResponse:
    # Render the style matchup screen
    fighters    = service.getAllFighters()
    next_fights = service.getNextFightsWithEvents()
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
        "readme_md": _load_readme_md(),
    })

@app.get("/events", response_class=HTMLResponse)
def events(request: Request) -> HTMLResponse:
    # Render the events screen with upcoming and past fights
    fighters    = service.getAllFighters()
    next_fights = service.getNextFightsWithEvents()
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
        "readme_md": _load_readme_md(),
    })

@app.get("/nextFights")
def getNextFights() -> dict:
    # Return upcoming fights from the data service
    return service.getNextFights()

@app.get("/lastFights", response_model=List[EventInfo])
def getLastFights() -> List[EventInfo]:
    # Return completed fights from the data service
    return service.getLastFights()

@app.get("/fighter/all", response_model=List[Fighter])
def getAllFighters() -> List[Fighter]:
    # Return all fighters from the data service
    return service.getAllFighters()

@app.get("/fighter/{fighter_id}", response_model=Fighter)
def getFighter(fighter_id: str):
    # Return a single fighter by id or raise 404
    fighter = service.getFighter(fighter_id)
    if not fighter:
        raise HTTPException(
            status_code=404,
            detail=f"No fighter found with id '{fighter_id}'"
        )
    return fighter

@app.get("/fighter/style/{fighter_id}", response_model=FighterStyle)
def getFighterStyle(fighter_id: str) -> FighterStyle:
    # Return a fighter's style vector from the prediction service
    return service.getFighterStyle(fighter_id)

@app.get("/predict")
def predictFight(fighter_a_id: str, fighter_b_id: str):
    # Return outcome probabilities from the prediction service
    return service.predictFight(fighter_a_id, fighter_b_id)

# Helpers
def _fighter_to_template(fighter: Optional[Fighter]) -> Optional[dict]:
    # Convert a Fighter into a Jinja-friendly dict with derived fields
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

def _composition_to_dict(composition: Optional[FighterComposition]) -> Optional[dict]:
    # Normalize FighterComposition into a dict for charts and JSON
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

def _event_to_template(info: EventInfo, event: Optional[Event]=None,) -> dict:
    # Convert EventInfo (+ optional Event) into a UI-friendly dict
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
    
def _empty_comparison() -> dict:
    # Return empty/default values for comparison/simulation fields
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

def _derive_style_labels(c: FighterComposition,) -> Tuple[str, List[str], List[str]]:
    # Derive archetype and style labels from FighterComposition scores
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

def _exploitability_score(c: FighterComposition) -> int:
    # Estimate how one-dimensional a fighter is on a 0–99 scale
    scores = [c.boxing, c.muay_thai, c.wrestling, c.grappling, c.pace]
    max_val = max(scores, default=1.0) or 1.0
    avg_val = (sum(scores) / len(scores)) if scores else 1.0
    if avg_val == 0:
        return 0
    return min(99, int((max_val / avg_val) * 20))

# SIMULATION HELPERS
def _sim_defaults(fighter: Optional[Fighter]) -> dict:
    # Seed simulation sliders from a fighter's composition scores
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

# MATCHUP HELPERS
def _prob_confidence(prob: float) -> str:
    # Convert a probability into a simple confidence label
    edge = abs(prob - 0.5)
    if edge >= 0.20:
        return "HIGH"
    if edge >= 0.10:
        return "MEDIUM"
    return "LOW"

def _get_outcome_prediction(red_id: str, blue_id: str) -> Optional[dict]:
    # Fetch outcome probabilities from the prediction service
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

def _compute_win_probability(red: Fighter, blue: Fighter,) -> dict:
    # Compute win probability for red vs blue using the outcome service
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

def _build_hth_stats(red: Fighter, blue: Fighter) -> List[dict]:
    # Build head-to-head comparison rows from FighterComposition
    rc, bc = red.composition, blue.composition

    def norm(a: float, b: float) -> Tuple[int, int]:
        # Scale both values so max(a, b) = 100%
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

def _build_matchup_stats(red: Fighter, blue: Fighter) -> dict:
    # Build summary chip values from FighterComposition
    rc, bc = red.composition, blue.composition
    exploit = _exploitability_score(rc)
    return {
        "str_acc_diff":         round(rc.boxing - bc.boxing, 1),
        "td_success_rate":      round(rc.wrestling, 1),
        "sub_attempts":         round(rc.grappling / 10, 1),
        "exploitability_score": exploit,
        "exploitability_label": "High" if exploit > 50 else "Moderate",
    }

# HEATMAP / PATTERN DATA
def _build_heatmap_data() -> dict:
    # Return the style-vs-style win rate matrix
    heatmap, _ = _compute_style_matchups()
    return heatmap

def _build_top_patterns() -> List[dict]:
    # Return top exploitable style matchup patterns
    _, patterns = _compute_style_matchups()
    return patterns

def _compute_style_matchups() -> Tuple[dict, List[dict]]:
    # Compute style matchups and top patterns from fight data
    cache = _STYLE_MATCHUP_CACHE
    input_paths = [service._events_info_csv, service._fights_csv, service._training_csv]
    mtimes = tuple(p.stat().st_mtime if p.exists() else 0 for p in input_paths)
    if cache["mtimes"] == mtimes and cache["heatmap"] and cache["patterns"] is not None:
        return cache["heatmap"], cache["patterns"]

    style_keys = ["Striking", "Muay Thai", "Wrestling", "Grappling"]
    style_display = {
        "Striking": "Striker",
        "Muay Thai": "Muay Thai",
        "Wrestling": "Wrestler",
        "Grappling": "Grappler",
    }
    key_index = {k: i for i, k in enumerate(style_keys)}

    try:
        name_to_id = _load_fighter_name_map()
        style_by_id = _load_style_by_fighter_id()

        n = len(style_keys)
        wins = [[0 for _ in range(n)] for _ in range(n)]
        totals = [[0 for _ in range(n)] for _ in range(n)]
        seen_fights: set = set()

        with service._events_info_csv.open("r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                fight_id = (row.get("fight_id") or "").strip()
                if not fight_id or fight_id in seen_fights:
                    continue
                seen_fights.add(fight_id)
                winner_name = (row.get("winner_name") or "").strip()
                loser_name = (row.get("loser_name") or "").strip()
                if not winner_name or not loser_name:
                    continue
                winner_id = name_to_id.get(_norm_name(winner_name))
                loser_id = name_to_id.get(_norm_name(loser_name))
                if not winner_id or not loser_id:
                    continue
                winner_style = style_by_id.get(winner_id)
                loser_style = style_by_id.get(loser_id)
                if not winner_style or not loser_style:
                    continue
                wi = key_index[winner_style]
                li = key_index[loser_style]
                totals[wi][li] += 1
                totals[li][wi] += 1
                wins[wi][li] += 1

        data: List[List[int]] = []
        for i in range(n):
            row: List[int] = []
            for j in range(n):
                total = totals[i][j]
                if total == 0:
                    row.append(50)
                else:
                    row.append(round((wins[i][j] / total) * 100))
            data.append(row)

        patterns: List[dict] = []
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                total = totals[i][j]
                if total == 0:
                    continue
                win_rate = round((wins[i][j] / total) * 100)
                patterns.append({
                    "label": f"{style_display[style_keys[i]]} vs {style_display[style_keys[j]]}",
                    "win_rate": win_rate,
                    "fight_count": total,
                })

        patterns.sort(key=lambda p: (p["win_rate"], p["fight_count"]), reverse=True)
        top_patterns = patterns[:3]

        heatmap = {
            "styles": [style_display[k] for k in style_keys],
            "data": data,
        }

        cache["mtimes"] = mtimes
        cache["heatmap"] = heatmap
        cache["patterns"] = top_patterns
        return heatmap, top_patterns
    except Exception as e:
        print(f"Failed to compute style matchups: {e}")
        fallback_heatmap = {
            "styles": ["Striker", "Muay Thai", "Wrestler", "Grappler", "Pace"],
            "data": [
                [50, 50, 50, 50, 50],
                [50, 50, 50, 50, 50],
                [50, 50, 50, 50, 50],
                [50, 50, 50, 50, 50],
                [50, 50, 50, 50, 50],
            ],
        }
        return fallback_heatmap, []


def _load_readme_md() -> str:
    try:
        readme_path = PROJECT_ROOT / "README.md"
        if readme_path.exists():
            return readme_path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""

def _load_fighter_name_map() -> Dict[str, str]:
    # Build a name-to-fighter_id map from fights.csv
    counts: Dict[str, Dict[str, int]] = {}
    with service._fights_csv.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            fighter_id = (row.get("fighter_id") or "").strip()
            fighter_name = (row.get("fighter") or "").strip()
            if not fighter_id or not fighter_name:
                continue
            key = _norm_name(fighter_name)
            if key not in counts:
                counts[key] = {}
            counts[key][fighter_id] = counts[key].get(fighter_id, 0) + 1
    return {
        name: max(id_counts, key=id_counts.get)
        for name, id_counts in counts.items()
        if id_counts
    }

def _load_style_by_fighter_id() -> Dict[str, str]:
    # Map fighter_id to primary style derived from composition
    compositions = service._compute_fighter_compositions()
    return {
        fighter_id: _primary_style_key(comp)
        for fighter_id, comp in compositions.items()
        if comp is not None
    }

def _primary_style_key(c: FighterComposition) -> str:
    # Return the dominant style key for a composition
    scores: Dict[str, float] = {
        "Striking":  c.boxing,
        "Muay Thai": c.muay_thai,
        "Wrestling": c.wrestling,
        "Grappling": c.grappling,
        "Pace":      c.pace,
    }
    return max(scores, key=lambda k: scores[k])

def _norm_name(name: str) -> str:
    # Normalize a fighter name for matching
    return " ".join(name.strip().lower().split())
