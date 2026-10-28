"""Builds a self-contained HTML dashboard from risk.db. Run: python dashboard.py"""

import json
import sqlite3
from datetime import datetime, timezone

import config

LABELS = {
    "armed_conflict": "Armed conflict", "military_tension": "Military tension",
    "terrorism": "Terrorism", "political_instability": "Political instability",
    "sanctions_trade": "Sanctions & trade", "energy_resources": "Energy & resources",
    "diplomacy": "Diplomacy", "cyber_hybrid": "Cyber & hybrid", "humanitarian": "Humanitarian",
}


def load():
    from agent import connect  # also adds any newer columns to an older database
    import events
    db = connect()
    events.ensure_schema(db)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(
        "SELECT source, title, link, fetched_at, country, region, category, severity, reason, demo, "
        "energy_themes, chokepoint, energy_note, event_id FROM articles ORDER BY fetched_at DESC")]
    import forecasts
    extra = {"events": events.summarise(db), "changes": events.gdelt_changes(db), "fc": forecasts.summary(db)}
    try:
        run = db.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        run = dict(run) if run else None
    except sqlite3.OperationalError:
        run = None
    try:
        gdelt = [dict(r) for r in db.execute(
            "SELECT day, country, region, category, events, mentions, goldstein FROM gdelt_daily")]
    except sqlite3.OperationalError:  # GDELT not loaded yet
        gdelt = []
    db.close()
    return rows, gdelt, run, extra


