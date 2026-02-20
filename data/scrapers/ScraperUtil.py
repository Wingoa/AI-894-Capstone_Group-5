import requests
import time

def make_session() -> requests.Session:
    s = requests.Session()
    # Headers to look like a normal browser (helps avoid intermittent 502s)
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "http://ufcstats.com/",
    })
    return s

def get_html(session: requests.Session, url: str, timeout: int = 30):
    resp = None
    attempts = 0
    while resp == None and attempts < 3:
        try:
            resp = session.get(url, timeout=timeout)
        except Exception as e:
            print(f"Attempted to get html for {url}, but encountered an exception: {e}")
            print(f"Trying again in 10 seconds")
            time.sleep(10)
            attempts = attempts + 1
    return resp
            

