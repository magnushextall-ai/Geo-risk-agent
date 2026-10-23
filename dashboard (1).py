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
<style>
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--s1:#2a78d6;--crit:#d03b3b;--warn:#fab219;
--q1:#cde2fb;--q2:#9ec5f4;--q3:#6da7ec;--q4:#3987e5;--q5:#256abf;--q6:#184f95;--q7:#0d366b;--hiink:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;
--q1:#104281;--q2:#184f95;--q3:#1c5cab;--q4:#256abf;--q5:#3987e5;--q6:#6da7ec;--q7:#9ec5f4;--hiink:#0b0b0b}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;
--q1:#104281;--q2:#184f95;--q3:#1c5cab;--q4:#256abf;--q5:#3987e5;--q6:#6da7ec;--q7:#9ec5f4;--hiink:#0b0b0b}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1120px;margin:0 auto;padding:28px 16px 48px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:12px;margin-bottom:20px}
h1{font-size:24px;margin:0 0 4px;letter-spacing:-.01em} h2{font-size:15px;margin:0 0 2px}
.sub{color:var(--ink2);margin:0}.note{color:var(--muted);font-size:12px;margin:0 0 12px}
.banner{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--warn);border-radius:8px;padding:10px 14px;margin-bottom:16px;color:var(--ink2)}
.filters{display:flex;gap:8px;flex-wrap:wrap}
select{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 8px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:12px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}
.tile .v{font-size:30px;font-weight:600;margin-top:4px}.tile .k{color:var(--ink2)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.grid2>*{min-width:0}
@media (max-width:820px){.grid2{grid-template-columns:1fr}}
svg{display:block;width:100%;height:auto;overflow:visible}
svg text{fill:var(--muted);font-size:11px}
.tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--border);
border-radius:6px;padding:6px 9px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:9}
.heat{width:100%;border-collapse:separate;border-spacing:2px;font-size:12px}
.heat th{color:var(--ink2);font-weight:500;text-align:left;padding:4px}
.heat th.c{text-align:center;writing-mode:vertical-rl;transform:rotate(180deg);height:118px;vertical-align:bottom}
.heat td{text-align:center;border-radius:4px;height:30px;min-width:30px;color:var(--ink);font-variant-numeric:tabular-nums}
.heatwrap{overflow-x:auto}
table.list{width:100%;border-collapse:collapse}
.list th{text-align:left;color:var(--ink2);font-weight:500;border-bottom:1px solid var(--axis);padding:6px 8px}
.list td:nth-child(2){min-width:220px}.list td{border-bottom:1px solid var(--grid);padding:8px;vertical-align:top}
.list a{color:var(--ink)}.sev{font-weight:600;white-space:nowrap}
.pill{display:inline-block;font-size:11px;line-height:1.3;color:var(--ink2);border:1px solid var(--border);border-radius:999px;padding:1px 7px;margin:3px 4px 0 0;white-space:nowrap}
.choke{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0 16px}
.cp{border:1px solid var(--border);border-radius:8px;padding:10px 12px;min-width:0}
.cp .n{font-size:22px;font-weight:600;margin:2px 0}.cp .k{color:var(--ink2);font-size:12px}
.cp .h{font-size:12px;color:var(--ink2);overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.cp .h a{color:var(--ink2)}
h3{font-size:13px;margin:0;color:var(--ink2);font-weight:600}
.lensnote{font-size:12px;color:var(--muted);margin:0 0 8px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media (max-width:820px){.two{grid-template-columns:1fr}}
.two>*{min-width:0}
.chg{list-style:none;margin:8px 0 0;padding:0}
.chg li{padding:8px 0;border-bottom:1px solid var(--grid);display:flex;gap:10px;align-items:baseline}
.chg li:last-child{border-bottom:0}
.chg .ic{width:16px;flex:none;text-align:center;font-weight:700}
.chg .t{font-weight:600}.chg .d{color:var(--ink2);font-size:12px}
.st{display:inline-block;font-size:11px;font-weight:600;border-radius:999px;padding:2px 8px;white-space:nowrap;border:1px solid var(--border);color:var(--ink2)}
.st.up{color:var(--crit);border-color:var(--crit)}.st.new{color:var(--ink);border-color:var(--ink)}
.mini{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0 14px}
.mini .cp .n{font-size:22px}
.evrow{cursor:pointer}.evrow:hover td{background:var(--grid)}
.evrow td:first-child{white-space:nowrap}
.evd td{padding:4px 8px 12px}
.evd ul{margin:0;padding-left:18px}.evd li{margin:3px 0;font-size:13px}
.spark{display:block}
.pct{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
details summary{cursor:pointer;color:var(--ink2);font-size:13px;margin-top:10px}
code{font-size:12px;background:var(--grid);padding:1px 4px;border-radius:4px}
.legend{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11px;margin-top:8px}
.legend span{width:18px;height:10px;border-radius:2px;display:inline-block}
</style></head><body><main>
<header><div><h1>Geopolitical Risk Monitor</h1>
<p class="sub">Headlines from major outlets, classified by Claude into risk type, region and severity (0–5).</p></div>
<div class="filters"><select id="fRange"><option value="7">Last 7 days</option><option value="30" selected>Last 30 days</option><option value="9999">All time</option></select>
<select id="fRegion"><option value="">All regions</option></select>
<select id="fLens" aria-label="Lens"><option value="">Lens: all risks</option><option value="*">Lens: energy security</option></select></div></header>
<div id="banner"></div>
<section class="tiles" id="tiles"></section>
<section class="card" style="margin-bottom:12px"><h2>What's changing</h2>
<p class="note">Compared with each story's and each country's own recent history, not with each other.</p>
<div class="two"><div><h3>News events</h3><ul class="chg" id="chgNews"></ul></div>
<div><h3>Unusual conflict activity (GDELT)</h3><ul class="chg" id="chgGdelt"></ul></div></div></section>
<section class="card" style="margin-bottom:12px"><h2>Forecasts</h2>
<p class="note">Each week the agent makes specific yes/no forecasts with deadlines. When a deadline passes it checks the news to see what happened, and every forecaster is scored. Brier score: lower is better; 0 is perfect, always saying 50% scores 0.25.</p>
<div class="mini" id="fcScore"></div>
<h3>Open forecasts</h3><div id="fcOpen"></div>
<h3 style="margin-top:16px">Resolved</h3><div id="fcDone"></div>
<details><summary>How to add your own forecasts</summary><p class="note" style="margin-top:6px">Open <code>my_forecasts.csv</code> in the GitHub repository, click the pencil icon, and add a line with the forecast ID and your probability, for example <code>F261022-1,35%</code>. Add <code>yes</code> or <code>no</code> as a third value to settle an outcome yourself. Your forecasts appear here after the next daily run.</p></details></section>
<section class="card" style="margin-bottom:12px"><h2>Tracked events</h2>
<p class="note">Coverage grouped into distinct stories by Claude, over the last 14 days. Click a row to see its headlines. Status compares the last 3 days with the 7 before: <b>Escalating</b> = severity up by at least a point (with 2+ reports) or coverage up 50%+ (with 4+ reports); <b>Cooling</b> = severity down a point or coverage halved; <b>New</b> = first reported in the last 3 days; <b>Quiet</b> = no reports in 3 days.</p>
<div id="events"></div></section>
<section class="card" style="margin-bottom:12px"><h2>Daily risk index</h2>
<p class="note">Sum of severity across each day's distinct events (each story counted once, at its highest severity). Higher means more, or more serious, events.</p><div id="trend"></div></section>
<section class="grid2">
<div class="card"><h2>Events by risk type</h2><p class="note">Distinct events</p><div id="cats"></div></div>
<div class="card"><h2>Region × risk type</h2><p class="note">Distinct events; darker = more</p><div class="heatwrap" id="heat"></div><div class="legend" id="hl"></div></div>
</section>
<section class="card" style="margin-bottom:12px"><h2>Energy security lens</h2>
<p class="note" id="enote">Headlines with an energy-security dimension, tagged by Claude on top of their main risk type.</p>
<h3>Chokepoint watch</h3><div class="choke" id="choke"></div>
<div class="grid2" style="margin-bottom:16px">
<div><h3>Energy items by theme</h3><p class="note">An item can carry more than one theme</p><div id="ethemes"></div></div>
<div><h3>Daily energy risk index</h3><p class="note">Sum of severity across energy-tagged items each day</p><div id="etrend"></div></div>
</div>
<h3>Energy-tagged items</h3><p class="note">Most severe first, with Claude's note on the energy implication</p><div id="elist"></div></section>
<section class="card" style="margin-bottom:12px"><h2>GDELT conflict events</h2><p class="lensnote" id="glens" style="display:none">The energy lens applies to the headline analysis only; GDELT shows all conflict events.</p>
<p class="note">Daily count of conflict-type events (threats, protests, sanctions, attacks, fighting) machine-coded by GDELT from world news, reported by at least two sources. A larger, independent sample to compare with the headline analysis above.</p>
<div id="gtrend"></div></section>
<section class="grid2">
<div class="card"><h2>GDELT: most conflict events by country</h2><p class="note">Total events in the selected range</p><div id="gcountries"></div></div>
<div class="card"><h2>GDELT: events by risk type</h2><p class="note">Total events in the selected range</p><div id="gcats"></div></div>
</section>
<section class="card"><h2>Highest-severity items</h2><p class="note">Severity 4–5, newest first, one headline per event</p><div id="top"></div></section>
<p class="note" id="foot" style="margin-top:16px"></p>
</main><div class="tip" id="tip"></div>
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
$('foot').textContent=`Generated ${D.generated}. Severity and categories are model judgements and can be wrong; check sources before relying on them.`;
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
  // tiles
  const hi=geo.filter(r=>r.severity>=4).length;
  const byReg={};geo.forEach(r=>byReg[r.region]=(byReg[r.region]||0)+r.severity);
  const topReg=Object.entries(byReg).sort((a,b)=>b[1]-a[1])[0];
  const avg=geo.length?(geo.reduce((a,r)=>a+r.severity,0)/geo.length).toFixed(1):'–';
  $('tiles').innerHTML=[['Headlines analysed',all.length],['Distinct events',geo.length],['High-severity events',hi],['Avg severity',avg],['Most at-risk region',topReg?topReg[0]:'–']]
   .map(([k,v])=>`<div class="card tile"><div class="k">${k}</div><div class="v" style="${String(v).length>8?'font-size:20px':''}">${esc(v)}</div></div>`).join('');
  trend(geoItems,Math.min(days,60)); cats(geo); heat(geo); topList(geo);
  changing(reg); fcRender(); eventsRender(reg);
  energyRender(base,lens,Math.min(days,60));
  gdeltRender(days,reg);
}

const ST={Escalating:['▲','up'],New:['●','new'],Steady:['–',''],Cooling:['▼',''],Quiet:['○','']};
const stPill=s=>`<span class="st ${ST[s][1]}">${ST[s][0]} ${s}</span>`;
const fmtDay=d=>new Date(d+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short'});
const pct=p=>p==null?'–':Math.round(p*100)+'%';

function changing(reg){
  const ev=(D.events||[]).filter(e=>!reg||e.region===reg);
  const hot=ev.filter(e=>e.status==='Escalating'||e.status==='New').slice(0,6);
  const cool=ev.filter(e=>e.status==='Cooling'&&e.max_severity>=3).slice(0,2);
  const li=(e)=>`<li><span class="ic" style="color:${e.status==='Escalating'?'var(--crit)':'var(--ink2)'}">${ST[e.status][0]}</span><div><div class="t">${esc(e.name)}</div><div class="d">${e.status} · ${esc(e.country)} · ${e.recent_reports} report${e.recent_reports==1?'':'s'} in 3 days · severity ${e.recent_severity}</div></div></li>`;
  $('chgNews').innerHTML=[...hot,...cool].map(li).join('')||'<li><span class="d">No events reported yet in this range.</span></li>';
  const c=D.changes||{};
  if(!c.ready){$('chgGdelt').innerHTML=`<li><span class="d">Building a baseline: needs ${21} days of GDELT data, has ${7+(c.baseline_days||0)}.</span></li>`;return}
  const r=(c.rising||[]).filter(x=>!reg||x.region===reg).slice(0,5), f=(c.falling||[]).filter(x=>!reg||x.region===reg).slice(0,2);
  const g=(x,up)=>`<li><span class="ic" style="color:${up?'var(--crit)':'var(--ink2)'}">${up?'▲':'▼'}</span><div><div class="t">${esc(x.country)} <span class="pct">${x.ratio>=1?x.ratio.toFixed(1)+'×':'−'+Math.round((1-x.ratio)*100)+'%'}</span></div><div class="d">${x.recent_per_day} events/day vs usual ${x.baseline_per_day}${x.driver?' · mostly '+esc((D.labels[x.driver]||x.driver).toLowerCase()):''}</div></div></li>`;
  $('chgGdelt').innerHTML=(r.map(x=>g(x,1)).join('')+f.map(x=>g(x,0)).join(''))||'<li><span class="d">Nothing unusual in the last 7 days.</span></li>';
}

function fcRender(){
  const F=(D.fc||{}).forecasts||[], S=(D.fc||{}).score||{};
  const tile=(k,v,sub)=>`<div class="cp"><div class="k">${k}</div><div class="n">${v}</div><div class="k">${sub}</div></div>`;
  $('fcScore').innerHTML=tile('Open forecasts',S.open||0,'awaiting their deadline')+tile('Resolved',S.resolved||0,'scored so far')
    +tile("Claude's Brier score",S.ai==null?'–':S.ai.toFixed(3),S.resolved?`over ${S.resolved} forecast${S.resolved==1?'':'s'}`:'none resolved yet')
    +tile('Your Brier score',S.me==null?'–':S.me.toFixed(3),S.mine_count?`Claude scored ${S.ai_on_mine.toFixed(3)} on the same ${S.mine_count}`:'add yours in my_forecasts.csv');
  const open=F.filter(f=>f.status==='open'), done=F.filter(f=>f.status!=='open');
  $('fcOpen').innerHTML=open.length?'<div class="heatwrap"><table class="list"><tr><th>ID</th><th>Question</th><th>By</th><th>Claude</th><th>You</th></tr>'+open.map(f=>
    `<tr><td style="white-space:nowrap"><code>${esc(f.id)}</code></td><td><b>${esc(f.question)}</b><div class="note" style="margin:2px 0 0">Yes if: ${esc(f.criteria)}</div><div class="note" style="margin:2px 0 0">Reasoning: ${esc(f.rationale)}</div></td><td style="white-space:nowrap">${fmtDay(f.deadline)}</td><td class="pct">${pct(f.probability)}</td><td class="pct">${pct(f.my_probability)}</td></tr>`).join('')+'</table></div>'
    :'<p class="note">The first forecasts are made on the next daily run.</p>';
  $('fcDone').innerHTML=done.length?'<div class="heatwrap"><table class="list"><tr><th>ID</th><th>Question</th><th>Outcome</th><th>Claude</th><th>You</th></tr>'+done.map(f=>
    `<tr><td style="white-space:nowrap"><code>${esc(f.id)}</code></td><td>${esc(f.question)}${f.resolution_note?`<div class="note" style="margin:2px 0 0">${esc(f.resolution_note)}</div>`:''}</td><td><b>${f.status==='unresolvable'?'Unresolved':f.outcome?'Yes':'No'}</b></td><td class="pct">${pct(f.probability)}${f.brier_ai!=null?`<div class="note" style="margin:0">Brier ${f.brier_ai.toFixed(2)}</div>`:''}</td><td class="pct">${pct(f.my_probability)}${f.brier_me!=null?`<div class="note" style="margin:0">Brier ${f.brier_me.toFixed(2)}</div>`:''}</td></tr>`).join('')+'</table></div>'
    :'<p class="note">None yet. The first forecasts resolve 2–8 weeks after they are made.</p>';
}

function spark(d){const W=84,H=22,m=Math.max(1,...d),bw=W/d.length;return `<svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">${d.map((v,i)=>v?`<rect x="${i*bw+0.5}" y="${H-Math.max(2,H*v/m)}" width="${bw-1.5}" height="${Math.max(2,H*v/m)}" rx="1" fill="var(--s1)"/>`:`<rect x="${i*bw+0.5}" y="${H-1}" width="${bw-1.5}" height="1" fill="var(--grid)"/>`).join('')}</svg>`}

function eventsRender(reg){
  const ev=(D.events||[]).filter(e=>!reg||e.region===reg).slice(0,25);
  $('events').innerHTML=ev.length?'<div class="heatwrap"><table class="list"><tr><th>Status</th><th>Event</th><th>Reports</th><th>Max sev.</th><th>Last 14 days</th></tr>'+ev.map((e,i)=>
    `<tr class="evrow" data-i="${i}"><td>${stPill(e.status)}</td><td><b>${esc(e.name)}</b><div class="note" style="margin:2px 0 0">${esc(e.country)} · ${e.sources} source${e.sources==1?'':'s'} · since ${fmtDay(e.first_seen)}</div></td><td class="pct">${e.reports}<div class="note" style="margin:0;font-weight:400">${e.recent_reports} in 3 days</div></td><td class="pct" style="color:${e.max_severity>=5?'var(--crit)':'var(--ink)'}">${e.max_severity>=5?'▲ ':''}${e.max_severity}</td><td>${spark(e.daily)}</td></tr>
     <tr class="evd" id="evd${i}" style="display:none"><td></td><td colspan="4"><ul>${e.headlines.map(h=>`<li>${fmtDay(h.day)} · ${esc(h.source)} · ${h.link?`<a href="${esc(h.link)}" target="_blank" rel="noopener">${esc(h.title)}</a>`:esc(h.title)}</li>`).join('')}</ul></td></tr>`).join('')+'</table></div>'
    :'<p class="note">Events appear here after the next daily run groups the headlines.</p>';
  $('events').querySelectorAll('.evrow').forEach(r=>r.onclick=()=>{const d=$('evd'+r.dataset.i);d.style.display=d.style.display==='none'?'':'none'});
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
      <div class="k" style="margin-bottom:4px">${items.length?`items · max severity <b style="color:${mx>=5?'var(--crit)':'var(--ink)'}">${mx>=5?'▲ ':''}${mx}</b>`:'no items in range'}</div>
      ${latest?`<div class="h">${latest.link?`<a href="${esc(latest.link)}" target="_blank" rel="noopener">${esc(latest.title)}</a>`:esc(latest.title)}</div>`:''}</div>`}).join('');
  // themes
  const byT=Object.keys(D.energy||{}).map(k=>[D.energy[k],e.filter(r=>themesOf(r).includes(k)).length]).filter(d=>!(lens&&lens!=='*')||d[1]).sort((a,b)=>b[1]-a[1]);
  barChart('ethemes',byT,'Energy items by theme',180);
  // trend
  const ds=[];for(let i=n-1;i>=0;i--)ds.push(new Date(Date.now()-i*864e5).toISOString().slice(0,10));
  lineChart('etrend',ds,ds.map(d=>e.filter(r=>day(r.fetched_at)===d).reduce((a,r)=>a+r.severity,0)),(d,v)=>`Energy risk index ${v} · ${e.filter(r=>day(r.fetched_at)===d).length} items`,'Daily energy risk index line chart',520);
  // list
  const t=[...e].sort((a,b)=>b.severity-a.severity||(b.fetched_at>a.fetched_at?1:-1)).slice(0,20);
  $('elist').innerHTML=t.length?'<div class="heatwrap"><table class="list"><tr><th>Sev.</th><th>Headline</th><th>Where</th><th>Source</th></tr>'+t.map(r=>
   `<tr><td class="sev" style="color:${r.severity>=5?'var(--crit)':'var(--ink)'}">${r.severity>=5?'▲ ':''}${r.severity}</td>
    <td>${r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}${r.energy_note&&!r.demo?`<div class="note" style="margin:2px 0 0">${esc(r.energy_note)}</div>`:''}<div>${pills(r)}</div></td>
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
  const raw=max/4,mag=Math.pow(10,Math.floor(Math.log10(raw))),stp=[1,2,2.5,5,10].map(m=>m*mag).find(s=>s>=raw),nice=stp*4;
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

function trend(geo,n){
  const W=1000,H=220,P={l:36,r:12,t:12,b:26};
  const ds=[];for(let i=n-1;i>=0;i--)ds.push(new Date(Date.now()-i*864e5).toISOString().slice(0,10));
  const v=ds.map(d=>dedupe(geo.filter(r=>day(r.fetched_at)===d)).reduce((a,r)=>a+r.severity,0));
  const max=Math.max(5,...v), nice=Math.ceil(max/5)*5;
  const x=i=>P.l+(ds.length<2?0:i*(W-P.l-P.r)/(ds.length-1)), y=t=>P.t+(H-P.t-P.b)*(1-t/nice);
  let g='';for(let k=0;k<=4;k++){const t=nice*k/4;g+=`<line x1="${P.l}" x2="${W-P.r}" y1="${y(t)}" y2="${y(t)}" stroke="var(--${k?'grid':'axis'})"/><text x="${P.l-6}" y="${y(t)+4}" text-anchor="end" style="font-variant-numeric:tabular-nums">${t}</text>`}
  const step=Math.ceil(ds.length/8);ds.forEach((d,i)=>{if((i%step===0&&ds.length-1-i>=step/2)||i===ds.length-1)g+=`<text x="${x(i)}" y="${H-6}" text-anchor="middle">${new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short'})}</text>`});
  const path=v.map((t,i)=>(i?'L':'M')+x(i)+','+y(t)).join('');
  $('trend').innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily risk index line chart">${g}
   <path d="${path}" fill="none" stroke="var(--s1)" stroke-width="2" stroke-linejoin="round"/>
   <line id="xh" y1="${P.t}" y2="${H-P.b}" stroke="var(--axis)" style="display:none"/><circle id="dot" r="4.5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2" style="display:none"/>
   <rect x="${P.l}" y="0" width="${W-P.l-P.r}" height="${H}" fill="transparent" id="hit"/></svg>`;
  const svg=$('trend').querySelector('svg');
  $('hit').onmousemove=e=>{const b=svg.getBoundingClientRect(),px=(e.clientX-b.left)*W/b.width;
    const i=Math.max(0,Math.min(ds.length-1,Math.round((px-P.l)/((W-P.l-P.r)/Math.max(1,ds.length-1)))));
    $('xh').setAttribute('x1',x(i));$('xh').setAttribute('x2',x(i));$('xh').style.display='';
    $('dot').setAttribute('cx',x(i));$('dot').setAttribute('cy',y(v[i]));$('dot').style.display='';
    const cnt=geo.filter(r=>day(r.fetched_at)===ds[i]).length;
    showTip(e,`<b>${new Date(ds[i]).toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'})}</b><br>Risk index ${v[i]} · ${cnt} items`)};
  $('hit').onmouseleave=()=>{hideTip();$('xh').style.display='none';$('dot').style.display='none'};
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
    return `<td title="${esc(r)} · ${esc(D.labels[k])}: ${n}" style="background:${shade(n)};${n?'':'border:1px solid var(--grid);'}${dark?'color:var(--hiink)':''}">${n||''}</td>`}).join('')+'</tr>'});
  $('heat').innerHTML=regs.length?h+'</table>':'<p class="note">No data in this range.</p>';
  $('hl').innerHTML='Fewer '+[1,2,3,4,5,6,7].map(i=>`<span style="background:var(--q${i})"></span>`).join('')+' More';
}

function topList(geo){
  const t=geo.filter(r=>r.severity>=4).slice(0,15);
  $('top').innerHTML=t.length?'<div class="heatwrap"><table class="list"><tr><th>Sev.</th><th>Headline</th><th>Where</th><th>Type</th><th>Source</th></tr>'+t.map(r=>
   `<tr><td class="sev" style="color:${r.severity>=5?'var(--crit)':'var(--ink)'}">${r.severity>=5?'▲ ':''}${r.severity}</td>
    <td>${r.link?`<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}${r.reason&&!r.demo?`<div class="note" style="margin:2px 0 0">${esc(r.reason)}</div>`:''}${themesOf(r).length?`<div>${pills(r)}</div>`:''}</td>
    <td>${esc(r.country)}</td><td>${esc(D.labels[r.category])}</td><td>${esc(r.source)}</td></tr>`).join('')+'</table></div>':'<p class="note">None in this range.</p>';
}
$('fRange').onchange=render;$('fRegion').onchange=render;$('fLens').onchange=render;render();
</script></body></html>"""

if __name__ == "__main__":
    build()
    print(f"Dashboard written to {config.DASHBOARD_PATH}")