def build():
    rows, gdelt, run, extra = load()
    data = {
        **extra,
        "run": run,
        "rows": rows,
        "gdelt": gdelt,
        "labels": LABELS,
        "energy": {k: label for k, (label, _) in config.ENERGY_THEMES.items()},
        "chokepoints": config.CHOKEPOINTS,
        "author": {"name": getattr(config, "AUTHOR_NAME", ""), "url": getattr(config, "AUTHOR_URL", "")},
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "demo": any(r["demo"] for r in rows),
    }
    html = TEMPLATE.replace("/*DATA*/null", json.dumps(data))
    with open(config.DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Geopolitical Risk Monitor</title>
<meta name="description" content="A daily, AI-assisted assessment of geopolitical risk from international news and GDELT conflict data.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<style>
:root{color-scheme:light;
--paper:#eef1f4;--surface:#ffffff;--ink:#172033;--ink2:#4b5568;--muted:#737c8f;--rule:#d9dee6;--grid:#e6e9ee;--axis:#c3c9d3;
--border:rgba(23,32,51,.10);--s1:#2a78d6;--crit:#c2362f;--warn:#fab219;--hover:#f3f5f8;
--q1:#cde2fb;--q2:#9ec5f4;--q3:#6da7ec;--q4:#3987e5;--q5:#256abf;--q6:#184f95;--q7:#0d366b;--hiink:#fff;
--serif:"Source Serif 4",Georgia,"Times New Roman",serif;--sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
--paper:#0e1218;--surface:#161b23;--ink:#e6e9ee;--ink2:#b3bac6;--muted:#858d9b;--rule:#2a313c;--grid:#232a34;--axis:#38404c;
--border:rgba(255,255,255,.08);--s1:#3987e5;--crit:#e5594f;--hover:#1c222b;
--q1:#104281;--q2:#184f95;--q3:#1c5cab;--q4:#256abf;--q5:#3987e5;--q6:#6da7ec;--q7:#9ec5f4;--hiink:#0e1218}}
:root[data-theme="dark"]{color-scheme:dark;
--paper:#0e1218;--surface:#161b23;--ink:#e6e9ee;--ink2:#b3bac6;--muted:#858d9b;--rule:#2a313c;--grid:#232a34;--axis:#38404c;
--border:rgba(255,255,255,.08);--s1:#3987e5;--crit:#e5594f;--hover:#1c222b;
--q1:#104281;--q2:#184f95;--q3:#1c5cab;--q4:#256abf;--q5:#3987e5;--q6:#6da7ec;--q7:#9ec5f4;--hiink:#0e1218}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans)}
a{color:inherit;text-decoration-color:var(--axis);text-underline-offset:2px}a:hover{text-decoration-color:currentColor}
:focus-visible{outline:2px solid var(--s1);outline-offset:2px;border-radius:3px}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
/* masthead */
.mast{padding:32px 0 18px;display:flex;flex-wrap:wrap;gap:16px;justify-content:space-between;align-items:flex-end}
.mast h1{font:600 32px/1.1 var(--serif);letter-spacing:-.01em;margin:0}
.mast .when{color:var(--ink2);margin:6px 0 0;font-size:14px}
.filters{display:flex;gap:8px;flex-wrap:wrap}
select{max-width:220px;font:inherit;font-size:14px;color:var(--ink);background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:6px 8px}
/* tabs */
.tabs{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--rule)}
.tabs .wrap{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}
.tab{font:500 15px var(--sans);color:var(--ink2);background:none;border:0;border-bottom:2px solid transparent;padding:12px 10px 10px;cursor:pointer;white-space:nowrap}
.tab:hover{color:var(--ink)}.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--ink)}
.tab .n{font-size:12px;color:var(--muted);margin-left:4px;font-variant-numeric:tabular-nums}
main.wrap{padding-top:24px;padding-bottom:48px}
.panel[hidden]{display:none}
/* blocks */
.block{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px 22px;margin-bottom:16px}
.block>h2,.sec-h{font:600 20px/1.25 var(--serif);margin:0 0 4px}
h3{font:600 15px/1.3 var(--sans);margin:0 0 6px;color:var(--ink)}
.note{color:var(--muted);font-size:13px;margin:0 0 14px;max-width:72ch}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid2>*{min-width:0}
@media (max-width:820px){.grid2{grid-template-columns:1fr}}
.banner{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--warn);border-radius:8px;padding:10px 14px;margin:0 0 16px;color:var(--ink2)}
/* lead */
.lead{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:0;padding:0;overflow:hidden}
@media (max-width:820px){.lead{grid-template-columns:1fr}}
.lead-main{padding:26px 28px 24px}
.lead-meta{display:flex;align-items:center;gap:10px;color:var(--ink2);font-size:14px}
.lead-h{font:600 clamp(26px,3.6vw,38px)/1.12 var(--serif);letter-spacing:-.015em;margin:12px 0 12px;max-width:22ch}
.lead-sum{font:400 17px/1.55 var(--serif);color:var(--ink2);margin:0 0 16px;max-width:60ch}
.lead-hl{list-style:none;margin:0;padding:0;border-top:1px solid var(--rule)}
.lead-hl li{padding:9px 0;border-bottom:1px solid var(--rule);font-size:14px}
.lead-hl .src{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.lead-side{background:var(--hover);padding:22px 22px 18px;border-left:1px solid var(--rule)}
@media (max-width:820px){.lead-side{border-left:0;border-top:1px solid var(--rule)}}
.lead-side h3{margin-bottom:10px}
/* change lists */
.chg{list-style:none;margin:0;padding:0}
.chg li{padding:9px 0;border-bottom:1px solid var(--rule);display:flex;gap:10px;align-items:baseline}
.chg li:last-child{border-bottom:0}
.chg .ic{width:14px;flex:none;text-align:center;font-size:12px}
.chg .t{font-weight:500;font-size:14px}.chg .d{color:var(--muted);font-size:12px}
/* stat strip */
.stats{display:grid;grid-template-columns:repeat(4,1fr);margin:0 0 16px;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.stats>div{padding:14px 16px;border-left:1px solid var(--rule)}.stats>div:first-child{border-left:0;padding-left:0}
.stats b{display:block;font:600 24px/1.2 var(--sans);font-variant-numeric:tabular-nums}
.stats span{color:var(--ink2);font-size:13px}
@media (max-width:640px){.stats{grid-template-columns:1fr 1fr}.stats>div:nth-child(3){border-left:0;padding-left:0}.stats>div:nth-child(n+3){border-top:1px solid var(--rule)}}
/* forecasts glance */
.fq{font:600 16px/1.35 var(--serif);margin:0}
.glance li{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:baseline}
.big-pct{font:600 20px var(--sans);font-variant-numeric:tabular-nums;text-align:right}
.big-pct small{display:block;font:400 12px var(--sans);color:var(--muted)}
.more{display:inline-block;margin-top:12px;font-size:14px;font-weight:500;color:var(--s1);background:none;border:0;padding:0;cursor:pointer;text-decoration:underline;text-underline-offset:3px}
/* tables */
.tw{overflow-x:auto}
table.list{width:100%;border-collapse:collapse;font-size:14px}
.list th{text-align:left;color:var(--muted);font-weight:500;font-size:12px;border-bottom:1px solid var(--axis);padding:6px 8px}
.list td{border-bottom:1px solid var(--rule);padding:10px 8px;vertical-align:top}
.list td.q{min-width:240px}
.sev{font-weight:600;white-space:nowrap;font-variant-numeric:tabular-nums}
.pct{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.sub{color:var(--muted);font-size:12px;margin-top:2px}
.pill{display:inline-block;font-size:11px;line-height:1.3;color:var(--ink2);border:1px solid var(--rule);border-radius:999px;padding:1px 7px;margin:4px 4px 0 0;white-space:nowrap}
.st{display:inline-block;font-size:12px;font-weight:500;border-radius:999px;padding:2px 9px;white-space:nowrap;border:1px solid var(--rule);color:var(--ink2);background:var(--surface)}
.st.up{color:var(--crit);border-color:var(--crit)}.st.new{color:var(--ink);border-color:var(--ink)}
.evrow{cursor:pointer}.evrow:hover td{background:var(--hover)}
.evrow .caret{color:var(--muted);font-size:11px;margin-left:6px}
.evd td{padding:2px 8px 14px;background:var(--hover)}
.evd ul{margin:0;padding-left:18px}.evd li{margin:4px 0;font-size:13px}
.spark{display:block}
/* collapsibles */
details.fold{background:var(--surface);border:1px solid var(--border);border-radius:8px;margin-bottom:16px}
details.fold>summary{list-style:none;cursor:pointer;padding:16px 22px;display:flex;justify-content:space-between;align-items:center;gap:12px}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary .sec-h{margin:0;font-size:18px}
details.fold>summary::after{content:"Show";font-size:14px;font-weight:500;color:var(--s1)}
details.fold[open]>summary::after{content:"Hide"}
details.fold>.body{padding:0 22px 18px}
details.inline summary{cursor:pointer;color:var(--ink2);font-size:13px;margin-top:4px}
details.inline p{margin:6px 0 0;font-size:13px;color:var(--ink2)}
/* charts */
svg{display:block;width:100%;height:auto;overflow:visible}
svg text{fill:var(--muted);font-size:11px;font-family:var(--sans)}
.tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:6px 9px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:9}
.heat{width:100%;border-collapse:separate;border-spacing:2px;font-size:12px}
.heat th{color:var(--ink2);font-weight:500;text-align:left;padding:4px}
.heat th.c{text-align:center;writing-mode:vertical-rl;transform:rotate(180deg);height:118px;vertical-align:bottom}
.heat td{text-align:center;border-radius:4px;height:30px;min-width:30px;color:var(--ink);font-variant-numeric:tabular-nums}
.legend{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11px;margin-top:8px}
.legend span{width:18px;height:10px;border-radius:2px;display:inline-block}
.choke{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0 20px}
.cp{border:1px solid var(--rule);border-radius:6px;padding:10px 12px;min-width:0}
.cp .n{font:600 22px/1.2 var(--sans);margin:2px 0;font-variant-numeric:tabular-nums}.cp .k{color:var(--ink2);font-size:12px}
.cp .h{font-size:12px;color:var(--ink2);overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.mini{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin:4px 0 20px}
code{font-size:12px;background:var(--grid);padding:1px 4px;border-radius:4px}
footer{color:var(--muted);font-size:13px;padding:8px 0 40px;border-top:1px solid var(--rule)}
footer p{margin:10px 0 0;max-width:80ch}
@media (prefers-reduced-motion:no-preference){.panel{animation:show .18s ease-out}@keyframes show{from{opacity:.4}to{opacity:1}}}
</style></head><body>
<div class="wrap"><header class="mast"><div><h1>Geopolitical Risk Monitor</h1><p class="when" id="when"></p></div>
<div class="filters"><select id="fRange" aria-label="Date range"><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option><option value="9999">All time</option></select>
<select id="fRegion" aria-label="Region"><option value="">All regions</option></select>
<select id="fLens" aria-label="Lens"><option value="">All risks</option><option value="*">Energy security</option></select></div></header></div>
<nav class="tabs" aria-label="Sections"><div class="wrap" role="tablist">
<button class="tab" role="tab" data-tab="overview">Overview</button>
<button class="tab" role="tab" data-tab="events">Events<span class="n" id="nEvents"></span></button>
<button class="tab" role="tab" data-tab="forecasts">Forecasts<span class="n" id="nFc"></span></button>
<button class="tab" role="tab" data-tab="energy">Energy</button>
<button class="tab" role="tab" data-tab="breakdown">Breakdown</button>
</div></nav>
<main class="wrap">
<div id="banner"></div>

<section class="panel" id="p-overview" role="tabpanel">
<div class="block lead"><div class="lead-main" id="lead"></div><div class="lead-side"><h3>Also moving</h3><ul class="chg" id="moving"></ul></div></div>
<div class="stats" id="stats"></div>
<div class="grid2" style="margin-bottom:16px">
<div class="block" style="margin:0"><h2>Unusual conflict activity</h2><p class="note">GDELT conflict events in the last 7 days compared with each country's own norm.</p><ul class="chg" id="chgGdelt"></ul></div>
<div class="block" style="margin:0"><h2>Next forecast deadlines</h2><p class="note">Probabilities that the answer will be yes.</p><ul class="chg glance" id="fcGlance"></ul><button class="more" data-go="forecasts">All forecasts and scores</button></div>
</div>
<div class="block"><h2>Daily risk index</h2><p class="note">Sum of severity across each day's distinct events, each story counted once at its highest severity.</p><div id="trend"></div></div>
<details class="fold" id="topFold"><summary><span class="sec-h" id="topTitle">Highest-severity headlines</span></summary><div class="body"><p class="note">Severity 4–5, newest first, one headline per event, with Claude's reason for the rating.</p><div id="top"></div></div></details>
</section>

<section class="panel" id="p-events" role="tabpanel" hidden>
<div class="block"><h2>Tracked events</h2>
<p class="note">Coverage grouped into distinct stories by Claude over the last 14 days. Select a row to see its headlines.</p>
<div id="events"></div>
<details class="inline"><summary>How status is decided</summary><p>Each event's last 3 days are compared with the 7 days before. <b>Escalating</b>: severity up at least a point (with 2+ reports) or coverage up 50% or more (with 4+ reports). <b>Cooling</b>: severity down a point or coverage halved. <b>New</b>: first reported in the last 3 days. <b>Quiet</b>: no reports in 3 days.</p></details></div>
</section>

<section class="panel" id="p-forecasts" role="tabpanel" hidden>
<div class="block"><h2>Forecasts</h2>
<p class="note">Each week the agent makes specific yes/no forecasts with deadlines. When a deadline passes it checks the news to see what happened, and every forecaster is scored with the Brier score: lower is better, 0 is perfect, and always saying 50% scores 0.25.</p>
<div class="mini" id="fcScore"></div>
<h3>Open</h3><div id="fcOpen"></div>
<h3 style="margin-top:22px">Resolved</h3><div id="fcDone"></div>
<details class="inline" style="margin-top:14px"><summary>Add your own forecasts</summary><p>Open <code>my_forecasts.csv</code> in the GitHub repository, select the pencil icon and add a line with the forecast ID and your probability, for example <code>F261022-1,35%</code>. Add <code>yes</code> or <code>no</code> as a third value to settle an outcome yourself. Your forecasts appear after the next daily run.</p></details></div>
</section>

<section class="panel" id="p-energy" role="tabpanel" hidden>
<div class="block"><h2>Energy security</h2>
<p class="note" id="enote">Headlines with an energy-security dimension, tagged by Claude on top of their main risk type.</p>
<h3>Chokepoint watch</h3><div class="choke" id="choke"></div>
<div class="grid2">
<div><h3>Energy items by theme</h3><p class="note">An item can carry more than one theme.</p><div id="ethemes"></div></div>
<div><h3>Daily energy risk index</h3><p class="note">Sum of severity across energy-tagged items each day.</p><div id="etrend"></div></div>
</div></div>
<details class="fold"><summary><span class="sec-h" id="eTitle">Energy headlines</span></summary><div class="body"><p class="note">Most severe first, with Claude's note on the energy implication.</p><div id="elist"></div></div></details>
</section>

<section class="panel" id="p-breakdown" role="tabpanel" hidden>
<div class="grid2" style="margin-bottom:16px">
<div class="block" style="margin:0"><h2>Events by risk type</h2><p class="note">Distinct events in the selected range.</p><div id="cats"></div></div>
<div class="block" style="margin:0"><h2>Region and risk type</h2><p class="note">Distinct events; darker means more.</p><div class="tw" id="heat"></div><div class="legend" id="hl"></div></div>
</div>
<div class="block"><h2>GDELT conflict events</h2><p class="note" id="glens" style="display:none">The energy lens applies to the headline analysis only; GDELT shows all conflict events.</p>
<p class="note">Daily count of conflict-type events (threats, protests, sanctions, attacks, fighting) machine-coded by GDELT from world news and reported by at least two sources. A larger, independent sample to set against the headline analysis.</p>
<div id="gtrend"></div></div>
<div class="grid2">
<div class="block" style="margin:0"><h2>Most conflict events by country</h2><p class="note">GDELT, selected range.</p><div id="gcountries"></div></div>
<div class="block" style="margin:0"><h2>Conflict events by risk type</h2><p class="note">GDELT, selected range.</p><div id="gcats"></div></div>
</div>
</section>
</main>
<div class="wrap"><footer id="foot"></footer></div>
<div class="tip" id="tip"></div>
<script>

const D=/*DATA*/null;
const $=id=>document.getElementById(id), tip=$('tip');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function showTip(e,h){tip.innerHTML=h;tip.style.display='block';const x=Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8);tip.style.left=x+'px';tip.style.top=(e.clientY+12)+'px'}
function hideTip(){tip.style.display='none'}
const day=s=>s.slice(0,10);
const dedupe=list=>{const m=new Map();list.forEach(r=>{const k=r.event_id||('a:'+r.fetched_at+r.title);const c=m.get(k);if(!c||r.severity>c.severity)m.set(k,r)});return [...m.values()]};
const themesOf=r=>(r.energy_themes||'').split(',').filter(Boolean);
Object.entries(D.energy||{}).forEach(([k,l])=>$('fLens').insertAdjacentHTML('beforeend',`<option value="${k}">Energy: ${esc(l)}</option>`));
const pills=r=>themesOf(r).map(t=>`<span class="pill">${esc((D.energy||{})[t]||t)}</span>`).join('')+(r.chokepoint?`<span class="pill">${esc(r.chokepoint)}</span>`:'');
const regions=[...new Set([...D.rows,...(D.gdelt||[])].map(r=>r.region).filter(Boolean))].sort();
regions.forEach(r=>$('fRegion').insertAdjacentHTML('beforeend',`<option>${esc(r)}</option>`));
(()=>{const a=D.author||{}, gh=location.hostname.endsWith('github.io')?`https://github.com/${location.hostname.split('.')[0]}/${location.pathname.split('/')[1]||''}`:'';
  $('when').textContent=`Updated ${D.generated}`+(a.name?`, by ${a.name}`:'');
  $('foot').innerHTML=`<p>Built with Claude, reading BBC World, Le Monde, Al Jazeera and The Guardian every morning, with GDELT conflict data for comparison.${gh?` <a href="${esc(gh)}">Method and source code</a>.`:''}${a.name?` Made by ${a.url?`<a href="${esc(a.url)}">${esc(a.name)}</a>`:esc(a.name)}.`:''}</p><p>Severity ratings, categories, event groupings and forecasts are model judgements and can be wrong. Check the original reporting before relying on them.</p>`;})();
if(D.run&&D.run.error)$('banner').innerHTML=`<div class="banner" style="border-left-color:var(--crit)"><b>News analysis failed on the last run</b> (${esc(new Date(D.run.started_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}))}). ${esc(D.run.error)} The GDELT section is unaffected.</div>`;
else if(D.demo)$('banner').innerHTML='<div class="banner"><b>Demo data.</b> These rows are synthetic placeholders, not real news. Run <code>python agent.py</code> with an API key to replace them.</div>';

function render(){
  const days=+$('fRange').value, reg=$('fRegion').value;
  const cutoff=new Date(Date.now()-days*864e5).toISOString();
  const lens=$('fLens').value;
  const inLens=r=>!lens||(lens==='*'?themesOf(r).length>0:themesOf(r).includes(lens));
  const base=D.rows.filter(r=>r.fetched_at>=cutoff&&(!reg||r.region===reg));
  const all=base.filter(inLens);
  const geoItems=all.filter(r=>r.category!=='not_geopolitical');
  const geo=dedupe(geoItems);
  $('glens').style.display=lens?'':'none';
  const hi=geo.filter(r=>r.severity>=4).length;
  const byReg={};geo.forEach(r=>byReg[r.region]=(byReg[r.region]||0)+r.severity);
  const topReg=Object.entries(byReg).sort((a,b)=>b[1]-a[1])[0];
  $('stats').innerHTML=[[all.length.toLocaleString(),'headlines read'],[geo.length.toLocaleString(),'distinct events'],[hi,'rated severity 4 or 5'],[topReg?topReg[0]:'–','carries the most risk']]
   .map(([v,k])=>`<div><b>${esc(v)}</b><span>${k}</span></div>`).join('');
  trend(geoItems,Math.min(days,60)); cats(geo); heat(geo); topList(geo);
  lead(reg,geo); changing(reg); fcRender(); eventsRender(reg);
  energyRender(base,lens,Math.min(days,60));
  gdeltRender(days,reg);
}

const ST={Escalating:['▲','up'],New:['●','new'],Steady:['–',''],Cooling:['▼',''],Quiet:['○','']};
const stPill=s=>`<span class="st ${ST[s][1]}">${ST[s][0]} ${s}</span>`;
const fmtDay=d=>new Date(d+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short'});
const pct=p=>p==null?'–':Math.round(p*100)+'%';

const evScore=e=>({Escalating:3,New:2,Steady:1,Cooling:0.5,Quiet:0}[e.status])+e.recent_severity+Math.min(e.recent_reports,12)/6;
const plural=(n,w)=>`${n} ${w}${n==1?'':'s'}`;

function lead(reg,geo){
  const ev=(D.events||[]).filter(e=>(!reg||e.region===reg)&&e.status!=='Quiet').sort((a,b)=>evScore(b)-evScore(a));
  const L=ev[0];
  if(!L){
    const h=[...geo].sort((a,b)=>b.severity-a.severity)[0];
    $('lead').innerHTML=h?`<div class="lead-meta"><span>${esc(h.country)}</span></div><h2 class="lead-h">${esc(h.title)}</h2><p class="lead-sum">${esc(h.reason||'')}</p>`
      :'<h2 class="lead-h">No reports yet</h2><p class="lead-sum">The first assessment appears after the next daily run.</p>';
    $('moving').innerHTML='<li><span class="d">Events appear once headlines have been grouped.</span></li>';return;
  }
  const hl=L.headlines.slice(0,3);
  $('lead').innerHTML=`<div class="lead-meta">${stPill(L.status)}<span>${esc(L.country)}</span></div>
    <h2 class="lead-h">${esc(L.name)}</h2>
    <p class="lead-sum">${plural(L.recent_reports,'report')} in the last three days and ${L.reports} in total, from ${plural(L.sources,'outlet')}. Highest severity recently: ${L.recent_severity} out of 5. First reported ${fmtDay(L.first_seen)}.</p>
    <ul class="lead-hl">${hl.map(h=>`<li>${h.link?`<a href="${esc(h.link)}" target="_blank" rel="noopener">${esc(h.title)}</a>`:esc(h.title)}<span class="src">${esc(h.source)}, ${fmtDay(h.day)}</span></li>`).join('')}</ul>`;
  const mv=ev.slice(1).filter(e=>e.status==='Escalating'||e.status==='New'||(e.status==='Cooling'&&e.max_severity>=3)).slice(0,6);
  $('moving').innerHTML=mv.map(e=>`<li><span class="ic" style="color:${e.status==='Escalating'?'var(--crit)':'var(--ink2)'}" aria-hidden="true">${ST[e.status][0]}</span><div><div class="t">${esc(e.name)}</div><div class="d">${e.status} in ${esc(e.country)}, ${plural(e.recent_reports,'report')} in 3 days</div></div></li>`).join('')
    ||'<li><span class="d">Nothing else is moving sharply.</span></li>';
}

function changing(reg){
  const c=D.changes||{};
  if(!c.ready){$('chgGdelt').innerHTML=`<li><span class="d">Building a baseline: this needs 21 days of GDELT data and has ${7+(c.baseline_days||0)}.</span></li>`;return}
  const r=(c.rising||[]).filter(x=>!reg||x.region===reg).slice(0,4), f=(c.falling||[]).filter(x=>!reg||x.region===reg).slice(0,2);
  const g=(x,up)=>`<li><span class="ic" style="color:${up?'var(--crit)':'var(--ink2)'}" aria-hidden="true">${up?'▲':'▼'}</span><div style="flex:1"><div class="t">${esc(x.country)}</div><div class="d">${x.recent_per_day} events a day against a usual ${x.baseline_per_day}${x.driver?', mostly '+esc((D.labels[x.driver]||x.driver).toLowerCase()):''}</div></div><span class="pct">${x.ratio>=1?x.ratio.toFixed(1)+'×':'−'+Math.round((1-x.ratio)*100)+'%'}</span></li>`;
  $('chgGdelt').innerHTML=(r.map(x=>g(x,1)).join('')+f.map(x=>g(x,0)).join(''))||'<li><span class="d">Nothing unusual in the last 7 days.</span></li>';
}

function fcRender(){
  const F=(D.fc||{}).forecasts||[], S=(D.fc||{}).score||{};
  const tile=(k,v,sub)=>`<div class="cp"><div class="k">${k}</div><div class="n">${v}</div><div class="k">${sub}</div></div>`;
  $('fcScore').innerHTML=tile('Open',S.open||0,'awaiting their deadline')+tile('Resolved',S.resolved||0,'scored so far')
    +tile("Claude's Brier score",S.ai==null?'–':S.ai.toFixed(3),S.resolved?`over ${plural(S.resolved,'forecast')}`:'none resolved yet')
    +tile('Your Brier score',S.me==null?'–':S.me.toFixed(3),S.mine_count?`Claude scored ${S.ai_on_mine.toFixed(3)} on the same ${S.mine_count}`:'add yours in my_forecasts.csv');
  const open=F.filter(f=>f.status==='open').sort((a,b)=>a.deadline<b.deadline?-1:1), done=F.filter(f=>f.status!=='open');
  $('nFc').textContent=open.length||'';
  $('fcGlance').innerHTML=open.slice(0,3).map(f=>`<li><div><p class="fq">${esc(f.question)}</p><div class="d">By ${fmtDay(f.deadline)}</div></div><div class="big-pct">${pct(f.probability)}<small>Claude${f.my_probability!=null?`, you ${pct(f.my_probability)}`:''}</small></div></li>`).join('')
    ||'<li><span class="d">The first forecasts are made on the next daily run.</span></li>';
  $('fcOpen').innerHTML=open.length?'<div class="tw"><table class="list"><tr><th>Question</th><th>Deadline</th><th>Claude</th><th>You</th></tr>'+open.map(f=>
    `<tr><td class="q"><p class="fq">${esc(f.question)}</p><details class="inline"><summary>Criteria and reasoning</summary><p><b>Yes if:</b> ${esc(f.criteria)}</p><p><b>Reasoning:</b> ${esc(f.rationale)}</p><p>ID for my_forecasts.csv: <code>${esc(f.id)}</code></p></details></td><td style="white-space:nowrap">${fmtDay(f.deadline)}</td><td class="pct">${pct(f.probability)}</td><td class="pct">${pct(f.my_probability)}</td></tr>`).join('')+'</table></div>'
    :'<p class="note">The first forecasts are made on the next daily run.</p>';
  $('fcDone').innerHTML=done.length?'<div class="tw"><table class="list"><tr><th>Question</th><th>Outcome</th><th>Claude</th><th>You</th></tr>'+done.map(f=>
    `<tr><td class="q">${esc(f.question)}${f.resolution_note?`<div class="sub">${esc(f.resolution_note)}</div>`:''}</td><td><b>${f.status==='unresolvable'?'Unresolved':f.outcome?'Yes':'No'}</b></td><td class="pct">${pct(f.probability)}${f.brier_ai!=null?`<div class="sub">Brier ${f.brier_ai.toFixed(2)}</div>`:''}</td><td class="pct">${pct(f.my_probability)}${f.brier_me!=null?`<div class="sub">Brier ${f.brier_me.toFixed(2)}</div>`:''}</td></tr>`).join('')+'</table></div>'
    :'<p class="note">None yet. Forecasts resolve 2 to 8 weeks after they are made.</p>';
}

function spark(d){const W=84,H=22,m=Math.max(1,...d),bw=W/d.length;return `<svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">${d.map((v,i)=>v?`<rect x="${i*bw+0.5}" y="${H-Math.max(2,H*v/m)}" width="${bw-1.5}" height="${Math.max(2,H*v/m)}" rx="1" fill="var(--s1)"/>`:`<rect x="${i*bw+0.5}" y="${H-1}" width="${bw-1.5}" height="1" fill="var(--grid)"/>`).join('')}</svg>`}

let showAllEvents=false;
function eventsRender(reg){
  const all=(D.events||[]).filter(e=>!reg||e.region===reg);
  $('nEvents').textContent=all.filter(e=>e.status!=='Quiet').length||'';
  const ev=showAllEvents?all:all.slice(0,12);
  $('events').innerHTML=ev.length?'<div class="tw"><table class="list"><tr><th>Status</th><th>Event</th><th>Reports</th><th>Max severity</th><th>Last 14 days</th></tr>'+ev.map((e,i)=>
    `<tr class="evrow" data-i="${i}" tabindex="0" aria-expanded="false"><td>${stPill(e.status)}</td><td class="q"><b>${esc(e.name)}</b><span class="caret" aria-hidden="true">▾</span><div class="sub">${esc(e.country)}, ${plural(e.sources,'outlet')}, since ${fmtDay(e.first_seen)}</div></td><td class="pct">${e.reports}<div class="sub" style="font-weight:400">${e.recent_reports} in 3 days</div></td><td class="pct" style="color:${e.max_severity>=5?'var(--crit)':'var(--ink)'}">${e.max_severity>=5?'▲ ':''}${e.max_severity}</td><td>${spark(e.daily)}</td></tr>
     <tr class="evd" id="evd${i}" hidden><td></td><td colspan="4"><ul>${e.headlines.map(h=>`<li>${h.link?`<a href="${esc(h.link)}" target="_blank" rel="noopener">${esc(h.title)}</a>`:esc(h.title)} <span class="sub" style="display:inline">${esc(h.source)}, ${fmtDay(h.day)}</span></li>`).join('')}</ul></td></tr>`).join('')+'</table></div>'
      +(all.length>12?`<button class="more" id="evAll">${showAllEvents?'Show the top 12 only':`Show all ${all.length} events`}</button>`:'')
    :'<p class="note">Events appear here after the next daily run groups the headlines.</p>';
  $('events').querySelectorAll('.evrow').forEach(r=>{const t=()=>{const d=$('evd'+r.dataset.i);d.hidden=!d.hidden;r.setAttribute('aria-expanded',String(!d.hidden))};
    r.onclick=t;r.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();t()}}});
  if($('evAll'))$('evAll').onclick=()=>{showAllEvents=!showAllEvents;eventsRender(reg)};
}

function energyRender(base,lens,n){
  const geoAll=base.filter(r=>r.category!=='not_geopolitical');
  const untagged=base.filter(r=>r.energy_themes==null).length;
  let e=base.filter(r=>themesOf(r).length);
  if(lens&&lens!=='*')e=e.filter(r=>themesOf(r).includes(lens));
  const share=geoAll.length?Math.round(100*geoAll.filter(r=>themesOf(r).length).length/geoAll.length):0;
  $('enote').textContent=`Headlines with an energy-security dimension, tagged by Claude on top of their main risk type. ${share}% of geopolitical items in this range have an energy angle.`+(untagged?` ${untagged} older items are still waiting to be tagged.`:'');
  // chokepoints
  $('choke').innerHTML=(D.chokepoints||[]).map(c=>{
    const items=e.filter(r=>r.chokepoint===c), mx=Math.max(0,...items.map(r=>r.severity));
    const latest=items[0];
    return `<div class="cp"><div class="k">${esc(c)}</div><div class="n">${items.length}</div>
      <div class="k" style="margin-bottom:4px">${items.length?`items, highest severity <b style="color:${mx>=5?'var(--crit)':'var(--ink)'}">${mx>=5?'▲ ':''}${mx}</b>`:'no items in range'}</div>
      ${latest?`<div class="h">${latest.link?`<a href="${esc(latest.link)}" target="_blank" rel="noopener">${esc(latest.title)}</a>`:esc(latest.title)}</div>`:''}</div>`}).join('');
  // themes
  const byT=Object.keys(D.energy||{}).map(k=>[D.energy[k],e.filter(r=>themesOf(r).includes(k)).length]).filter(d=>!(lens&&lens!=='*')||d[1]).sort((a,b)=>b[1]-a[1]);
  barChart('ethemes',byT,'Energy items by theme',180);
  // trend
  const ds=span(n,firstDay);
  lineChart('etrend',ds,ds.map(d=>e.filter(r=>day(r.fetched_at)===d).reduce((a,r)=>a+r.severity,0)),(d,v)=>`Energy risk index ${v}, ${plural(e.filter(r=>day(r.fetched_at)===d).length,'item')}`,'Daily energy risk index line chart',520);
  // list
  const t=[...e].sort((a,b)=>b.severity-a.severity||(b.fetched_at>a.fetched_at?1:-1)).slice(0,30);
  $('eTitle').textContent=`Energy headlines (${t.length})`;
  $('elist').innerHTML=t.length?'<div class="tw"><table class="list"><tr><th>Severity</th><th>Headline</th><th>Where</th><th>Source</th></tr>'+t.map(r=>
   `<tr><td class="sev" style="color:${r.severity>=5?'var(--crit)':'var(--ink)'}">${r.severity>=5?'▲ ':''}${r.severity}</td>
    <td class="q">${r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}${r.energy_note&&!r.demo?`<div class="sub">${esc(r.energy_note)}</div>`:''}<div>${pills(r)}</div></td>
    <td>${esc(r.country)}</td><td>${esc(r.source)}</td></tr>`).join('')+'</table></div>':'<p class="note">No energy-tagged items in this range.</p>';
}

function gdeltRender(days,reg){
  const n=Math.min(days,60);
  const cutoff=new Date(Date.now()-n*864e5).toISOString().slice(0,10);
  const g=(D.gdelt||[]).filter(r=>r.day>=cutoff&&(!reg||r.region===reg));
  if(!g.length){['gtrend','gcountries','gcats'].forEach(id=>$(id).innerHTML='<p class="note">No GDELT data yet. It is added on the next daily run.</p>');return}
  const ds=[];for(let i=n;i>=1;i--)ds.push(new Date(Date.now()-i*864e5).toISOString().slice(0,10));
  const byDay={};g.forEach(r=>byDay[r.day]=(byDay[r.day]||0)+r.events);
  const loaded=new Set(g.map(r=>r.day));
  lineChart('gtrend',ds,ds.map(d=>loaded.has(d)?byDay[d]||0:null),(d,v)=>`${v==null?'Not loaded':v.toLocaleString()+' events'}`,'GDELT daily conflict events line chart');
  const byC={};g.forEach(r=>byC[r.country]=(byC[r.country]||0)+r.events);
  barChart('gcountries',Object.entries(byC).sort((a,b)=>b[1]-a[1]).slice(0,10),'Top countries by GDELT conflict events');
  const byK={};g.forEach(r=>byK[r.category]=(byK[r.category]||0)+r.events);
  barChart('gcats',Object.entries(byK).sort((a,b)=>b[1]-a[1]).map(([k,v])=>[D.labels[k]||k,v]),'GDELT events by risk type');
}

function lineChart(id,ds,v,tipText,label,W=1000){
  const H=W<700?260:220,P={l:48,r:12,t:12,b:26};
  const vals=v.filter(x=>x!=null),max=Math.max(5,...vals);
  const raw=max/4,mag=Math.pow(10,Math.floor(Math.log10(raw))),stp=[1,2,5,10].map(m=>m*mag).find(s=>s>=raw),nice=stp*4;
  const x=i=>P.l+(ds.length<2?0:i*(W-P.l-P.r)/(ds.length-1)), y=t=>P.t+(H-P.t-P.b)*(1-t/nice);
  let g='';for(let k=0;k<=4;k++){const t=nice*k/4;g+=`<line x1="${P.l}" x2="${W-P.r}" y1="${y(t)}" y2="${y(t)}" stroke="var(--${k?'grid':'axis'})"/><text x="${P.l-6}" y="${y(t)+4}" text-anchor="end" style="font-variant-numeric:tabular-nums">${t>=1000?(t/1000)+'k':t}</text>`}
  const step=Math.ceil(ds.length/(W<700?4:8));ds.forEach((d,i)=>{if((i%step===0&&ds.length-1-i>=step/2)||i===ds.length-1)g+=`<text x="${x(i)}" y="${H-6}" text-anchor="${i===ds.length-1?'end':'middle'}">${new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short'})}</text>`});
  let path='',pen=false;v.forEach((t,i)=>{if(t==null){pen=false;return}path+=(pen?'L':'M')+x(i)+','+y(t);pen=true});
  $(id).innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}">${g}
   <path d="${path}" fill="none" stroke="var(--s1)" stroke-width="2" stroke-linejoin="round"/>
   <line class="xh" y1="${P.t}" y2="${H-P.b}" stroke="var(--axis)" style="display:none"/><circle class="dot" r="4.5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2" style="display:none"/>
   <rect x="${P.l}" y="0" width="${W-P.l-P.r}" height="${H}" fill="transparent" class="hit"/></svg>`;
  const svg=$(id).querySelector('svg'),xh=svg.querySelector('.xh'),dot=svg.querySelector('.dot'),hit=svg.querySelector('.hit');
  hit.onmousemove=e=>{const b=svg.getBoundingClientRect(),px=(e.clientX-b.left)*W/b.width;
    const i=Math.max(0,Math.min(ds.length-1,Math.round((px-P.l)/((W-P.l-P.r)/Math.max(1,ds.length-1)))));
    xh.setAttribute('x1',x(i));xh.setAttribute('x2',x(i));xh.style.display='';
    if(v[i]!=null){dot.setAttribute('cx',x(i));dot.setAttribute('cy',y(v[i]));dot.style.display=''}else dot.style.display='none';
    showTip(e,`<b>${new Date(ds[i]).toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'})}</b><br>${tipText(ds[i],v[i])}`)};
  hit.onmouseleave=()=>{hideTip();xh.style.display='none';dot.style.display='none'};
}

function barChart(id,c,label,L=150){
  const max=Math.max(1,...c.map(d=>d[1])),W=500,row=26,H=Math.max(row,c.length*row);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}">`;
  c.forEach(([k,n],i)=>{const w=Math.max(n?3:0,(W-L-56)*n/max),yy=i*row;
    s+=`<g class="b" data-t="${esc(k)}: ${n.toLocaleString()}"><rect x="0" y="${yy}" width="${W}" height="${row}" fill="transparent"/>
    <text x="${L-8}" y="${yy+17}" text-anchor="end" style="fill:var(--ink2)">${esc(k)}</text>
    ${n?`<path d="M${L},${yy+5}h${Math.max(0,w-4)}a4,4 0 0 1 4,4v8a4,4 0 0 1 -4,4h-${Math.max(0,w-4)}z" fill="var(--s1)"/>`:''}
    <text x="${L+w+6}" y="${yy+17}" style="fill:var(--ink2);font-variant-numeric:tabular-nums">${n.toLocaleString()}</text></g>`});
  $(id).innerHTML=s+'</svg>';
  $(id).querySelectorAll('.b').forEach(g=>{g.onmousemove=e=>showTip(e,esc(g.dataset.t));g.onmouseleave=hideTip});
}

