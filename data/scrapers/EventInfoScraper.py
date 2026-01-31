import re
import time
import random
from typing import Dict, List, Optional, Tuple, Any

import ScraperUtil
import requests
from bs4 import BeautifulSoup

EVENT_DETAILS_URL = "http://ufcstats.com/event-details/{event_id}"
FIGHT_DETAILS_PREFIX = "http://ufcstats.com/fight-details/"

FIGHT_ID_RE = re.compile(r"/fight-details/([a-zA-Z0-9]+)")

def scrapeEventInfo(event_id: str) -> List[Dict[str, str]]:
    session = ScraperUtil.make_session()
    fights = scrape_event_fights(session, event_id)

    print(f"Scraped {len(fights)} fights")
    return fights

def scrape_event_fights(session: requests.Session, event_id: str) -> List[Dict[str, str]]:
    """
    Scrape all fights from an event-details page.

    Per user requirement:
      - "first name listed is the fighter that won"
        -> We will treat the first fighter link in the row as the winner_name,
           second fighter link as loser_name.

    Returns list of dicts, one per fight.
    """
    url = EVENT_DETAILS_URL.format(event_id=event_id)
    print(url)

    # polite delay
    time.sleep(random.uniform(0.8, 1.8))

    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The fights table is typically: table.b-fight-details__table
    table = soup.select_one("table.b-fight-details__table")
    if not table:
        raise RuntimeError(f"Could not find fights table on event page: {url}")

    fights: List[Dict[str, str]] = []

    # Each fight is a row in tbody
    for tr in table.select("tbody tr"):
        # Fight row link is usually on the row (or in first cell) pointing to fight-details
        fight_link = tr.select_one("a[href*='fight-details']")
        fight_href = fight_link["href"].strip() if fight_link and fight_link.get("href") else ""
        fight_id = extract_fight_id(fight_href) or ""
        fight_url = f"{FIGHT_DETAILS_PREFIX}{fight_id}" if fight_id else fight_href

        # Fighters: typically two links to fighter-details inside the row
        fighter_links = tr.select("a[href*='fighter-details']")
        if len(fighter_links) < 2:
            # skip odd rows (rare)
            continue

        # Per your rule: first listed = winner
        winner_name = clean_text(fighter_links[0].get_text())
        loser_name = clean_text(fighter_links[1].get_text())

        # Weight class / method / round / time live in specific TD columns.
        # UFCStats markup sometimes shifts; safest approach is:
        # - grab all td text chunks and pick the ones we need by known classes if present,
        #   else by position fallback.
        tds = tr.find_all("td", recursive=False)

        # Preferred: pull by class selectors (more robust across column order changes)
        weight_class_el = tr.select_one("td.b-fight-details__table-col.l-page_align_left")
        # NOTE: That selector may match "weight_class" cell, but can also match others.
        # We'll do a safer approach: locate specific "weight_class" column by scanning td texts.

        td_texts = [clean_text(td.get_text(" ", strip=True)) for td in tds]

        # Heuristic fallback mapping (common UFCStats event table layout):
        # index: meaning
        # 0: (fight result icon / details link) - not reliable as text
        # 1: fighter 1 name (already captured)
        # 2: fighter 2 name (already captured)
        # 3: KD (or blank)
        # ...
        # Toward the end are: weight_class, method, round, time
        #
        # Because that can vary, we’ll use CSS classes where possible:
        weight_class = ""
        method = ""
        round_ended = ""
        time_ended = ""

        # UFCStats uses these classes often:
        # - weight_class: 'b-fight-details__fight-title' in the cell
        # - method: sometimes in 'p' tags with specific positioning
        # So we’ll grab them by “data ordering” in the row:
        # The last few <td> usually correspond to: weight_class, method, round, time.
        # We'll take them from the end if we have enough columns.
        if len(td_texts) >= 4:
            # Typical: [..., WEIGHT_CLASS, METHOD, ROUND, TIME]
            # We'll try extracting from the end.
            time_ended = td_texts[-1]
            round_ended = td_texts[-2]
            method = td_texts[-3]
            weight_class = td_texts[-4]

        fights.append({
            "event_id": event_id,
            "fight_id": fight_id,
            "winner_name": winner_name,
            "loser_name": loser_name,
            "weight_class": weight_class,
            "method": method,
            "round": round_ended,
            "time": time_ended,
            "fight_url": fight_url,
        })

    return fights

def extract_fight_id(href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    m = FIGHT_ID_RE.search(href)
    return m.group(1) if m else None


def clean_text(s: str) -> str:
    return " ".join((s or "").split())