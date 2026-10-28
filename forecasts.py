"""Makes specific, time-limited forecasts, resolves them and keeps score.

Every week Claude writes a few yes/no questions about the situations the monitor is
tracking, each with a deadline, clear resolution criteria and a probability. You can
add your own probability for each one in my_forecasts.csv. When a deadline passes,
Claude checks the stored headlines to decide what happened (you can override it), and
both forecasters are scored with the Brier score: the squared gap between the
probability given and what happened. 0 is perfect; always saying 50% scores 0.25.
"""

import csv
import os
import re
from datetime import date, datetime, timedelta, timezone

import config
from llm import ask_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecasts (
    id              TEXT PRIMARY KEY,   -- e.g. F261022-1 (made 22 Oct 2026, question 1)
    created         TEXT,
    question        TEXT,
    criteria        TEXT,               -- exactly what counts as YES
    deadline        TEXT,
    probability     REAL,               -- Claude's probability of YES
    rationale       TEXT,
    country         TEXT,
    status          TEXT,               -- open | resolved | unresolvable
    outcome         INTEGER,            -- 1 = yes, 0 = no
    resolved_on     TEXT,
    resolution_note TEXT
);
"""

MAKE_PROMPT = """You are a geopolitical forecaster in the style of the Good Judgment Project.
Today is {today}. Below is what a news-monitoring system has tracked over the last two weeks.

Most significant events (status | country | reports | max severity 0-5 | event | recent headlines):
{events}

Countries with unusual conflict activity in GDELT data (last 7 days vs their own norm):
{changes}

Forecasts already open (do not duplicate these):
{open}

Write {n} new forecasting questions about these situations. Each must:
- be a yes/no question about whether something happens between today and a deadline you choose,
  phrased "... by <deadline>?"; the deadline must fall between {min_date} and {max_date} (do not
  ask about a window that starts in the future);
- have resolution criteria precise enough that a neutral reader of major international news
  (BBC, Reuters, Le Monde, Al Jazeera) could later decide YES or NO without argument;
- be genuinely uncertain: your probability must be between 0.05 and 0.95;
- be useful to a risk analyst (escalation, ceasefires, sanctions, elections, attacks, supply
  disruption), with the set covering different countries or topics.

Give a calibrated probability: start from the base rate for this kind of event, then adjust for
the specific evidence. Explain your reasoning in one or two sentences.

Return ONLY a JSON object, no other text:
{{"forecasts": [{{"question": "...", "criteria": "...", "deadline": "YYYY-MM-DD",
  "probability": 0.0, "rationale": "...", "country": "..."}}]}}"""

RESOLVE_PROMPT = """You are resolving a forecasting question using news headlines.

Question: {question}
Resolves YES if: {criteria}
Deadline: {deadline} (the question was asked on {created})

Headlines collected by the monitor between those dates (date | source | headline):
{headlines}

Decide whether the YES criteria were met on or before the deadline.
- Answer "yes" only if the headlines clearly show the criteria were met.
- Answer "no" only if the headlines show the situation was covered and the criteria clearly
  were not met (e.g. coverage continues and describes the opposite).
- Otherwise answer "unclear". Absence of headlines alone is not evidence of "no".

