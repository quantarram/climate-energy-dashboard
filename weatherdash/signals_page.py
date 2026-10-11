"""Front page: the frozen climate signals, their live record. Built from data/signals.json (assembled by pipelines/run_daily.py)."""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Climate Signals</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{--accent:#5B8DBE;--accent2:#7FAAD1;--bg:#0C0E0D;--s1:#141614;--s2:#1B1E1B;--bdr:#2C302C;--bdr2:#3A3F3A;
--text:#DDE8DD;--text2:#8A9F8A;--text3:#5A6A5A;--hot:#C9784A;--cold:#5B8DBE;--ok:#7FB08A;--warn:#C8A84A;
--mono:'IBM Plex Mono',monospace;--sans:'IBM Plex Sans',sans-serif;--r:10px;--gap:16px;--pad:20px;}
*{box-sizing:border-box;margin:0;padding:0}html{font-size:15px}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.6;min-height:100vh}
header{background:linear-gradient(160deg,#0C0E0D,#141a1e,#0C0E0D);border-bottom:1px solid var(--bdr);padding:18px var(--pad);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
.h-title{font-family:var(--mono);font-size:clamp(13px,2vw,17px);font-weight:600;color:var(--accent2)}
.h-sub{font-family:var(--mono);font-size:11px;color:var(--text2);letter-spacing:.06em;text-transform:uppercase;margin-top:2px}
.h-meta{font-family:var(--mono);font-size:11px;color:var(--text2);text-align:right;line-height:1.8}
nav{display:flex;gap:18px;flex-wrap:wrap;max-width:1180px;margin:0 auto;padding:12px var(--pad) 0;font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
nav a{color:var(--text2);text-decoration:none;border-bottom:1px solid transparent}nav a:hover,nav a:focus-visible{color:var(--accent2);border-color:var(--accent2);outline:none}
main{max-width:1180px;margin:0 auto;padding:16px var(--pad) 10px}
.banner{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:var(--pad);margin-bottom:20px;font-size:13px;color:var(--text2);line-height:1.75}
.banner b{color:var(--text)}.banner a{color:var(--accent2)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:var(--gap);margin-bottom:20px}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:var(--pad)}
.c-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.c-name{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--accent2)}
.pill{font-family:var(--mono);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;padding:2px 8px;border-radius:99px;border:1px solid var(--bdr2);color:var(--text2);white-space:nowrap}
.pill.hot{color:var(--hot);border-color:#5A3A25}.pill.cold{color:var(--cold);border-color:#2C4050}.pill.on{color:var(--warn);border-color:#5A4E25}.pill.ok{color:var(--ok);border-color:#2C4A34}
.big{font-family:var(--mono);font-size:26px;font-weight:600;margin-top:8px}.big small{font-size:11px;color:var(--text2);font-weight:400}
.line{font-family:var(--mono);font-size:11px;color:var(--text2);margin-top:2px}
section{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:var(--pad);margin-bottom:20px;scroll-margin-top:8px}
.s-title{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--accent2);text-transform:uppercase;letter-spacing:.06em}
.s-sub{font-size:12.5px;color:var(--text2);margin:6px 0 14px;line-height:1.7;max-width:900px}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:var(--gap)}
.charts>div{min-width:0;overflow:hidden}
.c-label{font-family:var(--mono);font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.06em;margin:10px 0 2px}
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}th,td{text-align:right;padding:6px 10px;border-bottom:1px solid var(--bdr);font-family:var(--mono);vertical-align:top}
th:first-child,td:first-child,td.l,th.l{text-align:left}th{color:var(--text2);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.05em}
td.wrap{white-space:normal;font-family:var(--sans);font-size:12px;text-align:left;line-height:1.5}
.table-wrap table{min-width:720px}td.wrap{min-width:200px}
.note{font-size:12px;color:var(--text2);margin-top:12px;line-height:1.7;max-width:900px}.table-wrap{overflow-x:auto}
details{margin-top:14px}summary{cursor:pointer;font-family:var(--mono);font-size:11px;color:var(--accent2);text-transform:uppercase;letter-spacing:.06em}
summary:focus-visible{outline:1px solid var(--accent2);outline-offset:3px}
tr.fire td{color:var(--warn)}
footer{padding:24px var(--pad) 40px;text-align:center;font-family:var(--mono);font-size:10px;color:var(--text3);line-height:1.8}
footer a{color:var(--text2)}
</style></head><body>
<header><div><div class="h-title">Climate Signals</div>
<div class="h-sub">Rare, severe, slow climate states, frozen as CPE signals and scored forward</div></div><div class="h-meta" id="hmeta"></div></header>
<nav><a href="#state">Climate state</a><a href="#decisions">Registered decisions</a><a href="#books">Frozen signals and live record</a><a href="archive.html">Archive: daily weather panels</a></nav>
<main>
<div class="banner"><b>What this page tracks, and why only this.</b> The research behind it tested free weather forecasts against prices for gas, power, crops and energy equities, from daily rules to machine-learning models, and found no
edge: markets already price what the public forecasts say, and day-to-day weather moves prices far less than their own noise. What persisted in causal tests was confined to the rare, extreme tail of slow climate states (El Ni&ntilde;o above all) and to the CPE framework&rsquo;s own admission rules, on few episodes and without a positive return in a simple rule; it is a candidate, not a result. This page follows only that, as frozen CPE rows scored forward. Every signal in the table was frozen on <b id="frz"></b> from data through 2012 and is scored forward only. The daily weather-to-demand panels, which are
still scored for the registered experiment, are on the <a href="archive.html">archive page</a>.</div>

