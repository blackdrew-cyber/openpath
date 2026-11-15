#!/usr/bin/env python3
"""Discover opportunity leads from Google News RSS. Leads are never auto-approved."""
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

SEARCHES = [
    ("Scholarship", "Ghana scholarships applications students"),
    ("International scholarship", 'fully funded international scholarships Ghanaian students'),
    ("International scholarship", 'Commonwealth Shared Scholarships Ghana'),
    ("International scholarship", 'Erasmus Mundus scholarships applications'),
    ("International scholarship", 'DAAD scholarships Ghana students'),
    ("International scholarship", 'Fulbright Ghana student scholarship'),
    ("International scholarship", 'Stipendium Hungaricum Ghana applications'),
    ("International scholarship", 'Türkiye Scholarships Ghana applications'),
    ("International scholarship", 'Australia Awards Ghana scholarship'),
    ("Internship", 'Ghana internships students applications'),
    ("Job", 'Ghana entry level jobs graduate trainee vacancies'),
    ("Free course", 'free online courses certificates applications'),
]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load_existing():
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def fetch_feed(category, query):
    params = urllib.parse.urlencode({"q": query, "hl": "en-GH", "gl": "GH", "ceid": "GH:en"})
    url = "https://news.google.com/rss/search?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "OPENPATH-opportunity-discovery/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
    except Exception as exc:
        print(f"Feed failed for {query!r}: {exc}")
        return []

    items = []
    for item in root.findall(".//item")[:12]:
        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        pubdate = clean(item.findtext("pubDate"))
        source_node = item.find("source")
        publisher = clean(source_node.text if source_node is not None else "News source")
        if not title or not link:
            continue
        items.append({
            "type": category,
            "title": title,
            "org": publisher,
            "where": "Ghana / International — verify eligibility",
            "detail": "DISCOVERY LEAD ONLY. Check the original provider's official website for Ghana eligibility, requirements, funding, deadline and application link before approving.",
            "deadline": "Verify on official provider website",
            "url": link,
            "source_url": link,
            "source_publisher": publisher,
            "source_published": pubdate,
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "pending"
        })
    return items


def main():
    existing = load_existing()
    seen = {clean(x.get("source_url") or x.get("url")) for x in existing}
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
    print(f"OPENPATH discovery complete: {added} new pending leads; {len(existing)} total records.")
    print("IMPORTANT: all discoveries remain pending and are not visible on the public site until manually verified and approved.")


if __name__ == "__main__":
    main()
