"""Read the public, server-rendered Google Careers search results."""

import math
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser


BASE = "https://www.google.com/about/careers/applications/"
RESULTS = urllib.parse.urljoin(BASE, "jobs/results/")
COUNT = re.compile(r'<span class="SWhIm">([\d,]+)</span>\s+jobs matched')


class _Cards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.card = None
        self.li_depth = 0
        self.title = False
        self.company_depth = 0
        self.location_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "li" and "lLd3Je" in classes:
            self.card = {"id": (attrs.get("ssk") or "").split(":")[-1],
                         "title": "", "locations": [], "organization": "", "url": ""}
            self.li_depth = 1
            return
        if self.card is None:
            return
        if tag == "li":
            self.li_depth += 1
        elif tag == "h3" and "QJPWVe" in classes:
            self.title = True
        elif tag == "span":
            if self.company_depth:
                self.company_depth += 1
            elif "RP7SMd" in classes:
                self.company_depth = 1
            if self.location_depth:
                self.location_depth += 1
            elif "r0wTof" in classes:
                self.location_depth = 1
        elif tag == "a":
            href = attrs.get("href") or ""
            if href.startswith("jobs/results/") and not self.card["url"]:
                self.card["url"] = urllib.parse.urljoin(BASE, href.split("?")[0])

    def handle_data(self, data):
        if self.card is None:
            return
        if self.title:
            self.card["title"] += data
        if self.company_depth:
            self.card["organization"] += data
        if self.location_depth:
            location = data.strip(" ;")
            if location and location not in self.card["locations"]:
                self.card["locations"].append(location)

    def handle_endtag(self, tag):
        if self.card is None:
            return
        if tag == "h3":
            self.title = False
        elif tag == "span":
            self.company_depth = max(0, self.company_depth - 1)
            self.location_depth = max(0, self.location_depth - 1)
        elif tag == "li":
            self.li_depth -= 1
            if self.li_depth == 0:
                card = self.card
                card["title"] = card["title"].strip()
                card["location"] = "; ".join(card.pop("locations"))
                card["organization"] = card["organization"].replace("corporate_fare", "").strip()
                organization = re.match(r"^(Google|DeepMind|YouTube)", card["organization"])
                if organization:
                    card["organization"] = organization.group(1)
                if card["id"] and card["title"] and card["url"]:
                    self.cards.append(card)
                self.card = None


def parse_results(document):
    match = COUNT.search(document)
    if not match:
        raise ValueError("Google Careers result count missing")
    parser = _Cards()
    parser.feed(document)
    if not parser.cards:
        raise ValueError("Google Careers returned no readable job cards")
    return int(match.group(1).replace(",", "")), parser.cards


def fetch_google_careers(query="research scientist"):
    """Fetch all pages for one explicit query; failure never becomes a removal."""
    found = {}
    total = None
    page = 1
    while True:
        url = RESULTS + "?" + urllib.parse.urlencode({"q": query, "page": page})
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchLabRadar/1.0)", "Accept": "text/html"})
        with urllib.request.urlopen(request, timeout=30) as response:
            document = response.read().decode("utf-8", errors="replace")
        reported, cards = parse_results(document)
        if total is None:
            total = reported
            if total > 600:
                raise ValueError("Google Careers query is too broad for complete collection")
        if abs(reported - total) > 2:
            raise ValueError("Google Careers result count changed during pagination")
        for card in cards:
            found[card["id"]] = card
        if page >= math.ceil(total / 20):
            break
        page += 1
    if len(found) < total - 2:
        raise ValueError(f"Google Careers pagination incomplete: {len(found)}/{total}")
    return list(found.values()), RESULTS + "?" + urllib.parse.urlencode({"q": query})
