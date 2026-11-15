#!/usr/bin/env python3
"""Discover possible OPENPATH application leads. Never verifies or approves them."""
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "opportunities.json"

# Google News is used only to discover leads. Every lead must be checked manually.
SEARCHES = [
    ("Scholarship", 'Ghana scholarship ("applications open" OR "call for applications" OR "apply now")'),
    ("Scholarship", 'Ghana students scholarship ("application deadline" OR "now accepting applications")'),
    ("International scholarship", 'Ghanaian students international scholarship ("applications open" OR "apply now")'),
    ("International scholarship", 'Commonwealth scholarship 2027 ("applications open" OR "apply now")'),
    ("International scholarship", 'Erasmus Mundus 2027 scholarship ("applications open" OR "apply now")'),
    ("International scholarship", 'DAAD scholarship Ghana ("applications open" OR "apply now")'),
    ("International scholarship", 'Fulbright Ghana scholarship ("applications open" OR "apply now")'),
    ("Internship", 'Ghana internship ("applications open" OR "apply now" OR "apply by")'),
    ("Job", 'Ghana graduate trainee ("applications open" OR "apply now" OR "apply by")'),
    ("Job", 'Ghana entry level jobs ("applications open" OR "apply now" OR "application deadline")'),
    ("Free course", 'free online course ("enrol now" OR "enroll now" OR "registration open") certificate'),
]

ACTION = re.compile(
    r"\b(?:applications?\s+(?:are\s+)?open|call\s+for\s+applications?|"
    r"apply\s+now|now\s+accepting\s+applications?|accepting\s+applications?|"
    r"application\s+deadline|applications?\s+close|apply\s+by|register\s+now|"
    r"registration\s+open|enrol\s+now|enroll\s+now|submit\s+applications?)\b", re.I
)

# Reject titles that are clearly explanatory, retrospective, or list-style.
REJECT = re.compile(
    r"\b(?:guide|explained|what\s+you\s+need\s+to\s+know|how\s+to\s+apply|"
    r"eligibility\s+and|opinion|editorial|analysis|review|recap|"
    r"top\s+\d+|\d+\s+(?:best\s+)?opportunities|list\s+of|"
    r"best\s+scholarships|scholarship\s+tips|everything\s+you\s+need|"
    r"what\s+is|all\s+you\s+need\s+to\s+know)\b", re.I
)

# A matching action phrase alone is not enough; the headline must also match its category.
CATEGORY_TERMS = {
    "Scholarship": re.compile(r"\b(scholarship|scholarships|bursary|bursaries|grant|grants)\b", re.I),
    "International scholarship": re.compile(r"\b(scholarship|scholarships|fellowship|fellowships|bursary|grant)\b", re.I),
    "Internship": re.compile(r"\b(internship|internships|intern|interns)\b", re.I),
    "Job": re.compile(r"\b(job|jobs|vacanc(?:y|ies)|graduate trainee|trainee programme|recruitment|hiring)\b", re.I),
    "Free course": re.compile(r"\b(course|courses|training|certificate|certification|enrol|enroll)\b", re.I),
}


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def load_existing():
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise RuntimeError("opportunities.json must contain a JSON list.")
        return data
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Could not safely read {DATA_FILE.name}: {exc}") from exc


def resolve_article_url(url):
    """Try to resolve a Google News redirect; otherwise retain its RSS URL."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OPENPATH/3.0"})
        with urllib.request.urlopen(request, timeout=12) as response:
            final_url = response.geturl()
        if urllib.parse.urlparse(final_url).scheme in {"http", "https"}:
            return final_url
    except Exception:
        pass
    return url


def is_relevant_lead(category, title):
    title = clean(title)
    if not title or not ACTION.search(title) or REJECT.search(title):
        return False
    category_pattern = CATEGORY_TERMS.get(category)
    return bool(category_pattern and category_pattern.search(title))


def fetch_feed(category, query):
    params = urllib.parse.urlencode({"q": query, "hl": "en-GH", "gl": "GH", "ceid": "GH:en"})
    feed_url = "https://news.google.com/rss/search?" + params
    request = urllib.request.Request(feed_url, headers={"User-Agent": "OPENPATH-discovery/3.0"})
