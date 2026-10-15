"""Adds GDELT conflict-event data to the risk database.

GDELT (gdeltproject.org) machine-codes world news into events every day and keeps
a full archive, so unlike RSS feeds it can fill in past days. This script
downloads GDELT's free daily event files, keeps only conflict-type events
(CAMEO codes 13-20: threats, protests, force posture, sanctions, coercion,
assaults, fighting, mass violence), and stores daily counts per country and
risk category. No API key or Claude calls are needed.

Run on its own with:  python gdelt.py
It is also run automatically by agent.py. Each run fills in any missing days
in the last GDELT_DAYS days, so the first run backfills the whole window.
"""

import csv
import io
import sqlite3
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date, timedelta

import config

URL = "http://data.gdeltproject.org/events/{day}.export.CSV.zip"

SCHEMA = """
CREATE TABLE IF NOT EXISTS gdelt_daily (
    day        TEXT,     -- YYYY-MM-DD
    country    TEXT,
    region     TEXT,
    category   TEXT,
    events     INTEGER,  -- number of distinct events
    mentions   INTEGER,  -- total times those events were mentioned in the news
    goldstein  REAL,     -- average Goldstein score (-10 most destabilising, +10 most stabilising)
    PRIMARY KEY (day, country, category)
);
CREATE TABLE IF NOT EXISTS gdelt_days_loaded (day TEXT PRIMARY KEY);
"""

# Column positions in GDELT 1.0 daily event files (58 tab-separated columns).
COL_IS_ROOT, COL_CODE, COL_BASE, COL_ROOT = 25, 26, 27, 28
COL_GOLDSTEIN, COL_MENTIONS, COL_SOURCES = 30, 31, 32
COL_ACTION_COUNTRY = 51


def categorise(root, base):
    """Map a CAMEO event code to one of our risk categories (or None to skip)."""
    if root == "13" or root == "15":
        return "military_tension"          # threaten / exhibit force posture
    if root == "14" or root == "17":
        return "political_instability"     # protest / coerce, repress, arrest
    if root == "16":
        return "sanctions_trade" if base == "163" else "diplomacy"  # 163 = embargo, sanctions
    if root == "18":
        return "terrorism" if base == "183" else "armed_conflict"   # 183 = bombing
    if root in ("19", "20"):
        return "armed_conflict"            # fight / mass violence
    return None


