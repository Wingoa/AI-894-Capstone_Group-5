from __future__ import annotations
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

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
def homepage(request: Request) -> HTMLResponse:
    """
    Landing page — shows the Fighter Roster screen.
    Loads all fighters and upcoming events.
    No fighter comparison data is populated.
    """
    fighters    = service.getAllFighters()
    next_fights = service.getNextFightsWithEvents()
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":      request,
        "active_screen": "roster",
        # ── Roster (Fighter.name, Fighter.id, Fighter.fight_ids,
        #            Fighter.composition → derived fields)
        "fighters":     [_fighter_to_template(f) for f in fighters],
        # ── Events (EventInfo + Event joined)
        "next_fights":  [_event_to_template(info, event) for info, event in next_fights],
        "last_fights":  [_event_to_template(info, event) for info, event in last_fights],
        # ── Null out all comparison / simulation fields
        **_empty_comparison(),
    })

@app.get("/compare", response_class=HTMLResponse)
def compare(request: Request, red: str = "", blue: str = "") -> HTMLResponse:
    fighter_red  = service.getFighter(red)  if red  else None
    fighter_blue = service.getFighter(blue) if blue else None
    fighters     = service.getAllFighters()
    next_fights  = service.getNextFightsWithEvents()
    last_fights  = service.getLastFightsWithEvents()

    composition_red  = _composition_to_dict(fighter_red.composition  if fighter_red  else None)
    composition_blue = _composition_to_dict(fighter_blue.composition if fighter_blue else None)
    win_probability  = None
    hth_stats        = List[dict] = []
    matchup_stats    = dict   = {}
    
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
        "next_fights": [_event_to_template(i, e) for i, e in next_fights],
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
def matchup(request: Request) -> HTMLResponse:
    fighters    = service.getAllFighters()
    next_fights = service.getNextFightsWithEvents()
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":       request,
        "active_screen": "matchup",
        "fighters":      [_fighter_to_template(f) for f in fighters],
        "next_fights":   [_event_to_template(i, e) for i, e in next_fights],
        "last_fights":   [_event_to_template(i, e) for i, e in last_fights],
        "heatmap_data":  _build_heatmap_data(),
        "top_patterns":  _build_top_patterns(),
        **_empty_comparison(),
    })

@app.get("/events", response_class=HTMLResponse)
def events(request: Request) -> HTMLResponse:
    """
    Events screen.
    Shows all upcoming and past EventInfo rows joined with their parent Event.
    EventInfo fields used: winner_name, loser_name, weight_class, method,
                           round, time, fight_url
    Event fields used:     event_name, event_date, event_location, event_url
    """
    fighters    = service.getAllFighters()
    next_fights = service.getNextFightsWithEvents()
    last_fights = service.getLastFightsWithEvents()

    return templates.TemplateResponse(request, "index.html", {
        "request":       request,
        "active_screen": "events",
        "fighters":      [_fighter_to_template(f) for f in fighters],
        "next_fights":   [_event_to_template(i, e) for i, e in next_fights],
        "last_fights":   [_event_to_template(i, e) for i, e in last_fights],
        "heatmap_data":  _build_heatmap_data(),
        "top_patterns":  _build_top_patterns(),
        **_empty_comparison(),
    })

@app.get("/nextFights", response_model=List[EventInfo])
def getNextFights() -> List[EventInfo]:
    return service.getNextFights()

@app.get("/lastFights", response_model=List[EventInfo])
def getLastFights() -> List[EventInfo]:
    return service.getLastFights()

@app.get("/fighter/all", response_model=List[Fighter])
def getAllFighters() -> List[Fighter]:
    return service.getAllFighters()

@app.get("/fighter/{fighter_id}", response_model=Fighter)
def getFighter(fighter_id: str):
    fighter = service.getFighter(fighter_id)
    if not fighter:
        raise HTTPException(
            status_code=404,
            detail=f"No fighter found with id '{fighter_id}'"
        )
    return fighter

# Helpers
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
def _compute_win_probability(red: Fighter, blue: Fighter,) -> dict:
    """
    Compute win probability for the red corner vs blue corner.

    TODO: replace the stub return with your trained XGBoost / LightGBM call:

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
    return {
        "red_pct":    50,
        "blue_pct":   50,
        "auc":        "N/A",
        "confidence": "PENDING",
    }

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
# Placeholder values — replace with real aggregations over fights.csv
# once each fighter has a style label attached.
# ═════════════════════════════════════════════════════════════════════════════

def _build_heatmap_data() -> dict:
    """
    Style-vs-style win rate matrix.
    Rows and columns correspond to the 5 FighterComposition dimensions.

    TODO: replace static values with real win-rate aggregation:
        For each pair of style archetypes (derived from _derive_style_labels),
        count wins/total from fights.csv where red archetype = row,
        blue archetype = column.
    """
    return {
        "styles": ["Striker", "Muay Thai", "Wrestler", "Grappler", "Pace"],
        "data": [
            [50, 48, 27, 35, 52],
            [52, 50, 32, 44, 55],
            [73, 68, 50, 71, 62],
            [65, 56, 29, 50, 48],
            [48, 45, 38, 52, 50],
        ],
    }

def _build_top_patterns() -> List[dict]:
    """
    Top exploitable style matchup patterns.
    Each dict needs: label, win_rate (int), fight_count (int).

    TODO: derive from real data — aggregate wins by style pair,
    sort by win_rate descending, return top N.
    """
    return [
        {"label": "Wrestling vs Pure Striker",       "win_rate": 73, "fight_count": 112},
        {"label": "Muay Thai vs Pure Wrestler",      "win_rate": 68, "fight_count": 87},
        {"label": "Grappling vs High-Pace Fighter",  "win_rate": 65, "fight_count": 63},
    ]