Return ONLY a JSON object, no other text:
{{"outcome": "yes" | "no" | "unclear", "evidence": "<one sentence citing the deciding headline(s)>"}}"""


def _today():
    return datetime.now(timezone.utc).date()


def ensure_schema(db):
    db.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Your own forecasts

def _parse_prob(text):
    text = (text or "").strip().replace("%", "")
    if not text:
        return None
    try:
        p = float(text)
    except ValueError:
        return None
    if p > 1:
        p /= 100  # "35" means 35%
    return min(max(p, 0.0), 1.0)


def read_mine(path=None):
    """Read my_forecasts.csv: id, my_probability, outcome_override, note."""
    path = path or config.MY_FORECASTS_PATH
    mine = {}
    if not os.path.exists(path):
        return mine
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [l for l in f if l.strip() and not l.lstrip().startswith("#")]
    for row in csv.reader(lines):
        if not row or row[0].strip().lower() in ("id", ""):
            continue
        fid = row[0].strip().upper()
        override = (row[2].strip().lower() if len(row) > 2 else "")
        mine[fid] = {
            "my_probability": _parse_prob(row[1] if len(row) > 1 else ""),
            "override": 1 if override in ("yes", "y", "1", "true") else 0 if override in ("no", "n", "0", "false") else None,
            "note": row[3].strip() if len(row) > 3 else "",
        }
    return mine


# ---------------------------------------------------------------------------
# Making forecasts

def due(db, today=None):
    today = today or _today()
    last = db.execute("SELECT MAX(created) FROM forecasts").fetchone()[0]
    return not last or (today - date.fromisoformat(last)).days >= config.FORECAST_EVERY_DAYS


def make(db, client, events, changes, today=None, log=print):
    today = today or _today()
    ensure_schema(db)
    if not due(db, today):
        return
    top = [e for e in events if e["status"] != "Quiet"][:15]
    if not top:
        log("  no events to forecast on yet")
        return
    log(f"Making {config.FORECASTS_PER_ROUND} new forecasts...")
    ev_text = "\n".join(
        f"{e['status']} | {e['country']} | {e['reports']} | {e['max_severity']} | {e['name']} | "
        + "; ".join(h["title"] for h in e["headlines"][:3]) for e in top)
    ch = changes.get("rising", []) + changes.get("falling", [])
    ch_text = "\n".join(f"{c['country']}: {c['recent_per_day']} events/day vs {c['baseline_per_day']} usual"
                        for c in ch) or "(not enough history yet)"
    open_text = "\n".join(f"- {q} (by {d})" for q, d in db.execute(
        "SELECT question, deadline FROM forecasts WHERE status = 'open'")) or "(none)"
    min_d = today + timedelta(days=config.FORECAST_MIN_DAYS)
    max_d = today + timedelta(days=config.FORECAST_MAX_DAYS)
    reply = ask_json(client, MAKE_PROMPT.format(
        today=today.isoformat(), events=ev_text, changes=ch_text, open=open_text,
        n=config.FORECASTS_PER_ROUND, min_date=min_d.isoformat(), max_date=max_d.isoformat()),
        max_tokens=12000)
    n = 0
    for f in reply.get("forecasts", [])[: config.FORECASTS_PER_ROUND]:
        q = str(f.get("question") or "").strip()
        if not q:
            continue
        try:
            dl = date.fromisoformat(str(f.get("deadline"))[:10])
        except ValueError:
            dl = today + timedelta(days=30)
        dl = min(max(dl, min_d), max_d)
        try:
            p = float(f.get("probability"))
        except (TypeError, ValueError):
            continue
        p = min(max(p / 100 if p > 1 else p, 0.02), 0.98)
        n += 1
        fid = f"F{today.strftime('%y%m%d')}-{n}"
        db.execute("INSERT OR REPLACE INTO forecasts VALUES (?,?,?,?,?,?,?,?, 'open', NULL, NULL, NULL)",
                   (fid, today.isoformat(), q, str(f.get("criteria") or "").strip(), dl.isoformat(),
                    round(p, 3), str(f.get("rationale") or "").strip(), str(f.get("country") or "").strip()))
    db.commit()
    log(f"  made {n} forecasts")


# ---------------------------------------------------------------------------
# Resolving forecasts

_STOP = set("will the a an of to in on by for and or be is are at from with before after than "
            "any its it this that which who as least more less over under between".split())


def _keywords(text):
    return {w for w in re.findall(r"[a-zà-ÿ]{3,}", (text or "").lower()) if w not in _STOP}


def resolve(db, client, today=None, log=print):
    today = today or _today()
    ensure_schema(db)
    open_ = db.execute("SELECT id, created, question, criteria, deadline, country FROM forecasts "
                       "WHERE status = 'open' AND deadline < ?", (today.isoformat(),)).fetchall()
    for fid, created, question, criteria, deadline, country in open_:
        words = _keywords(question + " " + criteria + " " + (country or ""))
        until = (date.fromisoformat(deadline) + timedelta(days=2)).isoformat()
        cands = db.execute("SELECT SUBSTR(fetched_at,1,10), source, title, summary FROM articles "
                           "WHERE SUBSTR(fetched_at,1,10) BETWEEN ? AND ? AND demo = 0",
                           (created, until)).fetchall()
        scored = sorted(((len(words & _keywords(t + " " + (s or ""))), d, src, t) for d, src, t, s in cands),
                        reverse=True)
        picked = sorted([x for x in scored if x[0] >= 2][:80], key=lambda x: x[1])
        if not picked:
            outcome, note = "unclear", "No relevant headlines found."
        else:
            try:
                r = ask_json(client, RESOLVE_PROMPT.format(
                    question=question, criteria=criteria, deadline=deadline, created=created,
                    headlines="\n".join(f"{d} | {src} | {t}" for _, d, src, t in picked)), max_tokens=6000)
                outcome, note = str(r.get("outcome", "unclear")).lower(), str(r.get("evidence", ""))
            except Exception as e:
                log(f"  ! could not resolve {fid}: {e}")
                continue
        if outcome in ("yes", "no"):
            db.execute("UPDATE forecasts SET status='resolved', outcome=?, resolved_on=?, resolution_note=? "
                       "WHERE id=?", (1 if outcome == "yes" else 0, today.isoformat(), note, fid))
            log(f"  resolved {fid}: {outcome.upper()}")
        elif (today - date.fromisoformat(deadline)).days >= config.FORECAST_GIVE_UP_DAYS:
            db.execute("UPDATE forecasts SET status='unresolvable', resolved_on=?, resolution_note=? WHERE id=?",
                       (today.isoformat(), note or "Headlines did not settle the question.", fid))
            log(f"  {fid}: could not be resolved from headlines")
        else:
            db.execute("UPDATE forecasts SET resolution_note=? WHERE id=?", (note, fid))
    db.commit()


# ---------------------------------------------------------------------------
# Scoring, for the dashboard

def brier(p, outcome):
    return round((p - outcome) ** 2, 3)


def summary(db, mine=None):
    try:
        ensure_schema(db)
    except Exception:
        return {"forecasts": [], "score": {}}
    mine = read_mine() if mine is None else mine
    cols = ["id", "created", "question", "criteria", "deadline", "probability", "rationale",
            "country", "status", "outcome", "resolved_on", "resolution_note"]
    out = []
    for row in db.execute(f"SELECT {', '.join(cols)} FROM forecasts ORDER BY created DESC, id"):
        f = dict(zip(cols, row))
        m = mine.get(f["id"].upper(), {})
        f["my_probability"] = m.get("my_probability")
        f["my_note"] = m.get("note", "")
        if m.get("override") is not None:  # your call on the outcome always wins
            f["outcome"], f["status"] = m["override"], "resolved"
            f["resolution_note"] = "Outcome set by hand in my_forecasts.csv. " + (f["resolution_note"] or "")
        if f["status"] == "resolved":
            f["brier_ai"] = brier(f["probability"], f["outcome"])
            f["brier_me"] = brier(f["my_probability"], f["outcome"]) if f["my_probability"] is not None else None
        out.append(f)
    res = [f for f in out if f["status"] == "resolved"]
    both = [f for f in res if f.get("brier_me") is not None]
    avg = lambda xs: round(sum(xs) / len(xs), 3) if xs else None
    score = {
        "resolved": len(res),
        "open": sum(f["status"] == "open" for f in out),
        "ai": avg([f["brier_ai"] for f in res]),
        "me": avg([f["brier_me"] for f in both]),
        "ai_on_mine": avg([f["brier_ai"] for f in both]),  # fair head-to-head on the same questions
        "mine_count": len(both),
    }
    return {"forecasts": out, "score": score}
