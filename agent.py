"""Geopolitical risk agent.

Pulls headlines from news RSS feeds, asks Claude to classify each one by
country, risk category and severity, and stores the results in SQLite.

Usage:
    python agent.py            # fetch live feeds and classify (needs ANTHROPIC_API_KEY)
    python agent.py --demo     # load synthetic sample data, no internet or key needed
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          TEXT PRIMARY KEY,   -- hash of the link, used to skip duplicates
    source      TEXT,
    title       TEXT,
    summary     TEXT,
    link        TEXT,
    published   TEXT,
    fetched_at  TEXT,
    country     TEXT,
    region      TEXT,
    category    TEXT,
    severity    INTEGER,            -- 0 = not geopolitical, 1 = minor ... 5 = critical
    reason      TEXT,
    demo        INTEGER DEFAULT 0   -- 1 for synthetic sample rows
);
"""

PROMPT = """You are a geopolitical risk analyst. Classify the news item below.

Categories (pick exactly one key):
{categories}

Severity scale:
0 = not geopolitical
1 = minor / routine
2 = notable, limited impact
3 = significant, regional implications
4 = serious, could escalate or affect multiple countries
5 = critical, major escalation or global impact

Return ONLY a JSON object, no other text:
{{"country": "<main country involved, or 'Multiple' or 'Global'>",
  "region": "<one of: Europe, Middle East, Africa, Asia-Pacific, Americas, Russia & Central Asia, Global>",
  "category": "<category key>",
  "severity": <0-5>,
  "reason": "<one short sentence explaining the rating>"}}

Source: {source}
Headline: {title}
Summary: {summary}"""


def connect():
    db = sqlite3.connect(config.DB_PATH)
    db.execute(SCHEMA)
    return db


def article_id(link):
    return hashlib.sha256(link.encode()).hexdigest()[:16]


def fetch_feeds():
    import feedparser

    items = []
    for source, url in config.FEEDS.items():
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"  ! could not read {source}: {feed.bozo_exception}")
            continue
        for e in feed.entries[: config.MAX_PER_FEED]:
            items.append({
                "source": source,
                "title": e.get("title", "").strip(),
                "summary": _strip_html(e.get("summary", ""))[:500],
                "link": e.get("link", ""),
                "published": e.get("published", ""),
            })
        print(f"  {source}: {min(len(feed.entries), config.MAX_PER_FEED)} items")
    return items


def _strip_html(text):
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


def classify(client, item):
    categories = "\n".join(f"- {k}: {v}" for k, v in config.CATEGORIES.items())
    msg = client.messages.create(
        model=config.MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": PROMPT.format(categories=categories, **item)}],
    )
    text = msg.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}")
    result = json.loads(text[start : end + 1])
    if result.get("category") not in config.CATEGORIES:
        result["category"] = "not_geopolitical"
    result["severity"] = max(0, min(5, int(result.get("severity", 0))))
    return result


def run_live():
    from dotenv import load_dotenv
    import anthropic

    load_dotenv()
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    db = connect()
    db.execute("DELETE FROM articles WHERE demo = 1")  # clear any demo rows

    print("Fetching feeds...")
    items = fetch_feeds()
    new = [i for i in items if i["link"] and not db.execute(
        "SELECT 1 FROM articles WHERE id = ?", (article_id(i["link"]),)).fetchone()]
    print(f"{len(new)} new articles to classify")

    now = datetime.now(timezone.utc).isoformat()
    for n, item in enumerate(new, 1):
        try:
            r = classify(client, item)
        except Exception as e:  # keep going if one item fails
            print(f"  ! skipped '{item['title'][:60]}': {e}")
            continue
        db.execute(
            "INSERT OR IGNORE INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (article_id(item["link"]), item["source"], item["title"], item["summary"],
             item["link"], item["published"], now, r.get("country"), r.get("region"),
             r["category"], r["severity"], r.get("reason")),
        )
        print(f"  [{n}/{len(new)}] {r['severity']} {r['category']:<22} {item['title'][:60]}")
        db.commit()
    db.close()


def run_demo():
    """Load synthetic sample rows so you can see the dashboard without a key."""
    from demo_data import SAMPLES

    db = connect()
    db.execute("DELETE FROM articles WHERE demo = 1")
    today = datetime.now(timezone.utc)
    for i, (days_ago, source, title, country, region, cat, sev) in enumerate(SAMPLES):
        ts = (today - timedelta(days=days_ago)).isoformat()
        db.execute(
            "INSERT OR REPLACE INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (f"demo{i}", source, title, "", "", ts, ts, country, region, cat, sev,
             "Synthetic demo row"),
        )
    db.commit()
    db.close()
    print(f"Loaded {len(SAMPLES)} synthetic demo rows into {config.DB_PATH}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="load synthetic sample data instead of live feeds")
    args = p.parse_args()
    run_demo() if args.demo else run_live()
    from dashboard import build
    build()
    print(f"Dashboard written to {config.DASHBOARD_PATH}")
