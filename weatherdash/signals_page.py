"""Front page: the frozen climate signals, their live record, and the shock and policy monitor. Built from data/signals.json (assembled by pipelines/run_daily.py)."""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Climate and Shock Signals</title>
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
<header><div><div class="h-title">Climate and Shock Signals</div>
<div class="h-sub">Rare, severe, slow climate states, the policy reactions they trigger, and what the prices do</div></div><div class="h-meta" id="hmeta"></div></header>
<nav><a href="#state">Climate state</a><a href="#watch">Frozen signals</a><a href="#record">Live record</a><a href="#shock">Shock and policy monitor</a><a href="archive.html">Archive: daily weather panels</a></nav>
<main>
<div class="banner"><b>What this page tracks, and why only this.</b> The research behind it tested free weather forecasts against prices for gas, power, crops and energy equities, from daily rules to machine-learning models, and found no
edge: markets already price what the public forecasts say, and day-to-day weather moves prices far less than their own noise. What did hold up out of sample is rare, severe and slow: strong ocean-climate states (El Ni&ntilde;o above all)
and the way governments react to the supply shocks that follow. This page follows only that. Every signal in the table was frozen on <b id="frz"></b> from data through 2012 and is scored forward only. The daily weather-to-demand panels, which are
still scored for the registered experiment, are on the <a href="archive.html">archive page</a>.</div>

<section id="state"><div class="s-title">Climate state now</div>
<div class="cards" id="cards" style="margin-top:14px"></div>
<div class="c-label">Oceanic Nino Index since 1990 (3-month average anomaly, &deg;C; plotted at publication date)</div><div id="oniChart"></div>
<div class="note">Above +0.5 &deg;C is El Ni&ntilde;o, above +1.5 &deg;C strong; below &minus;0.5 &deg;C is La Ni&ntilde;a. The ONI is published about ten days into the second month after its window, so the latest value describes the three months to the end of last month.</div></section>

<section id="watch"><div class="s-title">Frozen signals: where each condition stands</div>
<div class="s-sub">Each row is a condition on a slow climate series, with its threshold fixed from formation data (through 2012). A condition fires when the series crosses the threshold; the targets then have the stated horizons to resolve.
&ldquo;Test&rdquo; is how the same rows scored against the base rate in 2013&ndash;2026, before the freeze.</div>
<div class="table-wrap"><table id="wtable"></table></div>
<div class="note" id="wnote"></div></section>

<section id="record"><div class="s-title">Live record since the freeze</div>
<div class="cards" id="rcards" style="margin-top:14px"></div>
<div class="table-wrap"><table id="rtable"></table></div>
<div class="c-label" style="margin-top:18px">Entry events logged</div>
<div class="table-wrap"><table id="etable"></table></div>
<details><summary>All frozen rows</summary><div class="table-wrap"><table id="ftable"></table></div></details>
<div class="note" id="rnote"></div></section>

<section id="shock"><div class="s-title">Shock and policy monitor</div>
<div class="s-sub">A weather shock reaches prices through an institution. In the twelve documented export-policy events, restrictions followed high domestic price pressure with thin buffer stocks and no institutional constraint; rainfall alone did not decide it,
and the price had already run up before the announcement. So the observable to watch is how far each market has already run, next to the climate state that drives the shock.</div>
<div class="cards" id="gcards"></div>
<div class="charts"><div><div class="c-label">Trailing 60-trading-day price move (%)</div><div id="gChart"></div></div>
<div><div class="c-label">Run-up in the 60 trading days before the announcement, as a percentile of all 60-day moves (daily futures)</div><div id="uChart"></div></div></div>
<div class="note" id="gnote"></div>
<div class="c-label" style="margin-top:18px">Past policy episodes: what the institutions did</div>
<div class="table-wrap"><table id="ltable"></table></div>
<details><summary>Policy events with sources</summary><div class="table-wrap"><table id="ptable"></table></div></details>
<div class="note" id="snote"></div></section>
</main>
<footer>Climate indices: NOAA CPC and PSL &middot; Prices: Yahoo Finance chart data, FRED (World Bank) &middot; Policy events: official notifications and news reports listed per event<br>
Research record, not a trading or operational tool. <a href="https://github.com/quantarram/weather-impacts-dashboard">Code and data</a></footer>
<script>
const D = __DATA__;
const C = D.cpe, S = D.shocks;
const f = (x, n) => x === null || x === undefined || Number.isNaN(x) ? '' : Number(x).toFixed(n);
const sgn = (x, n) => (x >= 0 ? '+' : '') + f(x, n);
const el = id => document.getElementById(id);
const BASE = {paper_bgcolor:'transparent',plot_bgcolor:'transparent',height:280,margin:{l:48,r:12,t:20,b:36},font:{family:'IBM Plex Mono',size:10,color:'#8A9F8A'},
  xaxis:{gridcolor:'#1B1E1B',automargin:true},yaxis:{gridcolor:'#1B1E1B',zeroline:false,automargin:true},
  legend:{orientation:'h',x:0,y:1.15,font:{size:9}}};
