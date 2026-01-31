import csv
import re
import time
import random
import data.scrapers.ScraperUtil as ScraperUtil
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup

COMPLETED_EVENTS_URL = "http://ufcstats.com/statistics/events/completed?page=all"
EVENT_DETAILS_PREFIX = "http://ufcstats.com/event-details/"

EVENT_ID_RE = re.compile(r"/event-details/([a-zA-Z0-9]+)$")

def extract_event_id(href: str) -> Optional[str]:
    """
    href is expected like:
      http://ufcstats.com/event-details/<event_id>
    or sometimes relative links (rare).
    """
    if not href:
        return None

    # Normalize to absolute-ish form for matching
    href = href.strip()

    # Match either absolute or relative
    m = re.search(r"/event-details/([a-zA-Z0-9]+)$", href)
    if m:
        return m.group(1)

    # Try if absolute URL has query params (unlikely, but safe)
    if "event-details/" in href:
        tail = href.split("event-details/", 1)[1]
        tail = tail.split("?", 1)[0].split("#", 1)[0]
        return tail or None

    return None

def extract_event_id(href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    m = re.search(r"/event-details/([a-zA-Z0-9]+)", href)
    return m.group(1) if m else None

def scrape_completed_events(session: requests.Session) -> List[Dict[str, str]]:
    # Polite delay (even for one request)
    time.sleep(random.uniform(0.8, 1.8))

    resp = session.get(COMPLETED_EVENTS_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.select_one("table.b-statistics__table-events")
    if not table:
        raise RuntimeError("Could not find events table. Site layout may have changed.")

    events: List[Dict[str, str]] = []

    # Each row in tbody corresponds to one event
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td", recursive=False)
        # Some rows might be empty or separators; require at least 2 tds
        if len(tds) < 2:
            continue

        # TD[0]: contains link + name + date span
        td0 = tds[0]
        a = td0.select_one("a[href*='event-details']")
        date_span = td0.select_one("span.b-statistics__date")

        if not a:
            continue

        href = a.get("href", "").strip()
        event_id = extract_event_id(href) or ""

        # Clean text for name (anchor text includes whitespace/newlines)
        event_name = " ".join(a.get_text(strip=True).split())

        # Date is in the span; if missing, fallback to empty string
        event_date = ""
        if date_span:
            event_date = " ".join(date_span.get_text(strip=True).split())

        # TD[1]: location text
        td1 = tds[1]
        event_location = " ".join(td1.get_text(strip=True).split())

        event_url = f"{EVENT_DETAILS_PREFIX}{event_id}" if event_id else href

        events.append({
            "event_id": event_id,
            "event_name": event_name,
            "event_date": event_date,
            "event_location": event_location,
            "event_url": event_url,
        })

    return events

def scrapeEvents() -> List[Dict]:
    events: List[Dict]
    try:
        session = ScraperUtil.make_session()
        events = scrape_completed_events(session)
    except Exception as e:
        print(f"Could not scrape events page, encountered an exception {e}")

    print(f"Scraped {len(events)} events.")
    if events:
        print("Example row:", events[0])

    return events

def reloadEventIds() -> List[str]:
    events = scrapeEvents()
    return [d["event_id"] for d in events if "event_id" in d]
