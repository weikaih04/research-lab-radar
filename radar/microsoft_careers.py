"""Read Microsoft's public careers search with explicit query scope."""

import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache


BASE = "https://apply.careers.microsoft.com"
SEARCH = BASE + "/api/pcsx/search"


def _page(query, start):
    url = SEARCH + "?" + urllib.parse.urlencode({
        "domain": "microsoft.com", "query": query, "location": "", "start": start,
        "sort_by": "solr",
    })
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
               "Referer": BASE + "/careers"}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                result = json.load(response)
            if result.get("status") != 200 or not isinstance(result.get("data", {}).get("positions"), list):
                raise ValueError("Microsoft Careers returned an invalid search result")
            return result["data"]
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise
            time.sleep(65)


@lru_cache(maxsize=2)
def fetch_microsoft_careers(query="researcher"):
    found = {}
    count = None
    start = 0
    while True:
        data = _page(query, start)
        if count is None:
            count = data["count"]
            if not isinstance(count, int) or count < 1 or count > 200:
                raise ValueError("Microsoft Careers query is empty or too broad")
        if abs(data["count"] - count) > 2:
            raise ValueError("Microsoft Careers result count changed during pagination")
        positions = data["positions"]
        if not positions:
            raise ValueError("Microsoft Careers pagination ended before reported count")
        for raw in positions:
            timestamp = raw.get("postedTs")
            found[str(raw["id"])] = {
                "id": str(raw["id"]),
                "title": raw.get("name") or "",
                "location": "; ".join(raw.get("standardizedLocations") or raw.get("locations") or []),
                "url": urllib.parse.urljoin(BASE, raw.get("positionUrl") or ""),
                "published_at": dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat() if timestamp else None,
                "department": raw.get("department") or "",
            }
        start += len(positions)
        if start >= count:
            break
    if len(found) < count - 2:
        raise ValueError(f"Microsoft Careers pagination incomplete: {len(found)}/{count}")
    return list(found.values()), BASE + "/careers?" + urllib.parse.urlencode({"query": query})


def is_named_msr(job):
    return "microsoft research" in job["title"].lower()
