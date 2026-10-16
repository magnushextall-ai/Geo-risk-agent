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

# GDELT: how many past days of conflict events to keep, and the minimum number of
# separate news sources an event needs (filters out one-off, possibly mistaken reports).
GDELT_DAYS = 30
GDELT_MIN_SOURCES = 2

# ---------------------------------------------------------------------------
# Energy security lens
# A headline can carry any number of these themes on top of its main category
# (e.g. a refinery strike is "armed_conflict" AND "infrastructure_attacks").
ENERGY_THEMES = {
    "supply_routes": ("Oil & gas supply routes",
        "Threats to tanker, LNG or pipeline flows of oil and gas, including attacks on shipping, "
        "blockades and disruption at chokepoints such as Hormuz, the Red Sea/Bab el-Mandeb/Suez, "
        "the Baltic and the Black Sea"),
    "russia_energy": ("Russian energy & sanctions",
        "Russian energy exports and Europe's dependence on them, gas supply cuts, the oil price "
        "cap, the shadow fleet, and sanctions targeting Russian energy"),
    "critical_minerals": ("Critical minerals",
        "Supply of minerals for the energy transition (lithium, cobalt, nickel, copper, graphite, "
        "rare earths, uranium): export controls, mining or processing disputes, resource nationalism"),
    "arctic": ("Arctic & Northern Sea Route",
        "Arctic oil and gas projects (e.g. Yamal LNG, Arctic LNG 2), Northern Sea Route shipping, "
        "and Arctic military or territorial competition affecting energy"),
    "infrastructure_attacks": ("Infrastructure attacks",
        "Physical or cyber attacks and sabotage on power grids, power plants, refineries, "
        "pipelines, subsea cables, interconnectors or other energy infrastructure"),
    "other_energy": ("Other energy security",
        "Other material energy-security risk: OPEC+ supply decisions, energy price shocks, "
        "nuclear plant safety in conflict zones, energy export bans"),
}

# Named chokepoints Claude can attach to a headline (or "none").
CHOKEPOINTS = ["Strait of Hormuz", "Red Sea & Suez", "Baltic Sea", "Black Sea",
               "Arctic & Northern Sea Route"]

# Max previously stored headlines to tag with energy themes per run (one-off catch-up).
ENERGY_BACKFILL_MAX = 200
