# Geopolitical Risk Monitor

An AI agent that reads headlines from major international news outlets (BBC, Le Monde, Al Jazeera, The Guardian), uses Claude to classify each one by country, region, risk type and severity, and tracks how geopolitical risk changes over time on a dashboard.

## How it works

1. **Collect**: pulls the latest items from each outlet's public RSS feed (headline, summary, link).
2. **Classify**: sends each new item to Claude with a fixed analytical framework: nine risk categories and a 0–5 severity scale (see `config.py`). Claude returns structured JSON: country, region, category, severity and a one-line justification.
3. **Store**: saves results in a local SQLite database (`risk.db`), skipping anything already seen.
4. **Cross-check with GDELT**: downloads the free daily event files from the [GDELT Project](https://www.gdeltproject.org/), which machine-codes world news into events, and keeps conflict-type events (CAMEO codes 13–20: threats, protests, force posture, sanctions, coercion, assaults, fighting, mass violence) reported by at least two sources. These are mapped to the same risk categories and stored as daily counts per country (`gdelt.py`). Because GDELT keeps a full archive, the first run backfills the last 30 days.
5. **Group into events**: Claude groups repeat coverage of the same story (different outlets, different days, live blogs) into distinct events, so each story is counted once (`events.py`).
6. **Forecast**: once a week Claude makes specific yes/no forecasts with deadlines; past deadlines are resolved from the stored headlines and scored (`forecasts.py`).
7. **Visualise**: builds the dashboard (`index.html`), showing what's changing, forecasts and scores, tracked events, a daily risk index, events by type, a region × risk-type heatmap, an energy security section and the highest-severity items, filterable by date range, region and lens.

## What's changing: change detection

Raw counts mostly measure how much attention a place gets, so the tool compares things with their own history instead:

- **Events** get a status from transparent rules comparing the last 3 days with the 7 before: *Escalating* (severity up a point with 2+ reports, or coverage up 50%+ with 4+ reports), *Cooling* (the reverse), *New* (first reported in the last 3 days), *Steady* or *Quiet*.
- **Countries** are flagged when their GDELT conflict events over the last 7 days are at least 1.5× (or below two-thirds of) their own norm over the previous weeks *and* the change is statistically unlikely to be noise (z ≥ 2, with a floor for random variation). Thresholds are in `config.py`.

## Forecasting and scoring

Tracking the past is easy; the test of an analytical tool is whether it can anticipate. Every week Claude writes four yes/no questions about the situations being tracked, each with precise resolution criteria, a deadline 2–8 weeks out, a probability and a short rationale (anchored on base rates, in the style of the Good Judgment Project).

- **Resolution:** after the deadline, Claude reads the relevant stored headlines and decides YES, NO or *unclear*. It is told that missing coverage is not evidence of NO. Questions still unclear two weeks after the deadline are marked unresolvable and excluded from scoring.
- **Human forecaster:** I add my own probabilities (and can override an outcome) in `my_forecasts.csv`.
- **Scoring:** each forecast gets a [Brier score](https://en.wikipedia.org/wiki/Brier_score), (probability − outcome)², where 0 is perfect and always saying 50% scores 0.25. The dashboard compares Claude and me on the same questions.

## Energy security lens

Energy risk rarely fits one category: a drone strike on a refinery is *armed conflict*, but it is also an energy-supply story. So energy is tagged as a separate, cross-cutting lens. Alongside its main category, Claude gives each headline:

- **Energy themes** (any that apply): oil & gas supply routes; Russian energy & sanctions; critical minerals; Arctic & Northern Sea Route; attacks on energy and subsea infrastructure; other energy security
- **Chokepoint** if one is involved: Strait of Hormuz, Red Sea & Suez, Baltic Sea, Black Sea, Arctic & Northern Sea Route
- **Energy note**: one sentence on the energy-security implication

The dashboard's *Lens* filter narrows every headline chart to energy items (or one theme), and the Energy security section shows a chokepoint watch, items by theme, a daily energy risk index and the energy-tagged items with their notes. Theme definitions live in `config.py`, so the lens can be tuned or extended. The lens applies to the headline analysis only, not to GDELT.

## Running it

The agent runs automatically every morning using GitHub Actions (`.github/workflows/daily.yml`), and the dashboard is published with GitHub Pages. The Anthropic API key is stored as a repository secret called `ANTHROPIC_API_KEY`.

## Running it locally (optional)

You need Python 3.10+ and an Anthropic API key (from console.anthropic.com).

```bash
pip install -r requirements.txt
cp .env.example .env          # then paste your API key into .env
```

## Usage

```bash
python agent.py --demo   # try it with synthetic data, no key needed
python agent.py          # fetch live news, classify, rebuild the dashboard
```

Open `index.html` in a browser. Your first live run clears out any demo rows.

## Design decisions

- **Headlines and summaries only.** The agent stores RSS summaries and links, not full articles, which respects publishers' terms and keeps costs low.
- **A small, fixed taxonomy.** Nine categories that are distinct enough for consistent classification. Changing them is a one-line edit in `config.py`.
- **Severity is a judgement, not a fact.** Every rating comes with Claude's one-line reason so it can be audited.

## Limitations and next steps

- Counts reflect what outlets choose to cover, so this measures *reported* risk, not risk itself. Regions with less Western media coverage will be under-counted.
- Event grouping is done by the model and can occasionally merge or split stories; the headlines behind each event are shown so this can be checked.
- Forecasts are resolved from headlines collected by this tool only. A small number of forecasts says little about skill; scores become meaningful after a few dozen.
- Compare the Claude headline classifications with GDELT's coding of the same period to measure agreement, and add ACLED as a curated conflict dataset.
- GDELT is automated and noisy: it can double count, misplace events geographically and mistake reported or historical events for new ones. The two-source filter reduces this but does not remove it.
- Add sources in other languages and regions to reduce coverage bias.
