# Geopolitical Risk Monitor

An AI agent that reads headlines from major international news outlets (BBC, Le Monde, Al Jazeera, The Guardian), uses Claude to classify each one by country, region, risk type and severity, and tracks how geopolitical risk changes over time on a dashboard.

## How it works

1. **Collect**: pulls the latest items from each outlet's public RSS feed (headline, summary, link).
2. **Classify**: sends each new item to Claude with a fixed analytical framework: nine risk categories and a 0–5 severity scale (see `config.py`). Claude returns structured JSON: country, region, category, severity and a one-line justification.
3. **Store**: saves results in a local SQLite database (`risk.db`), skipping anything already seen.
4. **Cross-check with GDELT**: downloads the free daily event files from the [GDELT Project](https://www.gdeltproject.org/), which machine-codes world news into events, and keeps conflict-type events (CAMEO codes 13–20: threats, protests, force posture, sanctions, coercion, assaults, fighting, mass violence) reported by at least two sources. These are mapped to the same risk categories and stored as daily counts per country (`gdelt.py`). Because GDELT keeps a full archive, the first run backfills the last 30 days.
5. **Visualise**: builds the dashboard (`index.html`), showing a daily risk index, events by type, a region × risk-type heatmap, an energy security section and the highest-severity items, filterable by date range, region and lens.

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
- The same event reported by four outlets is counted four times. Next step: cluster duplicate stories into single events.
- Compare the Claude headline classifications with GDELT's coding of the same period to measure agreement, and add ACLED as a curated conflict dataset.
- GDELT is automated and noisy: it can double count, misplace events geographically and mistake reported or historical events for new ones. The two-source filter reduces this but does not remove it.
- Add sources in other languages and regions to reduce coverage bias.
