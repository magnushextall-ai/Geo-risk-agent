"""Groups repeated coverage of the same story into events, and detects what is changing.

Headlines are counted once per *event* rather than once per article, so a live blog
republished every day, or four outlets covering the same attack, no longer inflate
the numbers. Each event then gets a status (New, Escalating, Steady, Cooling, Quiet)
from simple, transparent rules, and GDELT conflict activity in each country is
compared with that country's own recent norm rather than with other countries.
"""

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import config
from llm import ask_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,   -- E1, E2, ...
    name        TEXT,
    country     TEXT,
    region      TEXT,
    first_seen  TEXT,
    last_seen   TEXT
);
"""

PROMPT = """You maintain the list of ongoing news events for a geopolitical risk monitor.
An event is one specific developing story, for example "Iranian attacks on shipping in the Strait
of Hormuz" or "RSF siege of El Fasher, Sudan", not a whole country or topic. Coverage of the same
story by different outlets, on different days or in different languages belongs to the same event.
Separate stories in the same country are separate events.

Existing events (id | name | country):
{events}

New headlines (number | date | country | headline):
{headlines}

Assign every new headline to an existing event if it is the same story; otherwise create a new
event with a short, specific English name (at most 8 words) and its main country. Headlines that
belong to the same new event must use exactly the same new name.

Return ONLY a JSON object, no other text:
{{"assignments": [{{"i": <headline number>, "event": "<existing event id>"}},
                  {{"i": <headline number>, "new": "<new event name>", "country": "<country>"}}]}}"""


def _today():
    return datetime.now(timezone.utc).date()


def ensure_schema(db):
    db.executescript(SCHEMA)
    cols = {r[1] for r in db.execute("PRAGMA table_info(articles)")}
    if "event_id" not in cols:
        db.execute("ALTER TABLE articles ADD COLUMN event_id TEXT")


def _next_id(db):
    n = db.execute("SELECT MAX(CAST(SUBSTR(id, 2) AS INTEGER)) FROM events").fetchone()[0] or 0
    return n + 1


def update(db, client, log=print):
    """Assign event ids to geopolitical headlines that don't have one yet."""
    ensure_schema(db)
    pending = db.execute(
        "SELECT id, fetched_at, country, region, title FROM articles "
        "WHERE event_id IS NULL AND demo = 0 AND category != 'not_geopolitical' "
        "ORDER BY fetched_at").fetchall()
    if not pending:
        return
    log(f"Grouping {len(pending)} headlines into events...")
    by_day = defaultdict(list)
    for row in pending:
        by_day[row[1][:10]].append(row)

    assigned = calls = 0
    for day in sorted(by_day):
        rows = by_day[day]
        for start in range(0, len(rows), config.EVENT_BATCH):
            batch = rows[start : start + config.EVENT_BATCH]
            window = (date.fromisoformat(day) - timedelta(days=config.EVENT_MEMORY_DAYS)).isoformat()
            known = db.execute(
                "SELECT id, name, country FROM events WHERE last_seen >= ? "
                "ORDER BY last_seen DESC LIMIT ?", (window, config.EVENT_MAX_KNOWN)).fetchall()
            known_ids = {k[0] for k in known}
            prompt = PROMPT.format(
                events="\n".join(f"{i} | {n} | {c}" for i, n, c in known) or "(none yet)",
                headlines="\n".join(f"{n} | {r[1][:10]} | {r[2]} | {r[4]}" for n, r in enumerate(batch)))
            try:
                reply = ask_json(client, prompt, max_tokens=8000)
                calls += 1
            except Exception as e:
                log(f"  ! event grouping stopped (will retry next run): {e}")
                _refresh_dates(db)
                return
            new_ids = {}
            choice = {}
            for a in reply.get("assignments", []):
                try:
                    i = int(a.get("i"))
                except (TypeError, ValueError):
                    continue
                if not 0 <= i < len(batch) or i in choice:
                    continue
                if a.get("event") in known_ids:
                    choice[i] = a["event"]
                elif a.get("new"):
                    name = str(a["new"]).strip()[:120]
                    key = name.lower()
                    if key not in new_ids:
                        new_ids[key] = (f"E{_next_id(db)}", name, a.get("country") or batch[i][2], batch[i][3])
                        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (*new_ids[key], day, day))
                    choice[i] = new_ids[key][0]
            for i, row in enumerate(batch):
                if i not in choice:  # the model skipped it: give it an event of its own
                    eid = f"E{_next_id(db)}"
                    db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                               (eid, row[4][:120], row[2], row[3], day, day))
                    choice[i] = eid
                db.execute("UPDATE articles SET event_id = ? WHERE id = ?", (choice[i], row[0]))
                assigned += 1
            db.commit()
    _refresh_dates(db)
    n_events = db.execute("SELECT COUNT(DISTINCT event_id) FROM articles WHERE event_id IS NOT NULL").fetchone()[0]
    log(f"  grouped {assigned} headlines ({calls} calls); {n_events} events in total")


def _refresh_dates(db):
    db.execute("""UPDATE events SET
        first_seen = (SELECT MIN(SUBSTR(fetched_at, 1, 10)) FROM articles WHERE event_id = events.id),
        last_seen  = (SELECT MAX(SUBSTR(fetched_at, 1, 10)) FROM articles WHERE event_id = events.id)
        WHERE EXISTS (SELECT 1 FROM articles WHERE event_id = events.id)""")
    db.commit()


