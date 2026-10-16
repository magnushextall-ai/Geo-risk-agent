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
import os
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

# Columns added later; connect() adds them to older databases.
ENERGY_COLUMNS = {
    "energy_themes": "TEXT",  # comma-separated theme keys; '' = none; NULL = not yet tagged
    "chokepoint": "TEXT",     # one of config.CHOKEPOINTS, or ''
    "energy_note": "TEXT",    # one sentence on the energy-security implication
}

RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    started_at  TEXT,
    fetched     INTEGER,
    new_items   INTEGER,
    classified  INTEGER,
    failed      INTEGER,
    error       TEXT     -- plain-English reason if the news analysis failed
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
  "reason": "<one short sentence explaining the rating>",
  "energy_themes": [<zero or more energy theme keys from the list below>],
  "chokepoint": "<one of: {chokepoints}, or none>",
  "energy_note": "<if any energy theme applies, one short sentence on the energy-security implication; otherwise empty>"}}

Energy security themes (tag every theme that clearly applies, independent of the category above;
use [] if the item has no material energy-security dimension):
{energy_themes}

Source: {source}
Headline: {title}
Summary: {summary}"""


def connect():
    db = sqlite3.connect(config.DB_PATH)
    db.execute(SCHEMA)
    existing = {r[1] for r in db.execute("PRAGMA table_info(articles)")}
    for col, kind in ENERGY_COLUMNS.items():
        if col not in existing:
            db.execute(f"ALTER TABLE articles ADD COLUMN {col} {kind}")
    return db


def save_article(db, item, r, fetched_at, demo=0, row_id=None):
    db.execute(
        """INSERT OR REPLACE INTO articles (id, source, title, summary, link, published, fetched_at,
               country, region, category, severity, reason, demo, energy_themes, chokepoint, energy_note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (row_id or article_id(item["link"]), item["source"], item["title"], item["summary"],
         item["link"], item["published"], fetched_at, r.get("country"), r.get("region"),
         r["category"], r["severity"], r.get("reason"), demo,
         ",".join(r.get("energy_themes", [])), r.get("chokepoint", ""), r.get("energy_note", "")),
    )


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
    energy = "\n".join(f"- {k}: {label}. {desc}" for k, (label, desc) in config.ENERGY_THEMES.items())
    prompt = PROMPT.format(categories=categories, energy_themes=energy,
                           chokepoints=", ".join(config.CHOKEPOINTS), **item)
    msg = client.messages.create(
        model=config.MODEL,
        max_tokens=2000,  # room for the model's thinking as well as its answer
        messages=[{"role": "user", "content": prompt}],
    )
    # The reply can contain several blocks (e.g. thinking first); use only the text ones.
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON in reply (stop_reason={msg.stop_reason})")
    result = json.loads(text[start : end + 1])
    if result.get("category") not in config.CATEGORIES:
        result["category"] = "not_geopolitical"
    result["severity"] = max(0, min(5, int(result.get("severity", 0))))
    themes = result.get("energy_themes") or []
    if isinstance(themes, str):
        themes = [t.strip() for t in themes.split(",")]
    result["energy_themes"] = [t for t in config.ENERGY_THEMES if t in themes]  # keep valid, in fixed order
    cp = (result.get("chokepoint") or "").strip()
    result["chokepoint"] = next((c for c in config.CHOKEPOINTS if c.lower() == cp.lower()), "")
    result["energy_note"] = (result.get("energy_note") or "").strip() if result["energy_themes"] else ""
    return result


def backfill_energy(db, client):
    """Tag headlines stored before the energy lens existed (runs once per old headline)."""
    rows = db.execute(
        "SELECT id, source, title, summary FROM articles WHERE energy_themes IS NULL AND demo = 0 "
        "ORDER BY fetched_at DESC LIMIT ?", (config.ENERGY_BACKFILL_MAX,)).fetchall()
    if not rows:
        return
    print(f"Adding energy tags to {len(rows)} earlier headlines...")
    done = failed = 0
    for row_id, source, title, summary in rows:
        try:
            r = classify(client, {"source": source, "title": title, "summary": summary or ""})
        except Exception as e:
            failed += 1
            print(f"  ! energy tag skipped '{title[:60]}': {e}")
            if done == 0 and failed >= 3:
                break
            continue
        db.execute("UPDATE articles SET energy_themes = ?, chokepoint = ?, energy_note = ? WHERE id = ?",
                   (",".join(r.get("energy_themes", [])), r.get("chokepoint", ""),
                    r.get("energy_note", ""), row_id))
        db.commit()
        done += 1
    print(f"  tagged {done} ({failed} skipped)")