def fetch_day(day):
    """Download one day's file and return aggregated rows, or None if unavailable."""
    url = URL.format(day=day.strftime("%Y%m%d"))
    req = urllib.request.Request(url, headers={"User-Agent": "geo-risk-agent"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # not published yet
        raise

    agg = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        with z.open(z.namelist()[0]) as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                                delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in reader:
                if len(row) < 52 or row[COL_IS_ROOT] != "1":
                    continue  # root events only, to reduce double counting
                try:
                    if int(row[COL_SOURCES]) < config.GDELT_MIN_SOURCES:
                        continue
                    mentions = int(row[COL_MENTIONS])
                    goldstein = float(row[COL_GOLDSTEIN])
                except ValueError:
                    continue
                cat = categorise(row[COL_ROOT], row[COL_BASE])
                fips = row[COL_ACTION_COUNTRY]
                if not cat or fips not in COUNTRIES:
                    continue
                key = (fips, cat)
                a = agg.setdefault(key, [0, 0, 0.0])
                a[0] += 1
                a[1] += mentions
                a[2] += goldstein

    iso = day.isoformat()
    return [(iso, COUNTRIES[f][0], COUNTRIES[f][1], cat, n, m, round(g / n, 2))
            for (f, cat), (n, m, g) in agg.items()]


def update(days=None, today=None):
    days = days or config.GDELT_DAYS
    today = today or date.today()
    db = sqlite3.connect(config.DB_PATH)
    db.executescript(SCHEMA)
    loaded = {r[0] for r in db.execute("SELECT day FROM gdelt_days_loaded")}

    # Drop data older than the window so the database stays small.
    oldest = (today - timedelta(days=days)).isoformat()
    db.execute("DELETE FROM gdelt_daily WHERE day < ?", (oldest,))
    db.execute("DELETE FROM gdelt_days_loaded WHERE day < ?", (oldest,))

    for i in range(days, 0, -1):          # yesterday back to `days` ago, oldest first
        day = today - timedelta(days=i)
        if day.isoformat() in loaded:
            continue
        try:
            rows = fetch_day(day)
        except Exception as e:             # keep going if one day fails
            print(f"  ! GDELT {day}: {e}")
            continue
        if rows is None:
            print(f"  GDELT {day}: not published yet")
            continue
        db.executemany("INSERT OR REPLACE INTO gdelt_daily VALUES (?,?,?,?,?,?,?)", rows)
        db.execute("INSERT OR IGNORE INTO gdelt_days_loaded VALUES (?)", (day.isoformat(),))
        db.commit()
        print(f"  GDELT {day}: {sum(r[4] for r in rows)} conflict events")
    db.close()


# GDELT uses FIPS 10-4 country codes. Code -> (name, region).
_R = {
    "Europe": "AL Albania|AN Andorra|AU Austria|BE Belgium|BK Bosnia and Herzegovina|BU Bulgaria|"
              "HR Croatia|CY Cyprus|EZ Czechia|DA Denmark|EN Estonia|FI Finland|FR France|GM Germany|"
              "GR Greece|HU Hungary|IC Iceland|EI Ireland|IT Italy|KV Kosovo|LG Latvia|LS Liechtenstein|"
              "LH Lithuania|LU Luxembourg|MK North Macedonia|MT Malta|MD Moldova|MN Monaco|MJ Montenegro|"
              "NL Netherlands|NO Norway|PL Poland|PO Portugal|RO Romania|SM San Marino|RI Serbia|"
              "LO Slovakia|SI Slovenia|SP Spain|SW Sweden|SZ Switzerland|UK United Kingdom|UP Ukraine|"
              "BO Belarus|VT Vatican City",
    "Russia & Central Asia": "RS Russia|KZ Kazakhstan|KG Kyrgyzstan|TI Tajikistan|TX Turkmenistan|"
              "UZ Uzbekistan|GG Georgia|AM Armenia|AJ Azerbaijan",
    "Middle East": "IS Israel|WE West Bank|GZ Gaza Strip|LE Lebanon|SY Syria|JO Jordan|IZ Iraq|IR Iran|"
              "SA Saudi Arabia|YM Yemen|MU Oman|AE United Arab Emirates|QA Qatar|BA Bahrain|KU Kuwait|"
              "TU Turkey|EG Egypt",
    "Africa": "AG Algeria|AO Angola|BN Benin|BC Botswana|UV Burkina Faso|BY Burundi|CM Cameroon|"
              "CV Cape Verde|CT Central African Republic|CD Chad|CN Comoros|CG DR Congo|CF Republic of the Congo|"
              "IV Cote d'Ivoire|DJ Djibouti|EK Equatorial Guinea|ER Eritrea|WZ Eswatini|ET Ethiopia|GB Gabon|"
              "GA Gambia|GH Ghana|GV Guinea|PU Guinea-Bissau|KE Kenya|LT Lesotho|LI Liberia|LY Libya|"
              "MA Madagascar|MI Malawi|ML Mali|MR Mauritania|MP Mauritius|MO Morocco|MZ Mozambique|"
              "WA Namibia|NG Niger|NI Nigeria|RW Rwanda|TP Sao Tome and Principe|SG Senegal|SE Seychelles|"
              "SL Sierra Leone|SO Somalia|SF South Africa|OD South Sudan|SU Sudan|TZ Tanzania|TO Togo|"
              "TS Tunisia|UG Uganda|ZA Zambia|ZI Zimbabwe|WI Western Sahara",
    "Asia-Pacific": "AF Afghanistan|BG Bangladesh|BT Bhutan|BX Brunei|CB Cambodia|CH China|HK Hong Kong|"
              "IN India|ID Indonesia|JA Japan|KN North Korea|KS South Korea|LA Laos|MY Malaysia|"
              "MV Maldives|MG Mongolia|BM Myanmar|NP Nepal|PK Pakistan|RP Philippines|SN Singapore|"
              "CE Sri Lanka|TW Taiwan|TH Thailand|TT Timor-Leste|VM Vietnam|AS Australia|NZ New Zealand|"
              "PP Papua New Guinea|FJ Fiji|BP Solomon Islands|NH Vanuatu|WS Samoa|TN Tonga|MC Macau",
    "Americas": "US United States|CA Canada|MX Mexico|GT Guatemala|BH Belize|HO Honduras|ES El Salvador|"
              "NU Nicaragua|CS Costa Rica|PM Panama|CU Cuba|HA Haiti|DR Dominican Republic|JM Jamaica|"
              "BF Bahamas|TD Trinidad and Tobago|BB Barbados|CO Colombia|VE Venezuela|EC Ecuador|PE Peru|"
              "BR Brazil|BL Bolivia|PA Paraguay|UY Uruguay|AR Argentina|CI Chile|GY Guyana|NS Suriname|"
              "RQ Puerto Rico|GL Greenland",
}
COUNTRIES = {e[:2]: (e[3:], region) for region, s in _R.items() for e in s.split("|")}


if __name__ == "__main__":
    update()
    from dashboard import build
    build()
    print(f"Dashboard written to {config.DASHBOARD_PATH}")