<section id="state"><div class="s-title">Climate state now</div>
<div class="cards" id="cards" style="margin-top:14px"></div>
<div class="c-label">Oceanic Nino Index since 1990 (3-month average anomaly, &deg;C; plotted at publication date)</div><div id="oniChart"></div>
<div class="note">Above +0.5 &deg;C is El Ni&ntilde;o, above +1.5 &deg;C strong; below &minus;0.5 &deg;C is La Ni&ntilde;a. The ONI is published about ten days into the second month after its window, so the latest value describes the three months to the end of last month.</div></section>

<section id="decisions"><div class="s-title">Registered decisions: what the frozen conditions imply, and what that earns</div>
<div class="s-sub">The frozen climate conditions below are turned into paper positions by one fixed rule, registered before any result and scored from the first trading day after the freeze. These are implied positions in a research experiment, not advice.
The same rule run on rows admitted causally in the past shows no historical edge (see the backtest below), so the live record is the test.</div>
<div class="c-label">Implied positions from the next trading day</div><div class="table-wrap"><table id="dtoday"></table></div>
<div class="note" id="dnote"></div>
<div class="cards" id="dcards" style="margin-top:16px"></div>
<div class="charts"><div><div class="c-label">Live paper portfolio: cumulative log return (net of costs)</div><div id="dLive"></div></div>
<div><div class="c-label">Causal backtest 2016&ndash;2026: cumulative log return, climate extreme tail (weekly)</div><div id="dBack"></div></div></div>
<div class="c-label" style="margin-top:18px">Backtest: rows admitted causally each 1 January from outcomes already resolved, then scored on the entries made that year</div>
<div class="table-wrap"><table id="dbtable"></table></div>
<div class="note" id="dbnote"></div>
<details><summary>The registered rule and what would count as evidence</summary><div class="note" id="dreg"></div></details></section>

<div id="books"></div>
</main>
<footer>Climate indices: NOAA CPC and PSL &middot; Prices: Yahoo Finance chart data<br>
Research record, not a trading or operational tool. <a href="https://github.com/quantarram/weather-impacts-dashboard">Code and data</a></footer>
<script>
const D = __DATA__;
const A = D.cpe, BK = A.books;
const f = (x, n) => x === null || x === undefined || Number.isNaN(x) ? '' : Number(x).toFixed(n);
const sgn = (x, n) => (x >= 0 ? '+' : '') + f(x, n);
const el = id => document.getElementById(id);
const BASE = {paper_bgcolor:'transparent',plot_bgcolor:'transparent',height:280,margin:{l:48,r:12,t:20,b:36},font:{family:'IBM Plex Mono',size:10,color:'#8A9F8A'},
  xaxis:{gridcolor:'#1B1E1B',automargin:true},yaxis:{gridcolor:'#1B1E1B',zeroline:false,automargin:true},
  legend:{orientation:'h',x:0,y:1.15,font:{size:9}}};
