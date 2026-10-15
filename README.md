# Geopolitical Risk Monitor

An AI agent that reads headlines from major international news outlets (BBC, Le Monde, Al Jazeera, The Guardian), uses Claude to classify each one by country, region, risk type and severity, and tracks how geopolitical risk changes over time on a dashboard.

## How it works

1. **Collect**: pulls the latest items from each outlet's public RSS feed (headline, summary, link).
2. **Classify**: sends each new item to Claude with a fixed analytical framework: nine risk categories and a 0–5 severity scale (see `config.py`). Claude returns structured JSON: country, region, category, severity and a one-line justification.
3. **Store**: saves results in a local SQLite database (`risk.db`), skipping anything already seen.
4. **Visualise**: builds the dashboard (`index.html`), showing a daily risk index, events by type, a region × risk-type heatmap and the highest-severity items, filterable by date range and region.

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
- Validate against an established dataset such as ACLED or GDELT to measure how well the classifications hold up.
- Add sources in other languages and regions to reduce coverage bias.