const CFG = {displayModeBar:false,responsive:true};
const merge = (a, b) => Object.assign({}, a, b);
el('hmeta').innerHTML = 'Climate and prices through ' + C.asof + '<br>Updated ' + D.generated_utc + ' UTC';
el('frz').textContent = C.stats.table_end + ' (table ' + C.stats.table_sha + ')';

// ---------- climate state
const E = S.enso, firing = C.watch.filter(w => w.firing);
const ensoCls = /El Nino/.test(E.state) ? 'hot' : /La Nina/.test(E.state) ? 'cold' : '';
const cards = el('cards');
const card = (name, pill, pcls, big, small, lines) => { const c = document.createElement('div'); c.className = 'card';
  c.innerHTML = '<div class="c-head"><span class="c-name">' + name + '</span><span class="pill ' + pcls + '">' + pill + '</span></div><div class="big">' + big + ' <small>' + small + '</small></div>' + lines.map(l => '<div class="line">' + l + '</div>').join(''); return c; };
cards.appendChild(card('Oceanic Nino Index', E.state, ensoCls, sgn(E.oni, 2), '&deg;C', ['three months to ' + E.oni_available.slice(0, 7), 'published ' + E.oni_available]));
cards.appendChild(card('Nino 3.4 monthly anomaly', E.state, ensoCls, sgn(E.nino34_anom, 2), '&deg;C', ['published ' + E.nino34_available]));
cards.appendChild(card('Frozen conditions firing', firing.length ? 'live' : 'none', firing.length ? 'on' : 'ok', firing.length + ' of ' + C.watch.length, 'conditions', firing.length ? firing.map(w => w.targets.map(t => t.name).join(', ')) : ['none of the frozen thresholds is crossed']));
{
  const o = D.oni, x = o.map(r => r[0]), y = o.map(r => r[1]);
  Plotly.newPlot('oniChart', [{x, y, type:'scatter', mode:'lines', line:{color:'#7FAAD1', width:1.4}, hovertemplate:'%{x|%b %Y}: %{y:+.2f}<extra></extra>'}],
    merge(BASE, {height:240, shapes:[{type:'rect', xref:'paper', x0:0, x1:1, y0:0.5, y1:4, fillcolor:'rgba(201,120,74,.10)', line:{width:0}}, {type:'rect', xref:'paper', x0:0, x1:1, y0:-4, y1:-0.5, fillcolor:'rgba(91,141,190,.10)', line:{width:0}}],
      yaxis:merge(BASE.yaxis, {range:[-2.6, 3.2]}), showlegend:false}), CFG);
}

// ---------- watchlist
{
  let t = '<tr><th class="l">Condition</th><th>Now</th><th>Threshold</th><th>State</th><th class="l">Targets (horizon, trading days)</th><th>Rows</th><th>Test CPE vs base</th></tr>';
  C.watch.forEach(w => {
    t += '<tr class="' + (w.firing ? 'fire' : '') + '"><td class="wrap">' + w.condition + ' &rarr; <b>' + (w.direction === 'bullish' ? 'targets rise' : 'targets fall') + '</b></td><td>' + sgn(w.now, 2) + '</td><td>' + sgn(w.threshold, 2) + '</td>' +
         '<td>' + (w.firing ? '<span class="pill on">firing</span>' : '<span class="pill">waiting &middot; ' + f(w.gap, 2) + ' to go</span>') + '</td>' +
         '<td class="wrap">' + w.targets.map(x => x.name + ' (' + x.horizons.join(', ') + ')').join('; ') + '</td><td>' + w.n_rows + '</td><td>' + f(w.test_cpe, 2) + ' vs ' + f(w.test_base, 2) + '</td></tr>';
  });
  el('wtable').innerHTML = t;
  const nw = C.watch.filter(w => !w.firing).length;
  el('wnote').innerHTML = 'Units are &deg;C of the index (for averages, the mean anomaly over the window). &ldquo;To go&rdquo; is how far the series must still move to cross its threshold. ' + firing.length + ' of ' + C.watch.length + ' conditions fire now; ' + nw + ' wait.';
}