const CFG = {displayModeBar:false,responsive:true};
const merge = (a, b) => Object.assign({}, a, b);
el('hmeta').innerHTML = 'Climate and prices through ' + A.asof + '<br>Updated ' + D.generated_utc + ' UTC';
{ const f3 = BK.map(b => b.frozen_on + ' (' + b.stats.n_table_rows + ' rows, table ' + b.stats.table_sha + ')'); el('frz').textContent = f3.length > 1 ? f3.slice(0, -1).join(', ') + ' and ' + f3[f3.length - 1] : f3[0]; }

// ---------- climate state
const E = A.enso, allW = BK.flatMap(b => b.watch), firing = allW.filter(w => w.firing);
const ensoCls = /El Nino/.test(E.state) ? 'hot' : /La Nina/.test(E.state) ? 'cold' : '';
const cards = el('cards');
const card = (name, pill, pcls, big, small, lines) => { const c = document.createElement('div'); c.className = 'card';
  c.innerHTML = '<div class="c-head"><span class="c-name">' + name + '</span><span class="pill ' + pcls + '">' + pill + '</span></div><div class="big">' + big + ' <small>' + small + '</small></div>' + lines.map(l => '<div class="line">' + l + '</div>').join(''); return c; };
cards.appendChild(card('Oceanic Nino Index', E.state, ensoCls, sgn(E.oni, 2), '&deg;C', ['three months to ' + E.oni_available.slice(0, 7), 'published ' + E.oni_available]));
cards.appendChild(card('Nino 3.4 monthly anomaly', E.state, ensoCls, sgn(E.nino34_anom, 2), '&deg;C', ['published ' + E.nino34_available]));
cards.appendChild(card('Frozen conditions firing', firing.length ? 'live' : 'none', firing.length ? 'on' : 'ok', firing.length + ' of ' + allW.length, 'conditions', firing.length ? firing.map(w => w.targets.map(t => t.name).join(', ')) : ['none of the frozen thresholds is crossed']));
{
  const o = D.oni, x = o.map(r => r[0]), y = o.map(r => r[1]);
  Plotly.newPlot('oniChart', [{x, y, type:'scatter', mode:'lines', line:{color:'#7FAAD1', width:1.4}, hovertemplate:'%{x|%b %Y}: %{y:+.2f}<extra></extra>'}],
    merge(BASE, {height:240, shapes:[{type:'rect', xref:'paper', x0:0, x1:1, y0:0.5, y1:4, fillcolor:'rgba(201,120,74,.10)', line:{width:0}}, {type:'rect', xref:'paper', x0:0, x1:1, y0:-4, y1:-0.5, fillcolor:'rgba(91,141,190,.10)', line:{width:0}}],
      yaxis:merge(BASE.yaxis, {range:[-2.6, 3.2]}), showlegend:false}), CFG);
}