// Days to plot: the last n days, but starting no earlier than the first day with data.
function span(n,first){const ds=[];for(let i=n-1;i>=0;i--)ds.push(new Date(Date.now()-i*864e5).toISOString().slice(0,10));
  const k=first?ds.findIndex(d=>d>=first):0;return k>0?ds.slice(Math.min(k,ds.length-2)):ds}
const firstDay=D.rows.length?day(D.rows[D.rows.length-1].fetched_at):null;

function trend(geo,n){
  const ds=span(n,firstDay);
  const v=ds.map(d=>dedupe(geo.filter(r=>day(r.fetched_at)===d)).reduce((a,r)=>a+r.severity,0));
  lineChart('trend',ds,v,(d,x)=>`Risk index ${x}, ${plural(dedupe(geo.filter(r=>day(r.fetched_at)===d)).length,'event')}`,'Daily risk index line chart');
}

function cats(geo){
  const c=Object.keys(D.labels).map(k=>[k,geo.filter(r=>r.category===k).length]).sort((a,b)=>b[1]-a[1]);
  const max=Math.max(1,...c.map(d=>d[1])),W=500,row=26,L=140,H=c.length*row;
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Events by risk type bar chart">`;
  c.forEach(([k,n],i)=>{const w=Math.max(n?3:0,(W-L-40)*n/max),yy=i*row;
    s+=`<g class="b" data-t="${esc(D.labels[k])}: ${n}"><rect x="0" y="${yy}" width="${W}" height="${row}" fill="transparent"/>
    <text x="${L-8}" y="${yy+17}" text-anchor="end" style="fill:var(--ink2)">${esc(D.labels[k])}</text>
    <path d="M${L},${yy+5}h${Math.max(0,w-4)}a4,4 0 0 1 4,4v8a4,4 0 0 1 -4,4h-${Math.max(0,w-4)}z" fill="var(--s1)"/>
    <text x="${L+w+6}" y="${yy+17}" style="fill:var(--ink2);font-variant-numeric:tabular-nums">${n}</text></g>`});
  $('cats').innerHTML=s+'</svg>';
  $('cats').querySelectorAll('.b').forEach(g=>{g.onmousemove=e=>showTip(e,esc(g.dataset.t));g.onmouseleave=hideTip});
}