// ---------- live record
{
  const s = C.stats;
  const rc = el('rcards');
  [['Frozen rows', s.n_table_rows, 'sha ' + s.table_sha], ['Entry events logged', s.n_events, 'since ' + s.table_end], ['Outcomes resolved', s.n_resolved, s.n_pending + ' pending'], ['Last price bar', s.last_bar, 'prices from Yahoo']].forEach(a => {
    const c = document.createElement('div'); c.className = 'card'; c.innerHTML = '<div class="c-name">' + a[0] + '</div><div class="big" style="font-size:22px">' + a[1] + '</div><div class="line">' + a[2] + '</div>'; rc.appendChild(c); });
  let t = '<tr><th class="l">Horizon</th><th>Resolved</th><th>Pending</th><th class="l">First resolves</th><th>Claimed</th><th>Realised</th><th>Table base</th><th>Live base</th></tr>';
  s.by_horizon.forEach(r => { t += '<tr><td>' + r.horizon + ' days</td><td>' + r.n + '</td><td>' + r.n_pending + '</td><td class="l">' + (r.first_pending ? '~' + r.first_pending : '') + '</td><td>' + f(r.claimed, 3) + '</td><td>' + f(r.hit, 3) + '</td><td>' + f(r.base, 3) + '</td><td>' + f(r.live_base, 3) + '</td></tr>'; });
  el('rtable').innerHTML = t;
  let e = '<tr><th class="l">Entry</th><th class="l">Kind</th><th class="l">Condition</th><th>Move</th><th>Threshold</th><th class="l">Targets</th></tr>';
  C.events.forEach(v => { e += '<tr><td>' + v.entry_date + '</td><td class="l">' + v.kind.replace(/_/g, ' ') + '</td><td class="wrap">' + v.condition + '</td><td>' + sgn(v.x_move, 2) + '</td><td>' + sgn(v.x_threshold, 2) + '</td><td class="wrap">' + v.targets.join(', ') + '</td></tr>'; });
  el('etable').innerHTML = e;
  let g = '<tr><th class="l">Condition</th><th class="l">Target</th><th>Horizon</th><th>Claimed</th><th>Lift</th><th>Form. episodes</th><th>Test</th><th>Base</th><th>Test episodes</th></tr>';
  C.frozen.forEach(r => { g += '<tr><td class="wrap">' + r.condition + '</td><td class="l">' + r.target + ' ' + (r.direction === 'bullish' ? '&uarr;' : '&darr;') + '</td><td>' + r.horizon + '</td><td>' + f(r.claimed, 2) + '</td><td>' + f(r.lift, 2) + '</td><td>' + r.n_ep_f + '</td><td>' + f(r.test_cpe, 2) + '</td><td>' + f(r.test_base, 2) + '</td><td>' + r.n_ep_t + '</td></tr>'; });
  el('ftable').innerHTML = g;
  el('rnote').innerHTML = '<b>How outcomes are scored.</b> An event is the first day a condition crosses its frozen threshold (conditions already beyond it on the freeze date are logged once as ongoing). Each event fans out to every frozen row for that condition; the outcome is whether the target&rsquo;s forward move over the row&rsquo;s horizon lands beyond its frozen threshold in the stated direction. ' +
    'Claimed is the formation CPE, realised the live hit rate, table base the unconditional frequency in formation, live base the unconditional frequency since the freeze. Overlapping horizons are valid samples; no significance test is used. The longest horizons resolve in late 2027, so for now this is a record of conditions and what is pending.';
}