// ---------- registered decisions
{
  const Dn = D.decisions, pct = x => (x === null || x === undefined ? '' : (x >= 0 ? '+' : '') + (x * 100).toFixed(1) + '%');
  let t = '<tr><th class="l">Target</th><th class="l">Position</th><th>Weight</th><th>Rows</th><th class="l">Indices</th><th>Horizons</th><th class="l">Entered</th><th class="l">Open until about</th><th>Claimed CPE</th><th>Test CPE vs base</th></tr>';
  (Dn.today || []).forEach(d => { t += '<tr><td class="l">' + d.name + ' (' + d.target + ')</td><td class="l"><span class="pill ' + (d.side === 'long' ? 'on' : 'cold') + '">' + d.side + '</span></td><td>' + (d.weight >= 0 ? '+' : '') + f(d.weight, 2) + '</td><td>' + d.supporting_rows + '</td><td class="wrap">' + d.indices.join(', ') + '</td><td>' + d.horizons.join(', ') + '</td><td class="l">' + d.first_entry + '</td><td class="l">' + d.expires_about + '</td><td>' + f(d.claimed_cpe, 2) + '</td><td>' + f(d.test_cpe, 2) + ' vs ' + f(d.test_base, 2) + '</td></tr>'; });
  if (!(Dn.today || []).length) t += '<tr><td class="l" colspan="10">No frozen condition is active: the paper portfolio is flat.</td></tr>';
  el('dtoday').innerHTML = t;
  el('dnote').innerHTML = 'Weights are equal over the ' + (Dn.today || []).length + ' active target(s); the rows column counts how many frozen rows vote for the position, and they come from ENSO indices that move together, so ten rows are one view, not ten. Horizons are in trading days from entry.';
  const cards = el('dcards'), L = Dn.live || {}, st = L.strategy || {};
  [['Days scored', Dn.n_days, 'next review at ' + (Dn.review_points.find(r => r > Dn.n_days) || '')], ['Status', Dn.status.replace(/_/g, ' '), 'verdict only at a review'], ['Net annualised return', st.ann_return === undefined ? 'collecting' : pct(st.ann_return), 'same targets held: ' + (L.hold_same && L.hold_same.ann_return !== undefined ? pct(L.hold_same.ann_return) : 'collecting')]].forEach(a => {
    const c = document.createElement('div'); c.className = 'card'; c.innerHTML = '<div class="c-name">' + a[0] + '</div><div class="big" style="font-size:22px">' + a[1] + '</div><div class="line">' + a[2] + '</div>'; cards.appendChild(c); });
  const cv = Dn.curves;
  Plotly.newPlot('dLive', cv.dates.length ? [{x:cv.dates, y:cv.strategy, name:'Climate rule', type:'scatter', mode:'lines', line:{color:'#C8A84A', width:1.6}}, {x:cv.dates, y:cv.hold_same, name:'Same targets, long', type:'scatter', mode:'lines', line:{color:'#7FAAD1', width:1.2}}, {x:cv.dates, y:cv.spy, name:'SPY', type:'scatter', mode:'lines', line:{color:'#5A6A5A', width:1}}] : [],
    merge(BASE, {height:260, annotations: cv.dates.length ? [] : [{text:'Scoring starts on ' + Dn.registry.first_scored_day, showarrow:false, xref:'paper', yref:'paper', x:0.5, y:0.5, font:{size:12, color:'#8A9F8A'}}], xaxis:merge(BASE.xaxis, {visible: cv.dates.length > 0}), yaxis:merge(BASE.yaxis, {visible: cv.dates.length > 0})}), CFG);
  const B = Dn.backtest || {}, bc = B.climate && B.climate.curves;
  if (bc) Plotly.newPlot('dBack', [{x:bc.dates, y:bc.strategy, name:'Climate rule (extreme tail)', type:'scatter', mode:'lines', line:{color:'#C8A84A', width:1.5}}, {x:bc.dates, y:bc.hold_same, name:'Same targets, long', type:'scatter', mode:'lines', line:{color:'#7FAAD1', width:1.2}}, {x:bc.dates, y:bc.spy, name:'SPY', type:'scatter', mode:'lines', line:{color:'#5A6A5A', width:1}}],
    merge(BASE, {height:260, xaxis:merge(BASE.xaxis, {tickformat:'%Y'})}), CFG);
  const row = (lab, e, pf) => e ? '<tr><td class="l">' + lab + '</td><td>' + e.events + '</td><td>' + f(e.hit, 3) + '</td><td>' + f(e.base, 3) + '</td><td>' + pct(e.hit_diff) + '</td><td>' + pct(e.mean_return) + '</td><td>' + pct(e.mean_excess) + '</td><td>' + (e.t_events === null ? '' : f(e.t_events, 1)) + ' / ' + (e.t_year_clustered === null ? '' : f(e.t_year_clustered, 1)) + '</td><td>' + (pf ? pct(pf.strategy_full.ann) + ' (Sharpe ' + f(pf.strategy_full.sharpe, 2) + ')' : '') + '</td><td>' + (pf ? pct(pf.hold_same_full.ann) : '') + '</td></tr>' : '';
  let b = '<tr><th class="l">Arm</th><th>Events</th><th>Hit</th><th>Base</th><th>Diff</th><th>Mean return</th><th>Excess vs drift</th><th>t (events / by year)</th><th>Rule, annualised</th><th>Same targets long</th></tr>';
  if (B.climate) { const c = B.climate, p = c.portfolio || {};
    b += row('Climate, admitted, extreme tail (q_X &ge; 0.90)', c.extreme, p['extreme tail q_X>=0.9']) + row('Climate, admitted, moderate tail', c.moderate, p['moderate q_X<0.9']) + row('Climate, all admitted', c.admitted, p['all admitted']) + row('Climate, not admitted (control)', c.not_admitted, null); }
  if (B.market) { const c = B.market, p = c.portfolio || {};
    b += row('Control: the program&rsquo;s own market predictors, extreme tail', c.extreme, p['extreme tail q_X>=0.9']) + row('Control: market predictors, all admitted', c.admitted, p['all admitted']); }
  el('dbtable').innerHTML = b;
  el('dbnote').innerHTML = '<b>Reading it.</b> Rows admitted by the survivor filter with only past outcomes hit more often than the base rate in the extreme tail, but the effect is small against trade-level variance (about 16 points of excess-return sd per trade), is clustered in 2019&ndash;2023, and does not become a positive return: ' +
    'the rule earned ' + (B.climate ? pct(B.climate.portfolio['extreme tail q_X>=0.9'].strategy_full.ann) : '') + ' a year in the extreme tail against ' + (B.climate ? pct(B.climate.portfolio['extreme tail q_X>=0.9'].hold_same_full.ann) : '') + ' for holding the same targets. Excess is measured against each target&rsquo;s own mean return in the entry year, signed by the position. ' +
    'The market control shows the same shape: a hit-rate edge that mostly reproduces long drift. The ENSO batch (first table) is negative on its own. 164 of the 188 extreme-tail trades are median-split direction bets, so a few points of hit rate buy little.';
  el('dreg').innerHTML = '<b>Hypothesis.</b> ' + Dn.registry.hypothesis + '<br><b>Rule.</b> ' + Dn.registry.rule + '<br><b>Benchmarks.</b> ' + Dn.registry.benchmarks + '<br><b>Evidence of an edge.</b> ' + Dn.registry.evidence_of_edge + '<br><b>History.</b> ' + Dn.registry.history + '<br><b>Not claimed.</b> ' + Dn.registry.not_claimed;
}

