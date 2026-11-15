#!/usr/bin/env python3
"""Discover application-announcement leads for OPENPATH. Never approves or publishes leads."""
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

# Search for announcements, not broad discussion about opportunities.
SEARCHES = [
    ("Scholarship", 'Ghana scholarship "applications open" OR "call for applications"'),
    ("Scholarship", 'Ghana students scholarship "apply now" OR "application deadline"'),
    ("International scholarship", 'Ghanaian students scholarship "applications open"'),
    ("International scholarship", 'Commonwealth Shared Scholarship "apply" 2027'),
    ("International scholarship", 'Erasmus Mundus scholarship "applications" 2027'),
    ("International scholarship", 'DAAD Ghana scholarship "application" 2027'),
    ("International scholarship", 'Fulbright Ghana "application" student 2027'),
    ("Internship", 'Ghana internship "applications open" OR "apply now"'),
    ("Job", 'Ghana graduate trainee "apply now" OR "applications open"'),
    ("Job", 'Ghana entry level vacancy "application deadline"'),
    ("Free course", 'free online course "enrol now" OR "registration open" certificate'),
]

POSITIVE = re.compile(
    r"\b(applications? (?:are )?open|call for applications|apply now|now accepting applications|"
    r"accepting applications|application deadline|applications close|apply by|register now|"
    r"registration open|enrol now|enroll now|submit applications)\b", re.I
)
NEGATIVE = re.compile(
    r"\b(guide|explained|what you need to know|how to apply|eligibility and|"
    r"crisis|opinion|editorial|analysis|top \d+|\d+ opportunities|list of|"
    r"best scholarships|scholarship tips|everything you need)\b", re.I
)
GENERIC_PUBLISHERS = {
    "google news", "news source", "yahoo", "msn", "pulse", "graphic online",
    "citinewsroom", "bbc", "cnn", "the guardian", "ghanaweb", "modern ghana",
}


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def load_existing():
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Could not safely read {DATA_FILE.name}: {exc}") from exc


def resolve_article_url(url):
    """Try to follow the Google News redirect; fall back to its RSS URL."""
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 OPENPATH-opportunity-discovery/2.0"}
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            final_url = response.geturl()
        if urllib.parse.urlparse(final_url).scheme in {"http", "https"}:
            return final_url
    except Exception:
        pass
    return url


def looks_like_application_announcement(title):
    if not POSITIVE.search(title):
        return False
    if NEGATIVE.search(title):
        return False
    return True


def fetch_feed(category, query):
    params = urllib.parse.urlencode({"q": query, "hl": "en-GH", "gl": "GH", "ceid": "GH:en"})
    feed_url = "https://news.google.com/rss/search?" + params
    request = urllib.request.Request(
        feed_url, headers={"User-Agent": "OPENPATH-opportunity-discovery/2.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            root = ET.fromstring(response.read())
    except Exception as exc:
        print(f"Feed failed for {query!r}: {exc}")
        return []

    leads = []
    for item in root.findall(".//item")[:15]:
        title = clean(item.findtext("title"))
        rss_link = clean(item.findtext("link"))
        published = clean(item.findtext("pubDate"))
        source_node = item.find("source")
        publisher = clean(source_node.text if source_node is not None else "Unknown publisher")
        publisher_url = clean(source_node.get("url", "")) if source_node is not None else ""

        if not title or not rss_link or not looks_like_application_announcement(title):
            continue

        article_url = resolve_article_url(rss_link)
        leads.append({
            "type": category,
            "title": title,
            "org": "Verify from official provider",
            "where": "Ghana / International — eligibility not yet verified",
            "detail": (
                "UNVERIFIED DISCOVERY LEAD. A headline matched application-announcement terms. "
                "Confirm the opportunity on the provider's official website, including eligibility, "
                "requirements, funding, deadline and direct application link before approval."
            ),
            "deadline": "Not verified — check official provider",
            "url": article_url,
            "source_url": article_url,
            "source_publisher": publisher,
            "publisher_url": publisher_url,
            "source_published": published,
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "review_note": "Headline filter only; publisher is not assumed to be the opportunity provider.",
            "status": "pending",
        })
    return leads


def main():
    existing = load_existing()
    seen = {clean(x.get("source_url") or x.get("url")) for x in existing if isinstance(x, dict)}
    added = 0
    for category, query in SEARCHES:
        for lead in fetch_feed(category, query):
            key = clean(lead["source_url"])
            if key in seen:
                continue
            existing.append(lead)
            seen.add(key)
            added += 1
        time.sleep(1)

    DATA_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OPENPATH discovery complete: {added} new filtered pending leads; {len(existing)} total records.")
    print("All new leads remain pending. Headline filtering is not verification; manually check official providers before approval.")


if __name__ == "__main__":
    main()