// ---------- shock monitor
{
  const G = S.gauges, gc = el('gcards');
  G.forEach(g => { const c = card(g.name, g.elevated ? 'elevated' : 'normal', g.elevated ? 'on' : 'ok', sgn(g.runup_pct_return, 1) + '%', g.frequency.split(', ')[1] + ' move',
      ['percentile of its own history: <b>' + f(g.runup_percentile, 0) + '</b> (floor before past restrictions: ' + S.runup_floor + ')', 'informs: ' + g.countries + ' &middot; last ' + g.last_date]); gc.appendChild(c); });
  const col = {'SB=F':'#C8A84A', 'ZW=F':'#7FAAD1', 'ZL=F':'#7FB08A'};
  Plotly.newPlot('gChart', G.filter(g => col[g.ticker]).map(g => ({x:g.series.map(r => r[0]), y:g.series.map(r => r[1]), name:g.name, type:'scatter', mode:'lines', line:{color:col[g.ticker], width:1.4}})),
    merge(BASE, {yaxis:merge(BASE.yaxis, {ticksuffix:'%'}), shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:0, y1:0, line:{color:'#3A3F3A', width:1}}]}), CFG);
  const R = S.record.runup, cls = {restrict:'#C9784A', relax_imports:'#5B8DBE', relax:'#5B8DBE'};
  Plotly.newPlot('uChart', [{x:R.map(r => r.event), y:R.map(r => r.pre_pct), type:'bar', marker:{color:R.map(r => cls[r.class] || '#7A8F7A')}, hovertemplate:'%{x}: percentile %{y}<extra></extra>'}],
    merge(BASE, {yaxis:merge(BASE.yaxis, {range:[0, 100], title:{text:'percentile', font:{size:9}}}), xaxis:merge(BASE.xaxis, {tickfont:{size:8}, type:'category'}), showlegend:false,
      shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:S.runup_floor, y1:S.runup_floor, line:{color:'#C8A84A', width:1, dash:'dot'}}]}), CFG);
  const el2 = G.filter(x => x.elevated).map(x => x.name + (x.frequency.indexOf('monthly') >= 0 ? ' (data to ' + x.last_date.slice(0, 7) + ')' : ''));
  el('gnote').innerHTML = '<b>Reading it.</b> All ' + S.record.restrict_runup_n + ' restrictions with daily futures came after a run-up at or above the ' + f(S.record.restrict_runup_min, 0) + 'th percentile (orange bars); the same run-up preceded the 2009 import liberalisation (blue). ' +
    'A high percentile is not a forecast of a ban: it marks the market where the conditions seen before past restrictions are present. Elevated now: <b>' + (el2.length ? el2.join(', ') : 'none') + '</b>. ' +
    'Climate state: <b>' + E.state + '</b> (ONI ' + sgn(E.oni, 2) + ' &deg;C), the driver behind the Indian monsoon shocks that preceded the 2009 and 2023 episodes.';
  let t = '<tr><th class="l">Episode</th><th class="l">Country</th><th class="l">Shock</th><th class="l">Stocks</th><th class="l">Price pressure</th><th class="l">Response</th></tr>';
  S.record.ledger.forEach(r => { const c = r.response_class.indexOf('restrict') === 0 ? 'hot' : ''; t += '<tr><td class="l">' + r.episode + '</td><td class="l">' + r.country + '</td><td class="wrap">' + r.shock_severity + '</td><td class="wrap">' + r.stocks_position + '</td><td class="wrap">' + r.domestic_price_pressure + '</td><td class="wrap"><span class="pill ' + c + '">' + r.response_class.replace(/_/g, ' ') + '</span> ' + r.response + '</td></tr>'; });
  el('ltable').innerHTML = t;
  let p = '<tr><th class="l">Event</th><th class="l">Commodity</th><th class="l">Action</th><th class="l">Date</th><th class="l">Weather link</th><th class="l">Verification</th></tr>';
  S.record.events.forEach(r => { p += '<tr><td class="l">' + r.id + '</td><td class="wrap">' + r.commodity + '</td><td class="wrap">' + r.action + '</td><td class="l">' + r.official_date + '</td><td class="l">' + r.weather_link + '</td><td class="wrap">' + r.verification + '</td></tr>'; });
  el('ptable').innerHTML = p;
  const rc = S.record.response_counts;
  el('snote').innerHTML = '<b>What the record shows.</b> Of ' + S.record.ledger.length + ' shock episodes, ' + Object.keys(rc).map(k => rc[k] + ' ' + k.replace(/_/g, ' ')).join(', ') + '. Restrictions came with thin stocks, high price pressure and no institutional constraint (WTO standing, reputation from an earlier ban); where stocks were large, governments exported or imported instead. ' +
    'The set is small by nature (rare, slow events), which is the point of the framework: few independent episodes, each carrying a clear mechanism. Dates and sources for every event are in the list above.';
}

(function () {
  const resizeAll = () => document.querySelectorAll('.js-plotly-plot').forEach(p => Plotly.Plots.resize(p));
  window.addEventListener('load', resizeAll); [100, 400, 1200].forEach(ms => setTimeout(resizeAll, ms));
  if (window.ResizeObserver) { let raf = null; const ro = new ResizeObserver(() => { if (raf) cancelAnimationFrame(raf); raf = requestAnimationFrame(resizeAll); }); ro.observe(document.body); }
  window.addEventListener('resize', resizeAll);
})();
</script></body></html>"""


def assemble():
    """Collect the three data sources into the page payload (each already fault-tolerant at its own level)."""
    from weatherdash import cpe_climate, shocks
    cpe = cpe_climate.payload()
    oni = cpe_climate.index_series("ONI").dropna()
    oni = oni[(oni.index >= "1990-01-01") & (oni.index <= datetime.now(timezone.utc).strftime("%Y-%m-%d"))]
    return {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "cpe": cpe, "shocks": shocks.payload(),
            "oni": [[str(d.date()), round(float(v), 2)] for d, v in oni.items()]}


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