// ---------- one watchlist and live record per frozen table
BK.forEach(C => {
  const id = C.id, box = document.createElement('div');
  box.innerHTML =
    '<section id="watch-' + id + '"><div class="s-title">' + C.label + ': where each condition stands</div>' +
    '<div class="s-sub">Frozen ' + C.frozen_on + ', thresholds from formation data through 2012. A condition fires when its slow climate series crosses the threshold; the targets then have the stated horizons to resolve. ' +
    '&ldquo;Test&rdquo; is how the same rows scored against the base rate in 2013&ndash;2026, before the freeze.</div>' +
    '<div class="note" id="wlead-' + id + '" style="margin:0 0 6px"></div><div class="table-wrap"><table id="wtable-' + id + '"></table></div>' +
    '<details id="wall-' + id + '"><summary>All ' + C.watch.length + ' conditions</summary><div class="table-wrap"><table id="wfull-' + id + '"></table></div></details>' +
    '<div class="note" id="wnote-' + id + '"></div></section>' +
    '<section id="record-' + id + '"><div class="s-title">Live record: ' + C.label + '</div>' +
    '<div class="cards" id="rcards-' + id + '" style="margin-top:14px"></div>' +
    '<div class="table-wrap"><table id="rtable-' + id + '"></table></div>' +
    '<div class="c-label" style="margin-top:18px">Entry events logged</div><div class="table-wrap"><table id="etable-' + id + '"></table></div>' +
    '<details><summary>All ' + C.frozen_rows_n + ' frozen rows</summary><div class="table-wrap"><table id="ftable-' + id + '"></table></div></details>' +
    '<div class="note" id="rnote-' + id + '"></div></section>';
  el('books').appendChild(box);
  const wrow = w => '<tr class="' + (w.firing ? 'fire' : '') + '"><td class="wrap">' + w.condition + ' &rarr; <b>' + (w.direction === 'bullish' ? 'targets rise' : 'targets fall') + '</b></td><td>' + sgn(w.now, 2) + '</td><td>' + sgn(w.threshold, 2) + '</td>' +
    '<td>' + (w.firing ? '<span class="pill on">firing</span>' : '<span class="pill">waiting &middot; ' + f(w.gap, 2) + ' to go</span>') + '</td>' +
    '<td class="wrap">' + w.targets.map(x => x.name + ' (' + x.horizons.join(', ') + ')').join('; ') + '</td><td>' + w.n_rows + '</td><td>' + f(w.test_cpe, 2) + ' vs ' + f(w.test_base, 2) + '</td></tr>';
  const head = '<tr><th class="l">Condition</th><th>Now</th><th>Threshold</th><th>State</th><th class="l">Targets (horizon, trading days)</th><th>Rows</th><th>Test CPE vs base</th></tr>';
  const fw = C.watch.filter(w => w.firing), long = C.watch.length > 12;
  el('wtable-' + id).innerHTML = head + (long ? fw : C.watch).map(wrow).join('');
  if (!long) el('wall-' + id).style.display = 'none'; else el('wfull-' + id).innerHTML = head + C.watch.map(wrow).join('');
  el('wlead-' + id).innerHTML = long ? (fw.length ? 'Firing now (' + fw.length + ' of ' + C.watch.length + ' conditions); the rest are in the full list below.' : 'No condition fires now; the full list is below.') : '';
  el('wnote-' + id).innerHTML = 'Units are those of the index (&deg;C for temperature and sea-surface series, index points for drought, million km&sup2; for snow cover; for averages, the mean over the window). &ldquo;To go&rdquo; is how far the series must still move to cross its threshold. ' + fw.length + ' of ' + C.watch.length + ' conditions fire now.' +
    (C.redundancy ? ' <b>Read the rows with care:</b> ' + C.redundancy : '');
  const s = C.stats, rc = el('rcards-' + id);
  [['Frozen rows', s.n_table_rows, 'sha ' + s.table_sha], ['Entry events logged', s.n_events, 'since ' + s.table_end], ['Outcomes resolved', s.n_resolved, s.n_pending + ' pending'], ['Last price bar', s.last_bar, 'prices from Yahoo']].forEach(a => {
    const c = document.createElement('div'); c.className = 'card'; c.innerHTML = '<div class="c-name">' + a[0] + '</div><div class="big" style="font-size:22px">' + a[1] + '</div><div class="line">' + a[2] + '</div>'; rc.appendChild(c); });
  let t = '<tr><th class="l">Horizon</th><th>Resolved</th><th>Pending</th><th class="l">First resolves</th><th>Claimed</th><th>Realised</th><th>Table base</th><th>Live base</th></tr>';
  s.by_horizon.forEach(r => { t += '<tr><td>' + r.horizon + ' days</td><td>' + r.n + '</td><td>' + r.n_pending + '</td><td class="l">' + (r.first_pending ? '~' + r.first_pending : '') + '</td><td>' + f(r.claimed, 3) + '</td><td>' + f(r.hit, 3) + '</td><td>' + f(r.base, 3) + '</td><td>' + f(r.live_base, 3) + '</td></tr>'; });
  el('rtable-' + id).innerHTML = t;
  let e = '<tr><th class="l">Entry</th><th class="l">Kind</th><th class="l">Condition</th><th>Move</th><th>Threshold</th><th class="l">Targets</th></tr>';
  C.events.forEach(v => { e += '<tr><td>' + v.entry_date + '</td><td class="l">' + v.kind.replace(/_/g, ' ') + '</td><td class="wrap">' + v.condition + '</td><td>' + sgn(v.x_move, 2) + '</td><td>' + sgn(v.x_threshold, 2) + '</td><td class="wrap">' + v.targets.join(', ') + '</td></tr>'; });
  el('etable-' + id).innerHTML = e;
  let g = '<tr><th class="l">Condition</th><th class="l">Target</th><th>Horizon</th><th>Claimed</th><th>Lift</th><th>Form. episodes</th><th>Test</th><th>Base</th><th>Test episodes</th></tr>';
  C.frozen.forEach(r => { g += '<tr><td class="wrap">' + r.condition + '</td><td class="l">' + r.target + ' ' + (r.direction === 'bullish' ? '&uarr;' : '&darr;') + '</td><td>' + r.horizon + '</td><td>' + f(r.claimed, 2) + '</td><td>' + f(r.lift, 2) + '</td><td>' + r.n_ep_f + '</td><td>' + f(r.test_cpe, 2) + '</td><td>' + f(r.test_base, 2) + '</td><td>' + r.n_ep_t + '</td></tr>'; });
  el('ftable-' + id).innerHTML = g;
  el('rnote-' + id).innerHTML = '<b>How outcomes are scored.</b> An event is the first day a condition crosses its frozen threshold (conditions already beyond it on the data cutoff are logged once as ongoing). Each event fans out to every frozen row for that condition; the outcome is whether the target&rsquo;s forward move over the row&rsquo;s horizon lands beyond its frozen threshold in the stated direction. ' +
    'Claimed is the formation CPE, realised the live hit rate, table base the unconditional frequency in formation, live base the unconditional frequency since the freeze. Overlapping horizons are valid samples; no significance test is used. The longest horizons resolve in late 2027 and 2028, so for now this is a record of conditions and what is pending.';
});

