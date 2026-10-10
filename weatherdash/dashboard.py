"""Build docs/index.html (single self-contained page, data embedded) from data/latest.json."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weather to Energy Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{--accent:#5B8DBE;--accent2:#7FAAD1;--bg:#0C0E0D;--s1:#141614;--s2:#1B1E1B;--bdr:#2C302C;--bdr2:#3A3F3A;
--text:#DDE8DD;--text2:#7A8F7A;--text3:#4A5A4A;--hot:#C9784A;--cold:#5B8DBE;--ok:#7FB08A;--warn:#C8A84A;
--mono:'IBM Plex Mono',monospace;--sans:'IBM Plex Sans',sans-serif;--r:10px;--gap:16px;--pad:20px;}
*{box-sizing:border-box;margin:0;padding:0}html{font-size:15px}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.6;min-height:100vh}
header{background:linear-gradient(160deg,#0C0E0D,#141a1e,#0C0E0D);border-bottom:1px solid var(--bdr);padding:18px var(--pad);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
.h-title{font-family:var(--mono);font-size:clamp(13px,2vw,17px);font-weight:600;color:var(--accent2)}
.h-sub{font-family:var(--mono);font-size:11px;color:var(--text2);letter-spacing:.06em;text-transform:uppercase;margin-top:2px}
.h-meta{font-family:var(--mono);font-size:11px;color:var(--text2);text-align:right;line-height:1.8}
main{max-width:1180px;margin:0 auto;padding:20px var(--pad) 10px}
.banner{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:var(--pad);margin-bottom:20px;font-size:13px;color:var(--text2);line-height:1.75}
.banner b{color:var(--text)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:var(--gap);margin-bottom:20px}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:var(--pad)}
.c-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.c-name{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--accent2)}
.pill{font-family:var(--mono);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;padding:2px 8px;border-radius:99px;border:1px solid var(--bdr2);color:var(--text2)}
.pill.hot{color:var(--hot);border-color:#5A3A25}.pill.cold{color:var(--cold);border-color:#2C4050}.pill.flat{color:var(--text2)}
.big{font-family:var(--mono);font-size:26px;font-weight:600;margin-top:8px}.big small{font-size:11px;color:var(--text2);font-weight:400}
.line{font-family:var(--mono);font-size:11px;color:var(--text2);margin-top:2px}
section{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);padding:var(--pad);margin-bottom:20px}
.s-title{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--accent2);text-transform:uppercase;letter-spacing:.06em}
.s-sub{font-family:var(--mono);font-size:11px;color:var(--text2);margin:4px 0 14px;line-height:1.7}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:var(--gap)}
.c-label{font-family:var(--mono);font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:12px}th,td{text-align:right;padding:6px 10px;border-bottom:1px solid var(--bdr);font-family:var(--mono)}
th:first-child,td:first-child{text-align:left}th{color:var(--text2);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.05em}
.note{font-size:12px;color:var(--text2);margin-top:12px;line-height:1.7}.table-wrap{overflow-x:auto}
footer{padding:24px var(--pad) 40px;text-align:center;font-family:var(--mono);font-size:10px;color:var(--text3);line-height:1.8}
</style></head><body>
<header><div><div class="h-title">Weather to Energy Dashboard</div>
<div class="h-sub">Forecast temperature, electricity demand, scored against what happened</div></div><div class="h-meta" id="hmeta"></div></header>
<main>
<div class="banner"><b>Pilot: US electricity demand.</b> Each day the ECMWF 00z forecast is turned into regional temperature, degree days and
electricity demand for six US grid regions, next to the demand that normal weather would imply. Every forecast is logged and scored against
observed temperature and demand once they are known, with climatology as the baseline. Wind and solar generation for the same regions is below; crop stress is next.</div>
<div class="cards" id="cards"></div>
<section id="regions"><div class="s-title">Demand forecast vs normal, next 14 days</div>
<div class="s-sub">Daily electricity demand, GWh per day. Solid: forecast weather. Dashed: demand at normal temperature for the date. Shaded: days beyond the point where the forecast has scored worse than normal weather.</div>
<div class="charts" id="charts"></div></section>
<section id="verify"><div class="s-title">How the forecasts have scored</div><div class="s-sub" id="vsub"></div>
<div class="charts"><div><div class="c-label">Demand error by lead day (MAPE, %)</div><div id="vMape"></div></div>
<div><div class="c-label">Temperature error by lead day (MAE, &deg;C)</div><div id="vTemp"></div></div></div>
<div class="table-wrap" id="vtable"></div><div class="note" id="vnote"></div></section>
<section id="renew"><div class="s-title">Wind and solar generation, next 14 days</div>
<div class="s-sub">Daily generation, GWh, from forecast wind at 100 m and surface solar radiation at each region&rsquo;s generation areas, mapped to EIA-reported output.
Solid: forecast weather. Dashed: generation under normal weather for the date. Levels are anchored to the last 28 days of observed output; shaded days are beyond where the forecast scores better than normal weather.</div>
<div class="table-wrap" id="rtable"></div>
<div class="charts" id="rcharts" style="margin-top:16px"></div></section>
<section id="rverify"><div class="s-title">How the wind and solar forecasts have scored</div><div class="s-sub" id="rsub"></div>
<div class="charts"><div><div class="c-label">Wind: generation error by lead day (MAPE, %)</div><div id="rWind"></div></div>
<div><div class="c-label">Solar: generation error by lead day (MAPE, %)</div><div id="rSolar"></div></div></div>
<div class="table-wrap" id="rvtable"></div><div class="note" id="rnote"></div></section>
</main>
<footer>Contains ECMWF open data (IFS), CC-BY-4.0 &middot; Observed temperature: ERA5 (Copernicus) via Open-Meteo, CC-BY-4.0 &middot; Demand: U.S. EIA Form 930<br>
Research record, not a trading or operational tool.</footer>
<script>
const D = __DATA__;
const LABEL = {ERCO:'ERCOT (Texas)',PJM:'PJM (Mid-Atlantic / Midwest)',CISO:'CAISO (California)',NYIS:'NYISO (New York)',ISNE:'ISO-NE (New England)',MISO:'MISO (Midcontinent)'};
const BASE = {paper_bgcolor:'transparent',plot_bgcolor:'transparent',height:230,margin:{l:48,r:10,t:6,b:40},
  font:{family:'IBM Plex Mono',size:10,color:'#7A8F7A'},xaxis:{gridcolor:'#1B1E1B',tickfont:{size:9}},yaxis:{gridcolor:'#1B1E1B',zeroline:false},
  legend:{orientation:'h',y:-0.28,font:{size:9}}};
const CFG = {displayModeBar:false,responsive:true};
document.getElementById('hmeta').innerHTML = 'Forecast ' + D.model + ' issued ' + D.issue_date + '<br>Updated ' + D.generated_utc + ' UTC';
const byReg = {}; D.forecast.forEach(r => (byReg[r.region] = byReg[r.region] || []).push(r));
const V = D.verification;
// last lead day (contiguous from 0) at which the forecast-driven demand error is still below the normal-weather error
function skillHorizon() {
  if (!V.n_resolved) return null;
  let last = null;
  for (const r of V.by_lead.filter(r => r.n >= 30)) { if (r.mape_fc <= r.mape_clim) last = r.lead; else break; }
  return last;
}
const SKILL = skillHorizon();
const cards = document.getElementById('cards'), charts = document.getElementById('charts');
Object.keys(byReg).forEach(reg => {
  const rows = byReg[reg].filter(r => r.lead_days <= 13), wk = rows.filter(r => r.lead_days <= 6);
  const mean = (a, f) => a.reduce((s, r) => s + f(r), 0) / a.length;
  const anom = (mean(wk, r => r.demand_fc_mwh) / mean(wk, r => r.demand_normal_mwh) - 1) * 100;
  const dT = mean(wk, r => r.t_fc_c - r.t_normal_c);
  const peak = rows.reduce((a, r) => (r.demand_fc_mwh - r.demand_normal_mwh > a.demand_fc_mwh - a.demand_normal_mwh ? r : a), rows[0]);
  const cls = anom > 2 ? 'hot' : anom < -2 ? 'cold' : 'flat', word = anom > 2 ? 'above normal' : anom < -2 ? 'below normal' : 'near normal';
  const c = document.createElement('div'); c.className = 'card';
  c.innerHTML = '<div class="c-head"><span class="c-name">' + LABEL[reg] + '</span><span class="pill ' + cls + '">' + word + '</span></div>' +
    '<div class="big">' + (anom >= 0 ? '+' : '') + anom.toFixed(1) + '% <small>demand vs normal, next 7 days</small></div>' +
    '<div class="line">temperature ' + (dT >= 0 ? '+' : '') + dT.toFixed(1) + ' &deg;C vs normal &middot; mean ' + mean(wk, r => r.demand_fc_mwh / 1000).toFixed(0) + ' GWh/day</div>' +
    '<div class="line">largest gap: ' + peak.valid_date + ' (' + ((peak.demand_fc_mwh / peak.demand_normal_mwh - 1) * 100).toFixed(1) + '%)</div>';
  cards.appendChild(c);
  const d = document.createElement('div'); d.innerHTML = '<div class="c-label">' + LABEL[reg] + '</div><div id="ch_' + reg + '"></div>'; charts.appendChild(d);
  Plotly.newPlot('ch_' + reg, [
    {x: rows.map(r => r.valid_date), y: rows.map(r => r.demand_fc_mwh / 1000), name: 'Forecast', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}, marker: {size: 4}},
    {x: rows.map(r => r.valid_date), y: rows.map(r => r.demand_normal_mwh / 1000), name: 'Normal', mode: 'lines', line: {color: '#7A8F7A', width: 1.5, dash: 'dot'}}
  ], Object.assign({}, BASE, {yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: ' GWh'},
    shapes: (SKILL !== null && rows.some(r => r.lead_days > SKILL)) ? [{type: 'rect', xref: 'x', yref: 'paper',
      x0: rows.find(r => r.lead_days === SKILL + 1).valid_date, x1: rows[rows.length - 1].valid_date, y0: 0, y1: 1,
      fillcolor: 'rgba(200,168,74,0.07)', line: {width: 0}}] : []}), CFG);
});
document.getElementById('vsub').innerHTML = V.n_resolved ?
  V.n_resolved.toLocaleString() + ' of ' + V.n_logged.toLocaleString() + ' logged forecast-days scored (issued ' + V.first_issue + ' to ' + V.last_issue + '). Baseline: demand at normal temperature for the date.' :
  V.n_logged.toLocaleString() + ' forecast-days logged, none scored yet (observed temperature arrives about 6 days behind).';
if (V.n_resolved) {
  const L = V.by_lead.filter(r => r.n >= 30);
  const x = L.map(r => r.lead);
  Plotly.newPlot('vMape', [
    {x: x, y: L.map(r => r.mape_fc), name: 'Forecast weather', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
    {x: x, y: L.map(r => r.mape_clim), name: 'Normal weather', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}},
    {x: x, y: L.map(r => r.mape_oracle), name: 'Observed weather (model limit)', mode: 'lines', line: {color: '#7FB08A', width: 1.5}}
  ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: '%', rangemode: 'tozero'}}), CFG);
  Plotly.newPlot('vTemp', [
    {x: x, y: L.map(r => r.t_mae_fc), name: 'Forecast', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
    {x: x, y: L.map(r => r.t_mae_clim), name: 'Normal', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}}
  ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: ' C', rangemode: 'tozero'}}), CFG);
  let t = '<table><tr><th>Region</th><th>Forecast-days</th><th>Demand error, forecast</th><th>Demand error, normal</th><th>Demand error, observed weather</th><th>Temp error, forecast</th><th>Temp error, normal</th></tr>';
  V.by_region.forEach(r => { t += '<tr><td>' + LABEL[r.region] + '</td><td>' + r.n.toLocaleString() + '</td><td>' + r.mape_fc.toFixed(2) + '%</td><td>' + r.mape_clim.toFixed(2) + '%</td><td>' + r.mape_oracle.toFixed(2) + '%</td><td>' + r.t_mae_fc.toFixed(2) + ' C</td><td>' + r.t_mae_clim.toFixed(2) + ' C</td></tr>'; });
  const o = V.overall; t += '<tr><td><b>All</b></td><td>' + o.n.toLocaleString() + '</td><td>' + o.mape_fc.toFixed(2) + '%</td><td>' + o.mape_clim.toFixed(2) + '%</td><td>' + o.mape_oracle.toFixed(2) + '%</td><td>' + o.t_mae_fc.toFixed(2) + ' C</td><td>' + o.t_mae_clim.toFixed(2) + ' C</td></tr></table>';
  document.getElementById('vtable').innerHTML = t;
}
document.getElementById('vnote').innerHTML =
  'Demand model: daily electricity demand regressed on heating and cooling degree days (base 65&deg;F, with squares), day of week and a trend, fitted per grid region on 2023 to 2025 and held out on 2026. ' +
  'On observed temperature the 2026 holdout error is ' + Object.keys(D.impact_model).map(k => k + ' ' + D.impact_model[k].test_mape_model_obs_temp.toFixed(1) + '% (climatology ' + D.impact_model[k].test_mape_climatology.toFixed(1) + '%)').join(', ') + '. ' +
  'Regional temperature is a population-weighted sample at each region&rsquo;s main load centres (approximate weights); the model has no holiday, humidity or behind-the-meter solar terms. ' +
  'Forecast issues from 1 June 2026 onward are archived ECMWF runs, scored exactly as they would have been live.';

// ---------------- wind and solar ----------------
(function () {
  const R = D.renewables; if (!R) return;
  const RV = R.verification;
  const KIND = {wind: 'Wind', solar: 'Solar'};
  function rskill(kind) {
    let last = null;
    for (const r of RV.by_lead.filter(r => r.resource === kind && r.n >= 30)) { if (r.nmae_fc <= r.nmae_clim) last = r.lead; else break; }
    return last;
  }
  const sk = {wind: rskill('wind'), solar: rskill('solar')};
  const series = {};
  R.forecast.forEach(r => { const k = r.region + '|' + r.resource; (series[k] = series[k] || []).push(r); });
  let t = '<table><tr><th>Region</th><th>Resource</th><th>Next 7 days, GWh/day</th><th>vs normal weather</th><th>Holdout error, observed weather</th></tr>';
  const charts = document.getElementById('rcharts');
  Object.keys(series).sort().forEach(k => {
    const rows = series[k].filter(r => r.lead_days <= 13), wk = rows.filter(r => r.lead_days <= 6);
    const [reg, kind] = k.split('|');
    const mean = (a, f) => a.reduce((s, r) => s + f(r), 0) / a.length;
    const anom = (mean(wk, r => r.gen_fc_mwh) / mean(wk, r => r.gen_normal_mwh) - 1) * 100;
    const im = R.impact_model[k];
    t += '<tr><td>' + LABEL[reg] + '</td><td>' + KIND[kind] + '</td><td>' + (mean(wk, r => r.gen_fc_mwh) / 1000).toFixed(1) + '</td><td>' +
      (anom >= 0 ? '+' : '') + anom.toFixed(0) + '%</td><td>' + im.test_nmae_model_obs_weather.toFixed(0) + '% (normal ' + im.test_nmae_normal_weather.toFixed(0) + '%)</td></tr>';
    const d = document.createElement('div');
    d.innerHTML = '<div class="c-label">' + LABEL[reg] + ' &mdash; ' + KIND[kind] + '</div><div id="rc_' + reg + '_' + kind + '"></div>';
    charts.appendChild(d);
    const cut = sk[kind];
    Plotly.newPlot('rc_' + reg + '_' + kind, [
      {x: rows.map(r => r.valid_date), y: rows.map(r => r.gen_fc_mwh / 1000), name: 'Forecast', mode: 'lines+markers', line: {color: kind === 'wind' ? '#5B8DBE' : '#C8A84A', width: 2}, marker: {size: 4}},
      {x: rows.map(r => r.valid_date), y: rows.map(r => r.gen_normal_mwh / 1000), name: 'Normal', mode: 'lines', line: {color: '#7A8F7A', width: 1.5, dash: 'dot'}}
    ], Object.assign({}, BASE, {yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: ' GWh', rangemode: 'tozero'},
      shapes: (cut !== null && rows.some(r => r.lead_days > cut)) ? [{type: 'rect', xref: 'x', yref: 'paper',
        x0: rows.find(r => r.lead_days === cut + 1).valid_date, x1: rows[rows.length - 1].valid_date, y0: 0, y1: 1,
        fillcolor: 'rgba(200,168,74,0.07)', line: {width: 0}}] : []}), CFG);
  });
  document.getElementById('rtable').innerHTML = t + '</table>';
  document.getElementById('rsub').innerHTML = RV.n_scored ?
    RV.n_scored.toLocaleString() + ' forecast-days scored after level calibration (issued ' + RV.first_issue + ' to ' + RV.last_issue + '; ' + RV.n_logged.toLocaleString() + ' logged). Baseline: generation under normal weather for the date.' :
    RV.n_logged.toLocaleString() + ' forecast-days logged, none scored yet.';
  ['wind', 'solar'].forEach(kind => {
    const L = RV.by_lead.filter(r => r.resource === kind && r.n >= 30); if (!L.length) return;
    const x = L.map(r => r.lead);
    Plotly.newPlot(kind === 'wind' ? 'rWind' : 'rSolar', [
      {x: x, y: L.map(r => r.nmae_fc), name: 'Forecast weather', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
      {x: x, y: L.map(r => r.nmae_clim), name: 'Normal weather', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}},
      {x: x, y: L.map(r => r.nmae_oracle), name: 'Observed weather', mode: 'lines', line: {color: '#7FB08A', width: 1.5}}
    ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: '%', rangemode: 'tozero'}}), CFG);
  });
  let v = '<table><tr><th>Region</th><th>Resource</th><th>Forecast-days</th><th>Error, forecast</th><th>Error, normal</th><th>Error, observed weather</th></tr>';
  RV.by_series.forEach(r => { v += '<tr><td>' + LABEL[r.region] + '</td><td>' + KIND[r.resource] + '</td><td>' + r.n.toLocaleString() + '</td><td>' + r.nmae_fc.toFixed(1) + '%</td><td>' + r.nmae_clim.toFixed(1) + '%</td><td>' + r.nmae_oracle.toFixed(1) + '%</td></tr>'; });
  document.getElementById('rvtable').innerHTML = v + '</table>';
  document.getElementById('rnote').innerHTML =
    'Wind: ERA5 or forecast wind at 100 m at candidate generation areas, through a generic turbine curve, weighted by site with weights learned from EIA output; solar: surface solar radiation, same method; both with a linear capacity-growth term fitted on 2023 to 2025. ' +
    'Daily generation from a few weather points is a rough measure, wind especially: even with observed weather the wind error is large, so wind levels should be read as a guide to windier or calmer than normal, not as a megawatt forecast. ' +
    'Error is the mean absolute error of daily generation as a percentage of the series&rsquo; mean daily output; rows count from the first issue with a calibration factor known at issue time (28-day window, at least 7 days old).';
})();
</script></body></html>"""


def build(latest_path=None, out_path=None):
    latest_path = latest_path or os.path.join(ROOT, "data", "latest.json")
    out_path = out_path or os.path.join(ROOT, "docs", "index.html")
    data = open(latest_path).read()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(PAGE.replace("__DATA__", data))
    return out_path


if __name__ == "__main__":
    print("wrote", build())