function heat(geo){
  const regs=[...new Set(geo.map(r=>r.region))].sort(), ks=Object.keys(D.labels);
  const cnt=(r,k)=>geo.filter(x=>x.region===r&&x.category===k).length;
  const max=Math.max(1,...regs.flatMap(r=>ks.map(k=>cnt(r,k))));
  const shade=n=>n?`var(--q${Math.min(7,1+Math.floor(6*n/max))})`:'transparent';
  let h='<table class="heat"><tr><th></th>'+ks.map(k=>`<th class="c">${esc(D.labels[k])}</th>`).join('')+'</tr>';
  regs.forEach(r=>{h+=`<tr><th>${esc(r)}</th>`+ks.map(k=>{const n=cnt(r,k),dark=n/max>0.55;
    return `<td title="${esc(r)}, ${esc(D.labels[k])}: ${n}" style="background:${shade(n)};${n?'':'border:1px solid var(--grid);'}${dark?'color:var(--hiink)':''}">${n||''}</td>`}).join('')+'</tr>'});
  $('heat').innerHTML=regs.length?h+'</table>':'<p class="note">No data in this range.</p>';
  $('hl').innerHTML='Fewer '+[1,2,3,4,5,6,7].map(i=>`<span style="background:var(--q${i})"></span>`).join('')+' More';
}