(function () {
  const resizeAll = () => document.querySelectorAll('.js-plotly-plot').forEach(p => Plotly.Plots.resize(p));
  window.addEventListener('load', resizeAll); [100, 400, 1200].forEach(ms => setTimeout(resizeAll, ms));
  if (window.ResizeObserver) { let raf = null; const ro = new ResizeObserver(() => { if (raf) cancelAnimationFrame(raf); raf = requestAnimationFrame(resizeAll); }); ro.observe(document.body); }
  window.addEventListener('resize', resizeAll);
})();
</script></body></html>"""


def assemble():
    """Collect the three data sources into the page payload (each already fault-tolerant at its own level)."""
    from weatherdash import cpe_climate
    from weatherdash import climate_decisions
    books = cpe_climate.payload_all()
    cpe = {"asof": books[0]["asof"], "enso": books[0]["enso"], "books": books}
    oni = cpe_climate.index_series("ONI").dropna()
    oni = oni[(oni.index >= "1990-01-01") & (oni.index <= datetime.now(timezone.utc).strftime("%Y-%m-%d"))]
    return {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "cpe": cpe, "decisions": climate_decisions.payload(), "oni": [[str(d.date()), round(float(v), 2)] for d, v in oni.items()]}


def build(out_path=None, payload_path=None):
    payload_path = payload_path or os.path.join(ROOT, "data", "signals.json")
    out_path = out_path or os.path.join(ROOT, "docs", "index.html")
    data = open(payload_path).read()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(PAGE.replace("__DATA__", data))
    return out_path


if __name__ == "__main__":
    p = os.path.join(ROOT, "data", "signals.json")
    json.dump(assemble(), open(p, "w"), default=float)
    print("wrote", build())
