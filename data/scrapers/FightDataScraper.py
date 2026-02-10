import re
import time
import random
from scrapers.ScraperUtil import make_session, get_html
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

# ----------------------------
# Constants
# ----------------------------
FIGHT_DETAILS_URL = "http://ufcstats.com/fight-details/{fight_id}"
FIGHTER_ID_RE = re.compile(r"/fighter-details/([a-zA-Z0-9]+)")


# ----------------------------
# Reusable helpers (same style as earlier parts of your project)
# ----------------------------
def clean_text(s: str) -> str:
    return " ".join((s or "").split())

def fighter_id_from_href(href: str) -> str:
    m = FIGHTER_ID_RE.search(href or "")
    return m.group(1) if m else ""

def two_vals_from_td(td) -> Tuple[str, str]:
    """
    UFCStats totals tables store both fighters in the same <td>, as two <p> blocks:
      first <p> = fighter A
      second <p> = fighter B
    """
    ps = td.select("p.b-fight-details__table-text")
    vals = [clean_text(p.get_text(" ", strip=True)) for p in ps]
    if len(vals) >= 2:
        return vals[0], vals[1]
    if len(vals) == 1:
        return vals[0], ""
    return "", ""

def find_table_by_headers(soup: BeautifulSoup, must_have: List[str]):
    """
    Find the first <table> whose <thead> contains all strings in must_have.
    This targets the TOP-LEVEL totals tables (not the per-round 'js-fight-table' tables).
    """
    for table in soup.find_all("table"):
        thead = table.find("thead")
        if not thead:
            continue
        header_text = clean_text(thead.get_text(" ", strip=True)).lower()
        if all(x.lower() in header_text for x in must_have):
            return table
    return None


# ----------------------------
# Fetch + parse
# ----------------------------
def scrape_fight_totals_by_id(session: requests.Session, fight_id: str) -> List[Dict]:
    """
    Fetch http://ufcstats.com/fight-details/{fight_id} and return 2 rows (1 per fighter)
    with the columns you want:

    Fighter, KD, Sig. str., Sig. str. %, Total str., Td, Td %, Sub. att, Rev., Ctrl,
    Head, Body, Leg, Distance, Clinch, Ground

    Also includes: fighter_id
    """
    url = FIGHT_DETAILS_URL.format(fight_id=fight_id)

    # polite delay
    time.sleep(random.uniform(0.8, 1.8))

    resp = get_html(session, url)
    if resp == None:
        print(f"Could not return html after multiple attempts for url {url}")
        return []
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) Totals (overall) table
    totals_table = find_table_by_headers(
        soup,
        must_have=["Fighter", "KD", "Sig. str.", "Total str.", "Td", "Ctrl"]
    )
    if not totals_table:
        raise RuntimeError(f"Could not find Totals table on {url}")

    # 2) Significant strikes breakdown totals table
    sig_table = find_table_by_headers(
        soup,
        must_have=["Fighter", "Head", "Body", "Leg", "Distance", "Clinch", "Ground"]
    )
    if not sig_table:
        raise RuntimeError(f"Could not find Significant Strikes totals table on {url}")

    # ---- Extract fighter names + ids from the Totals table fighter cell ----
    totals_row = totals_table.select_one("tbody tr")
    if not totals_row:
        raise RuntimeError(f"Totals table missing tbody row on {url}")

    totals_tds = totals_row.find_all("td", recursive=False)
    fighter_td = totals_tds[0]

    fighter_links = fighter_td.select("a[href*='fighter-details']")
    if len(fighter_links) < 2:
        raise RuntimeError(f"Could not find two fighter links in Totals table on {url}")

    f1_name = clean_text(fighter_links[0].get_text(strip=True))
    f2_name = clean_text(fighter_links[1].get_text(strip=True))
    f1_id = fighter_id_from_href(fighter_links[0].get("href", ""))
    f2_id = fighter_id_from_href(fighter_links[1].get("href", ""))

    rows = [
        {"fight_id": fight_id, "fighter_id": f1_id, "fighter": f1_name},
        {"fight_id": fight_id, "fighter_id": f2_id, "fighter": f2_name},
    ]

    # Totals table column order (matches UFCStats HTML structure shown):
    # Fighter | KD | Sig Str | Sig Str % | Total Str | Td | Td % | Sub Att | Rev | Ctrl
    totals_cols = {
        "kd": 1,
        "sig_str": 2,
        "sig_str_pct": 3,
        "total_str": 4,
        "td": 5,
        "td_pct": 6,
        "sub_att": 7,
        "rev": 8,
        "ctrl": 9,
    }

    for key, idx in totals_cols.items():
        v1, v2 = two_vals_from_td(totals_tds[idx])
        rows[0][key] = v1
        rows[1][key] = v2

    # Sig strikes totals table column order:
    # Fighter | Sig Str | Sig Str % | Head | Body | Leg | Distance | Clinch | Ground
    sig_row = sig_table.select_one("tbody tr")
    if not sig_row:
        raise RuntimeError(f"Sig strikes table missing tbody row on {url}")

    sig_tds = sig_row.find_all("td", recursive=False)
    sig_cols = {
        "head": 3,
        "body": 4,
        "leg": 5,
        "distance": 6,
        "clinch": 7,
        "ground": 8,
    }

    for key, idx in sig_cols.items():
        v1, v2 = two_vals_from_td(sig_tds[idx])
        rows[0][key] = v1
        rows[1][key] = v2

    return rows

def scrapeFight(fight_id: str) -> List[Dict]:
    try:
        session = make_session()
        fights = scrape_fight_totals_by_id(session, fight_id)
        return fights
    except Exception as e:
        print(f"Encountered exception when trying to scrape {fight_id}. Ignoring fight entry: {e}")
        return []