function topList(geo){
  const t=geo.filter(r=>r.severity>=4).slice(0,20);
  $('topTitle').textContent=`Highest-severity headlines (${t.length})`;
  $('top').innerHTML=t.length?'<div class="tw"><table class="list"><tr><th>Severity</th><th>Headline</th><th>Where</th><th>Type</th></tr>'+t.map(r=>
   `<tr><td class="sev" style="color:${r.severity>=5?'var(--crit)':'var(--ink)'}">${r.severity>=5?'▲ ':''}${r.severity}</td>
    <td class="q">${r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}<div class="sub">${esc(r.source)}, ${fmtDay(day(r.fetched_at))}</div>${r.reason&&!r.demo?`<div class="sub">${esc(r.reason)}</div>`:''}${themesOf(r).length?`<div>${pills(r)}</div>`:''}</td>
    <td>${esc(r.country)}</td><td>${esc(D.labels[r.category])}</td></tr>`).join('')+'</table></div>':'<p class="note">None in this range.</p>';
}

// tabs: remember the open tab in the address (#forecasts etc.)
const TABS=['overview','events','forecasts','energy','breakdown'];
function openTab(name,push){
  if(!TABS.includes(name))name='overview';
  document.querySelectorAll('.tab').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===name)));
  TABS.forEach(t=>$('p-'+t).hidden=t!==name);
  if(push)history.replaceState(null,'','#'+name);
}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{openTab(b.dataset.tab,true);window.scrollTo({top:0})});
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>{openTab(b.dataset.go,true);window.scrollTo({top:0})});
openTab(location.hash.slice(1));
window.addEventListener('hashchange',()=>openTab(location.hash.slice(1)));

$('fRange').onchange=render;$('fRegion').onchange=render;$('fLens').onchange=render;render();
</script></body></html>"""

if __name__ == "__main__":
    build()
    print(f"Dashboard written to {config.DASHBOARD_PATH}")