def explain_error(e):
    """Turn an API error into a plain-English reason and fix."""
    text = str(e)
    if e.__cause__ is not None:
        text += f" ({type(e.__cause__).__name__}: {e.__cause__})"
    low = text.lower()
    if "illegal header" in low:
        return ("The API key contains a space or invalid character. Paste it again into the GitHub "
                "secret ANTHROPIC_API_KEY, copying only the key itself.")
    if "credit balance" in low:
        return ("Your Anthropic account has no credit. Add credit under Billing at "
                "console.anthropic.com, then run the workflow again.")
    if "x-api-key" in low or "authentication" in low or "401" in low:
        return ("The API key was rejected. Create a new key at console.anthropic.com and paste it "
                "into the GitHub secret ANTHROPIC_API_KEY (Settings > Secrets and variables > Actions).")
    if "not_found" in low or "model" in low and "404" in low:
        return f"The model '{config.MODEL}' was not found. Check MODEL in config.py."
    if "permission" in low or "403" in low:
        return "The API key does not have permission to use this model. Check your Console account."
    if "rate" in low and "limit" in low or "429" in low:
        return "Hit the API rate limit. It should work on the next run."
    return text[:300]


def run_live():
    from dotenv import load_dotenv
    import anthropic

    load_dotenv()
    db = connect()
    db.execute(RUNS_SCHEMA)
    db.execute("DELETE FROM articles WHERE demo = 1")  # clear any demo rows
    started = datetime.now(timezone.utc).isoformat()

    def finish(fetched, new_count, ok, failed, error):
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)",
                   (started, fetched, new_count, ok, failed, error))
        db.commit()
        db.close()

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"\'')  # tolerate stray spaces, line breaks or quotes
    if not key:
        msg = ("No API key found. Add it as the GitHub secret ANTHROPIC_API_KEY "
               "(Settings > Secrets and variables > Actions).")
        print(f"\n*** NEWS ANALYSIS FAILED: {msg}\n")
        finish(0, 0, 0, 0, msg)
        return
    if not key.startswith("sk-ant-"):
        print("  ! Warning: the API key does not start with 'sk-ant-'; check it was copied correctly.")
    client = anthropic.Anthropic(api_key=key)

    print("Fetching feeds...")
    items = fetch_feeds()
    new = [i for i in items if i["link"] and not db.execute(
        "SELECT 1 FROM articles WHERE id = ?", (article_id(i["link"]),)).fetchone()]
    print(f"{len(items)} items fetched, {len(new)} new articles to classify")
    if not items:
        msg = "Could not read any of the news feeds."
        print(f"\n*** NEWS ANALYSIS FAILED: {msg}\n")
        finish(0, 0, 0, 0, msg)
        return

    now = datetime.now(timezone.utc).isoformat()
    ok = failed = 0
    first_error = None
    for n, item in enumerate(new, 1):
        try:
            r = classify(client, item)
        except Exception as e:  # keep going if one item fails
            failed += 1
            first_error = first_error or explain_error(e)
            print(f"  ! skipped '{item['title'][:60]}': {e}")
            if ok == 0 and failed >= 3:  # same error every time: stop wasting time
                print("  First three items all failed, so stopping.")
                break
            continue
        ok += 1
        save_article(db, item, r, now)
        tag = f" [energy: {','.join(r['energy_themes'])}]" if r.get("energy_themes") else ""
        print(f"  [{n}/{len(new)}] {r['severity']} {r['category']:<22} {item['title'][:60]}{tag}")
        db.commit()

    error = first_error if ok == 0 and failed else None
    if error:
        print(f"\n*** NEWS ANALYSIS FAILED: {error}\n")
    else:
        print(f"Classified {ok} articles ({failed} skipped)")
        try:
            backfill_energy(db, client)
        except Exception as e:  # never let the catch-up stop today's results being saved
            print(f"  ! energy catch-up stopped: {e}")
    finish(len(items), len(new), ok, failed, error)


def run_demo():
    """Load synthetic sample rows so you can see the dashboard without a key."""
    from demo_data import SAMPLES

    db = connect()
    db.execute("DELETE FROM articles WHERE demo = 1")
    today = datetime.now(timezone.utc)
    for i, (days_ago, source, title, country, region, cat, sev, themes, cp) in enumerate(SAMPLES):
        ts = (today - timedelta(days=days_ago)).isoformat()
        item = {"source": source, "title": title, "summary": "", "link": "", "published": ts}
        r = {"country": country, "region": region, "category": cat, "severity": sev,
             "reason": "Synthetic demo row", "energy_themes": themes, "chokepoint": cp,
             "energy_note": "Synthetic demo row" if themes else ""}
        save_article(db, item, r, ts, demo=1, row_id=f"demo{i}")
    db.commit()
    db.close()
    print(f"Loaded {len(SAMPLES)} synthetic demo rows into {config.DB_PATH}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="load synthetic sample data instead of live feeds")
    args = p.parse_args()
    if args.demo:
        run_demo()
    else:
        run_live()
        print("Updating GDELT data...")
        try:
            import gdelt
            gdelt.update()
        except Exception as e:  # the news part still works if GDELT is down
            print(f"  ! GDELT update failed: {e}")
    from dashboard import build
    build()
    print(f"Dashboard written to {config.DASHBOARD_PATH}")
