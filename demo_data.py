"""Synthetic sample rows for --demo mode. These are NOT real news: they exist only
so the dashboard has something to show before you run the agent for real."""

import random

_rng = random.Random(42)

_REGIONS = {
    "Europe": ["Ukraine", "France", "Germany", "Serbia", "Poland"],
    "Middle East": ["Israel", "Iran", "Syria", "Yemen", "Lebanon"],
    "Africa": ["Sudan", "Sahel", "DR Congo", "Ethiopia", "Nigeria"],
    "Asia-Pacific": ["China", "Taiwan", "North Korea", "Myanmar", "India"],
    "Americas": ["United States", "Venezuela", "Mexico", "Haiti", "Brazil"],
    "Russia & Central Asia": ["Russia", "Kazakhstan", "Georgia", "Armenia"],
}

_CATS = {
    "armed_conflict": (3, 5), "military_tension": (2, 4), "terrorism": (2, 4),
    "political_instability": (2, 4), "sanctions_trade": (1, 3), "energy_resources": (2, 4),
    "diplomacy": (1, 3), "cyber_hybrid": (2, 3), "humanitarian": (2, 4),
    "not_geopolitical": (0, 0),
}
_CAT_WEIGHTS = [14, 10, 4, 10, 9, 6, 10, 4, 7, 12]
_SOURCES = ["BBC World", "Le Monde International", "Al Jazeera", "The Guardian World"]


def _make():
    rows = []
    for _ in range(220):
        region = _rng.choice(list(_REGIONS))
        country = _rng.choice(_REGIONS[region])
        cat = _rng.choices(list(_CATS), weights=_CAT_WEIGHTS)[0]
        lo, hi = _CATS[cat]
        sev = _rng.randint(lo, hi)
        days_ago = _rng.randint(0, 29)
        title = f"[DEMO] Synthetic {cat.replace('_', ' ')} item — {country}"
        rows.append((days_ago, _rng.choice(_SOURCES), title, country, region, cat, sev))
    return rows


SAMPLES = _make()