def summarise(db, today=None, days=config.EVENT_TRACK_DAYS):
    """Events reported in the last `days` days, with daily coverage and a status."""
    today = today or _today()
    try:
        ensure_schema(db)
    except Exception:
        return []
    since = (today - timedelta(days=days - 1)).isoformat()
    rows = db.execute(
        "SELECT a.event_id, SUBSTR(a.fetched_at, 1, 10), a.severity, a.source, a.title, a.link, "
        "e.name, e.country, e.region, e.first_seen "
        "FROM articles a JOIN events e ON e.id = a.event_id "
        "WHERE SUBSTR(a.fetched_at, 1, 10) >= ? ORDER BY a.fetched_at DESC", (since,)).fetchall()
    ev = {}
    for eid, d, sev, src, title, link, name, country, region, first in rows:
        e = ev.setdefault(eid, {"id": eid, "name": name, "country": country, "region": region,
                                "first_seen": first, "daily": defaultdict(int), "sev": defaultdict(int),
                                "sources": set(), "headlines": []})
        e["daily"][d] += 1
        e["sev"][d] = max(e["sev"][d], sev or 0)
        e["sources"].add(src)
        if len(e["headlines"]) < 6:
            e["headlines"].append({"title": title, "link": link, "source": src, "day": d, "severity": sev})

    out = []
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    recent = set(dates[-3:])            # last 3 days
    earlier = set(dates[-10:-3])         # the 7 days before that
    for e in ev.values():
        r_n = sum(e["daily"][d] for d in recent)
        p_n = sum(e["daily"][d] for d in earlier)
        r_s = max([e["sev"][d] for d in recent] or [0])
        p_s = max([e["sev"][d] for d in earlier] or [0])
        last = max(d for d in e["daily"])
        if last < min(recent):
            status = "Quiet"
        elif e["first_seen"] >= min(recent):
            status = "New"
        elif (r_s >= p_s + 1 and r_s >= 3 and r_n >= 2) or (r_n >= 4 and r_n / 3 >= 1.5 * max(p_n, 1) / 7):
            status = "Escalating"   # clearly more severe, or clearly more coverage
        elif (r_s <= p_s - 1 and p_s >= 3) or (p_n >= 4 and r_n / 3 <= 0.5 * p_n / 7):
            status = "Cooling"      # clearly less severe, or clearly less coverage
        else:
            status = "Steady"
        out.append({
            "id": e["id"], "name": e["name"], "country": e["country"], "region": e["region"],
            "status": status, "first_seen": e["first_seen"], "last_seen": last,
            "reports": sum(e["daily"].values()), "recent_reports": r_n,
            "max_severity": max(e["sev"].values()), "recent_severity": r_s,
            "sources": len(e["sources"]), "daily": [e["daily"].get(d, 0) for d in dates],
            "headlines": e["headlines"],
        })
    order = {"Escalating": 0, "New": 1, "Steady": 2, "Cooling": 3, "Quiet": 4}
    out.sort(key=lambda e: (order[e["status"]], -e["recent_severity"], -e["max_severity"], -e["reports"]))
    return out


def gdelt_changes(db):
    """Countries whose GDELT conflict activity in the last 7 days is unusual for them."""
    try:
        days = [r[0] for r in db.execute("SELECT day FROM gdelt_days_loaded ORDER BY day")]
    except Exception:
        return {"ready": False, "rising": [], "falling": []}
    if len(days) < 7 + config.CHANGE_MIN_BASELINE_DAYS:
        return {"ready": False, "rising": [], "falling": [], "baseline_days": max(0, len(days) - 7)}
    recent, base = days[-7:], days[:-7]
    counts = defaultdict(lambda: defaultdict(int))
    cats = defaultdict(lambda: defaultdict(int))
    region = {}
    for d, country, reg, cat, n in db.execute(
            "SELECT day, country, region, category, events FROM gdelt_daily WHERE day >= ?", (days[0],)):
        counts[country][d] += n
        region[country] = reg
        if d in recent:
            cats[country][cat] += n
    rising, falling = [], []
    for country, by_day in counts.items():
        r = [by_day.get(d, 0) for d in recent]
        b = [by_day.get(d, 0) for d in base]
        r_mean, b_mean = sum(r) / len(r), sum(b) / len(b)
        if max(r_mean, b_mean) < config.CHANGE_MIN_DAILY_EVENTS:
            continue  # too few events to say anything
        sd = math.sqrt(sum((x - b_mean) ** 2 for x in b) / max(1, len(b) - 1))
        sd = max(sd, math.sqrt(max(b_mean, 1)))  # floor: roughly Poisson noise
        z = (r_mean - b_mean) / (sd / math.sqrt(len(r)))
        ratio = (r_mean + 1) / (b_mean + 1)
        item = {"country": country, "region": region[country], "recent_per_day": round(r_mean, 1),
                "baseline_per_day": round(b_mean, 1), "ratio": round(ratio, 2), "z": round(z, 1),
                "driver": max(cats[country], key=cats[country].get) if cats[country] else None}
        if ratio >= config.CHANGE_RATIO and z >= config.CHANGE_Z:
            rising.append(item)
        elif ratio <= 1 / config.CHANGE_RATIO and z <= -config.CHANGE_Z:
            falling.append(item)
    rising.sort(key=lambda x: -x["ratio"])
    falling.sort(key=lambda x: x["ratio"])
    return {"ready": True, "rising": rising[:8], "falling": falling[:5],
            "recent": [recent[0], recent[-1]], "baseline": [base[0], base[-1]]}
