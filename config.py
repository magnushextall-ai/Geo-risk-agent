"""Settings for the geopolitical risk agent. Edit these to change what it tracks."""

# RSS feeds to pull headlines from. Add or remove freely.
FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Le Monde International": "https://www.lemonde.fr/international/rss_full.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "The Guardian World": "https://www.theguardian.com/world/rss",
}

# The risk categories Claude can assign. Keep them few and distinct:
# this list is the core of your analytical framework, so be ready to justify it.
CATEGORIES = {
    "armed_conflict": "Active fighting, military strikes, insurgency, or war",
    "military_tension": "Troop build-ups, exercises, border standoffs, arms deals, threats of force",
    "terrorism": "Terrorist attacks, plots, or designations",
    "political_instability": "Coups, contested elections, government collapse, mass protest or unrest",
    "sanctions_trade": "Sanctions, tariffs, export controls, trade disputes",
    "energy_resources": "Disruption to oil, gas, food, water, critical minerals or shipping routes",
    "diplomacy": "Summits, treaties, ceasefires, breakdowns in diplomatic relations",
    "cyber_hybrid": "State-linked cyberattacks, disinformation, sabotage",
    "humanitarian": "Refugee flows, famine, mass atrocities, humanitarian crises",
    "not_geopolitical": "Anything else (sport, culture, domestic news with no international risk)",
}

# Model used for classification. A small model is cheap and accurate enough for headlines.
MODEL = "claude-haiku-5-5"

DB_PATH = "risk.db"
DASHBOARD_PATH = "index.html"  # index.html so GitHub Pages shows it as the home page

# Max articles to classify per feed per run (keeps costs predictable).
MAX_PER_FEED = 40
