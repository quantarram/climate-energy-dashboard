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
.charts>div{min-width:0;overflow:hidden}
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
electricity demand for six US grid regions, next to the demand that climatology would imply (the demand at the average temperature for that calendar date over __CD__). Every forecast is logged and scored against
observed temperature and demand once they are known, with climatology as the baseline. Wind and solar generation for the same regions, and crop stress for the US corn and soybean states, follow below.</div>
<div class="cards" id="cards"></div>
<section id="regions"><div class="s-title">Demand forecast vs climatology, next 14 days</div>
<div class="s-sub">Daily electricity demand, GWh per day. Solid: forecast weather. Dashed: climatology, the demand at the average temperature for that date (__CD__). Shaded: days beyond the point where the forecast has scored worse than climatology.</div>
<div class="charts" id="charts"></div></section>
<section id="verify"><div class="s-title">How the forecasts have scored</div><div class="s-sub" id="vsub"></div>
<div class="charts"><div><div class="c-label">Demand error by lead day (MAPE, %)</div><div id="vMape"></div></div>
<div><div class="c-label">Temperature error by lead day (MAE, &deg;C)</div><div id="vTemp"></div></div></div>
<div class="table-wrap" id="vtable"></div><div class="note" id="vnote"></div></section>
<section id="renew"><div class="s-title">Wind and solar generation, next 14 days</div>
<div class="s-sub">Daily generation, GWh, from forecast wind at 100 m and surface solar radiation at each region&rsquo;s generation areas, mapped to EIA-reported output.
Solid: forecast weather. Dashed: climatology, the generation under the average wind and sunshine for that date (__CR__). Levels are anchored to the last 28 days of observed output; shaded days are beyond where the forecast stops scoring better than climatology.</div>
<div class="table-wrap" id="rtable"></div>
<div class="charts" id="rcharts" style="margin-top:16px"></div></section>
<section id="rverify"><div class="s-title">How the wind and solar forecasts have scored</div><div class="s-sub" id="rsub"></div>
<div class="charts"><div><div class="c-label">Wind: generation error by lead day (MAPE, %)</div><div id="rWind"></div></div>
<div><div class="c-label">Solar: generation error by lead day (MAPE, %)</div><div id="rSolar"></div></div></div>
<div class="table-wrap" id="rvtable"></div><div class="note" id="rnote"></div></section>
<section id="crops"><div class="s-title">Crop stress: US corn and soybean states, next full weeks</div>
<div class="s-sub" id="csub"></div>
<div class="table-wrap" id="ctable"></div></section>
<section id="cverify"><div class="s-title">How the crop-stress forecasts have scored</div><div class="s-sub" id="cvsub"></div>
<div class="charts"><div><div class="c-label">Weekly heat-stress degree days (above 30 &deg;C): forecast error by lead (MAE)</div><div id="cKdd"></div></div>
<div><div class="c-label">Weekly afternoon vapour-pressure deficit (kPa): forecast error by lead (MAE)</div><div id="cVpd"></div></div>
<div><div class="c-label">Weekly rainfall (mm): forecast error by lead (MAE)</div><div id="cRain"></div></div>
<div><div class="c-label">Weekly change in good+excellent rating (points): error vs baselines (MAE)</div><div id="cCond"></div></div></div>
<div class="table-wrap" id="cvtable"></div><div class="note" id="cnote"></div></section>
</main>
<footer>Contains ECMWF open data (IFS), CC-BY-4.0 &middot; Observed temperature: ERA5 (Copernicus) via Open-Meteo, CC-BY-4.0 &middot; Demand: U.S. EIA Form 930<br>
Research record, not a trading or operational tool.</footer>
<script>
const D = __DATA__;
const LABEL = {ERCO:'ERCOT (Texas)',PJM:'PJM (Mid-Atlantic / Midwest)',CISO:'CAISO (California)',NYIS:'NYISO (New York)',ISNE:'ISO-NE (New England)',MISO:'MISO (Midcontinent)'};
const BASE = {paper_bgcolor:'transparent',plot_bgcolor:'transparent',height:250,margin:{l:52,r:12,t:30,b:34},
  font:{family:'IBM Plex Mono',size:10,color:'#7A8F7A'},
  xaxis:{gridcolor:'#1B1E1B',tickfont:{size:9},tickformat:'%b %d',nticks:6,automargin:true},
  yaxis:{gridcolor:'#1B1E1B',zeroline:false,automargin:true},
  legend:{orientation:'h',x:0,xanchor:'left',y:1.14,yanchor:'bottom',font:{size:9},entrywidth:105,entrywidthmode:'pixels',itemwidth:30}};
const CFG = {displayModeBar:false,responsive:true};
document.getElementById('hmeta').innerHTML = 'Forecast ' + D.model + ' issued ' + D.issue_date + '<br>Updated ' + D.generated_utc + ' UTC';
const byReg = {}; D.forecast.forEach(r => (byReg[r.region] = byReg[r.region] || []).push(r));
const V = D.verification;
// last lead day (contiguous from 0) at which the forecast-driven demand error is still below the climatology error
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
  const anom = (mean(wk, r => r.demand_fc_mwh) / mean(wk, r => r.demand_clim_mwh) - 1) * 100;
  const dT = mean(wk, r => r.t_fc_c - r.t_clim_c);
  const peak = rows.reduce((a, r) => (r.demand_fc_mwh - r.demand_clim_mwh > a.demand_fc_mwh - a.demand_clim_mwh ? r : a), rows[0]);
  const cls = anom > 2 ? 'hot' : anom < -2 ? 'cold' : 'flat', word = anom > 2 ? 'above climatology' : anom < -2 ? 'below climatology' : 'near climatology';
  const c = document.createElement('div'); c.className = 'card';
  c.innerHTML = '<div class="c-head"><span class="c-name">' + LABEL[reg] + '</span><span class="pill ' + cls + '">' + word + '</span></div>' +
    '<div class="big">' + (anom >= 0 ? '+' : '') + anom.toFixed(1) + '% <small>demand vs climatology, next 7 days</small></div>' +
    '<div class="line">temperature ' + (dT >= 0 ? '+' : '') + dT.toFixed(1) + ' &deg;C vs climatology &middot; mean ' + mean(wk, r => r.demand_fc_mwh / 1000).toFixed(0) + ' GWh/day</div>' +
    '<div class="line">largest gap: ' + peak.valid_date + ' (' + ((peak.demand_fc_mwh / peak.demand_clim_mwh - 1) * 100).toFixed(1) + '%)</div>';
  cards.appendChild(c);
  const d = document.createElement('div'); d.innerHTML = '<div class="c-label">' + LABEL[reg] + '</div><div id="ch_' + reg + '"></div>'; charts.appendChild(d);
  Plotly.newPlot('ch_' + reg, [
    {x: rows.map(r => r.valid_date), y: rows.map(r => r.demand_fc_mwh / 1000), name: 'Forecast', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}, marker: {size: 4}},
    {x: rows.map(r => r.valid_date), y: rows.map(r => r.demand_clim_mwh / 1000), name: 'Climatology', mode: 'lines', line: {color: '#7A8F7A', width: 1.5, dash: 'dot'}}
  ], Object.assign({}, BASE, {showlegend: false, margin: {l: 56, r: 12, t: 10, b: 34}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: ' GWh', automargin: true},
    shapes: (SKILL !== null && rows.some(r => r.lead_days > SKILL)) ? [{type: 'rect', xref: 'x', yref: 'paper',
      x0: rows.find(r => r.lead_days === SKILL + 1).valid_date, x1: rows[rows.length - 1].valid_date, y0: 0, y1: 1,
      fillcolor: 'rgba(200,168,74,0.07)', line: {width: 0}}] : []}), CFG);
});
document.getElementById('vsub').innerHTML = V.n_resolved ?
  V.n_resolved.toLocaleString() + ' of ' + V.n_logged.toLocaleString() + ' logged forecast-days scored (issued ' + V.first_issue + ' to ' + V.last_issue + '). Baseline: climatology, the demand at the average temperature for the date (__CD__).' :
  V.n_logged.toLocaleString() + ' forecast-days logged, none scored yet (observed temperature arrives about 6 days behind).';
if (V.n_resolved) {
  const L = V.by_lead.filter(r => r.n >= 30);
  const x = L.map(r => r.lead);
  Plotly.newPlot('vMape', [
    {x: x, y: L.map(r => r.mape_fc), name: 'Forecast weather', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
    {x: x, y: L.map(r => r.mape_clim), name: 'Climatology', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}},
    {x: x, y: L.map(r => r.mape_oracle), name: 'Observed weather (model limit)', mode: 'lines', line: {color: '#7FB08A', width: 1.5}}
  ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: '%', rangemode: 'tozero'}}), CFG);
  Plotly.newPlot('vTemp', [
    {x: x, y: L.map(r => r.t_mae_fc), name: 'Forecast', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
    {x: x, y: L.map(r => r.t_mae_clim), name: 'Climatology', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}}
  ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: ' C', rangemode: 'tozero'}}), CFG);
  let t = '<table><tr><th>Region</th><th>Forecast-days</th><th>Demand error, forecast</th><th>Demand error, climatology</th><th>Demand error, observed weather</th><th>Temp error, forecast</th><th>Temp error, climatology</th></tr>';
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
  let t = '<table><tr><th>Region</th><th>Resource</th><th>Next 7 days, GWh/day</th><th>vs climatology</th><th>Holdout error, observed weather</th></tr>';
  const charts = document.getElementById('rcharts');
  Object.keys(series).sort().forEach(k => {
    const rows = series[k].filter(r => r.lead_days <= 13), wk = rows.filter(r => r.lead_days <= 6);
    const [reg, kind] = k.split('|');
    const mean = (a, f) => a.reduce((s, r) => s + f(r), 0) / a.length;
    const anom = (mean(wk, r => r.gen_fc_mwh) / mean(wk, r => r.gen_clim_mwh) - 1) * 100;
    const im = R.impact_model[k];
    t += '<tr><td>' + LABEL[reg] + '</td><td>' + KIND[kind] + '</td><td>' + (mean(wk, r => r.gen_fc_mwh) / 1000).toFixed(1) + '</td><td>' +
      (anom >= 0 ? '+' : '') + anom.toFixed(0) + '%</td><td>' + im.test_nmae_model_obs_weather.toFixed(0) + '% (climatology ' + im.test_nmae_climatology.toFixed(0) + '%)</td></tr>';
    const d = document.createElement('div');
    d.innerHTML = '<div class="c-label">' + LABEL[reg] + ' &mdash; ' + KIND[kind] + '</div><div id="rc_' + reg + '_' + kind + '"></div>';
    charts.appendChild(d);
    const cut = sk[kind];
    Plotly.newPlot('rc_' + reg + '_' + kind, [
      {x: rows.map(r => r.valid_date), y: rows.map(r => r.gen_fc_mwh / 1000), name: 'Forecast', mode: 'lines+markers', line: {color: kind === 'wind' ? '#5B8DBE' : '#C8A84A', width: 2}, marker: {size: 4}},
      {x: rows.map(r => r.valid_date), y: rows.map(r => r.gen_clim_mwh / 1000), name: 'Climatology', mode: 'lines', line: {color: '#7A8F7A', width: 1.5, dash: 'dot'}}
    ], Object.assign({}, BASE, {showlegend: false, margin: {l: 56, r: 12, t: 10, b: 34}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: ' GWh', rangemode: 'tozero', automargin: true},
      shapes: (cut !== null && rows.some(r => r.lead_days > cut)) ? [{type: 'rect', xref: 'x', yref: 'paper',
        x0: rows.find(r => r.lead_days === cut + 1).valid_date, x1: rows[rows.length - 1].valid_date, y0: 0, y1: 1,
        fillcolor: 'rgba(200,168,74,0.07)', line: {width: 0}}] : []}), CFG);
  });
  document.getElementById('rtable').innerHTML = t + '</table>';
  document.getElementById('rsub').innerHTML = RV.n_scored ?
    RV.n_scored.toLocaleString() + ' forecast-days scored after level calibration (issued ' + RV.first_issue + ' to ' + RV.last_issue + '; ' + RV.n_logged.toLocaleString() + ' logged). Baseline: climatology (__CR__).' :
    RV.n_logged.toLocaleString() + ' forecast-days logged, none scored yet.';
  ['wind', 'solar'].forEach(kind => {
    const L = RV.by_lead.filter(r => r.resource === kind && r.n >= 30); if (!L.length) return;
    const x = L.map(r => r.lead);
    Plotly.newPlot(kind === 'wind' ? 'rWind' : 'rSolar', [
      {x: x, y: L.map(r => r.nmae_fc), name: 'Forecast weather', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
      {x: x, y: L.map(r => r.nmae_clim), name: 'Climatology', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}},
      {x: x, y: L.map(r => r.nmae_oracle), name: 'Observed weather', mode: 'lines', line: {color: '#7FB08A', width: 1.5}}
    ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, ticksuffix: '%', rangemode: 'tozero'}}), CFG);
  });
  let v = '<table><tr><th>Region</th><th>Resource</th><th>Forecast-days</th><th>Error, forecast</th><th>Error, climatology</th><th>Error, observed weather</th></tr>';
  RV.by_series.forEach(r => { v += '<tr><td>' + LABEL[r.region] + '</td><td>' + KIND[r.resource] + '</td><td>' + r.n.toLocaleString() + '</td><td>' + r.nmae_fc.toFixed(1) + '%</td><td>' + r.nmae_clim.toFixed(1) + '%</td><td>' + r.nmae_oracle.toFixed(1) + '%</td></tr>'; });
  document.getElementById('rvtable').innerHTML = v + '</table>';
  document.getElementById('rnote').innerHTML =
    'Wind: ERA5 or forecast wind at 100 m at candidate generation areas, through a generic turbine curve, weighted by site with weights learned from EIA output; solar: surface solar radiation, same method; both with a linear capacity-growth term fitted on 2023 to 2025. ' +
    'Daily generation from a few weather points is a rough measure, wind especially: even with observed weather the wind error is large, so wind levels should be read as a guide to windier or calmer than climatology, not as a megawatt forecast. ' +
    'Error is the mean absolute error of daily generation as a percentage of the series&rsquo; mean daily output; rows count from the first issue with a calibration factor known at issue time (28-day window, at least 7 days old).';
})();

// ---------------- crop stress ----------------
(function () {
  const C = D.crops; if (!C) return;
  const CV = C.verification;
  const iso = d => { const t = new Date(d + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7)); const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1)); return Math.ceil(((t - y0) / 86400000 + 1) / 7); };
  const inSeason = C.forecast.some(r => r.dge_corn_fc !== null || r.dge_soybeans_fc !== null);
  document.getElementById('csub').innerHTML = inSeason ?
    'Weeks run Monday to Sunday, as in the USDA crop condition reports. Drivers are averages over each state&rsquo;s main growing areas. The rating change is the model&rsquo;s expected week-on-week move in the share of the crop rated good or excellent, for the ten-state average only: single-state weekly moves are mostly survey noise.' :
    'Corn and soybean condition ratings run from about June to mid-September, so the condition outlook is switched off until the next season; the weather drivers below run all year. Scored results from the 2026 season are underneath.';
  const wk = {}; C.forecast.forEach(r => (wk[r.week_ending] = wk[r.week_ending] || []).push(r));
  const weeks = Object.keys(wk).sort();
  let t = '';
  const fmt = (v, d) => (v === null || v === undefined) ? '&ndash;' : v.toFixed(d);
  const sgn = (v, d) => (v === null || v === undefined) ? '&ndash;' : (v >= 0 ? '+' : '') + v.toFixed(d);
  weeks.forEach(we => {
    t += '<div class="c-label" style="margin-top:14px">Week ending ' + we + '</div><table><tr><th>State</th><th>Heat degree-days</th><th>vs climatology</th><th>Hot days (&gt;35 &deg;C)</th><th>Afternoon VPD, kPa</th><th>vs climatology</th><th>Rain, mm</th><th>vs climatology</th>' +
      (inSeason ? '<th>Corn rating change</th><th>Soy rating change</th>' : '') + '</tr>';
    const rows = wk[we].slice().sort((a, b) => (a.state === 'ALL' ? -1 : b.state === 'ALL' ? 1 : a.state.localeCompare(b.state)));
    rows.forEach(r => {
      const all = r.state === 'ALL';
      t += '<tr' + (all ? ' style="font-weight:600;color:var(--text)"' : '') + '><td>' + (all ? 'Ten-state average' : r.state) + '</td><td>' + fmt(r.kdd_fc, 1) + '</td><td>' + sgn(r.kdd_fc - r.kdd_clim, 1) + '</td><td>' + fmt(r.hot_days_fc, 1) + '</td><td>' + fmt(r.vpd_fc, 2) + '</td><td>' + sgn(r.vpd_fc - r.vpd_clim, 2) + '</td><td>' + fmt(r.rain_fc, 0) + '</td><td>' + sgn(r.rain_fc - r.rain_clim, 0) + '</td>' +
        (inSeason ? '<td>' + (all ? sgn(r.dge_corn_fc, 1) + ' pts' : '&ndash;') + '</td><td>' + (all ? sgn(r.dge_soybeans_fc, 1) + ' pts' : '&ndash;') + '</td>' : '') + '</tr>';
    });
    t += '</table>';
  });
  document.getElementById('ctable').innerHTML = t || '<div class="note">No full forecast week yet.</div>';
  document.getElementById('cvsub').innerHTML = CV.n_weather ?
    CV.n_weather.toLocaleString() + ' ten-state-average weeks scored on weather drivers and ' + CV.n_condition.toLocaleString() + ' on crop-condition change (issued ' + CV.first_issue + ' to ' + CV.last_issue + '; ' + CV.n_logged.toLocaleString() + ' logged). Baseline: climatology, the __CC__ average for that week of the year.' :
    CV.n_logged.toLocaleString() + ' state-weeks logged, none scored yet.';
  [['kdd', 'cKdd', ''], ['vpd', 'cVpd', ''], ['rain', 'cRain', '']].forEach(([f, id]) => {
    const L = CV.weather.filter(r => r.feature === f); if (!L.length) return;
    Plotly.newPlot(id, [
      {x: L.map(r => r.lead), y: L.map(r => r.mae_fc), name: 'Forecast', mode: 'lines+markers', line: {color: '#5B8DBE', width: 2}},
      {x: L.map(r => r.lead), y: L.map(r => r.mae_clim), name: 'Climatology', mode: 'lines', line: {color: '#B5726A', width: 1.8, dash: 'dot'}}
    ], Object.assign({}, BASE, {xaxis: {title: {text: 'lead to week end (days)', font: {size: 9}}, gridcolor: '#1B1E1B'}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, rangemode: 'tozero'}}), CFG);
  });
  if (CV.condition.length) {
    const x = CV.condition.map(r => r.crop === 'corn' ? 'Corn (n=' + r.n + ')' : 'Soybeans (n=' + r.n + ')');
    Plotly.newPlot('cCond', [
      {x: x, y: CV.condition.map(r => r.mae_fc), name: 'Forecast', type: 'bar', marker: {color: '#5B8DBE'}, text: CV.condition.map(r => r.mae_fc.toFixed(2)), textposition: 'outside'},
      {x: x, y: CV.condition.map(r => r.mae_clim), name: 'Climatological change', type: 'bar', marker: {color: '#B5726A'}, text: CV.condition.map(r => r.mae_clim.toFixed(2)), textposition: 'outside'},
      {x: x, y: CV.condition.map(r => r.mae_zero), name: 'No change', type: 'bar', marker: {color: '#7A8F7A'}, text: CV.condition.map(r => r.mae_zero.toFixed(2)), textposition: 'outside'}
    ], Object.assign({}, BASE, {barmode: 'group', xaxis: {type: 'category', tickfont: {size: 9}}, yaxis: {gridcolor: '#1B1E1B', zeroline: false, rangemode: 'tozero', ticksuffix: ' pts'}}), CFG);
  }
  let v = '<table><tr><th>Crop</th><th>Weeks scored (live)</th><th>Error, forecast-driven</th><th>Error, climatological change</th><th>Error, no change</th><th>Correlation (forecast, actual)</th><th>Leave-one-year-out, 12 seasons: model / climatology / no change (points)</th></tr>';
  CV.condition.forEach(r => { const m = C.model[r.crop.toUpperCase()]; v += '<tr><td>' + (r.crop === 'corn' ? 'Corn' : 'Soybeans') + '</td><td>' + r.n.toLocaleString() + '</td><td>' + r.mae_fc.toFixed(2) + ' pts</td><td>' + r.mae_clim.toFixed(2) + ' pts</td><td>' + r.mae_zero.toFixed(2) + ' pts</td><td>' + r.corr.toFixed(2) + '</td><td>' + m.loyo_mae_model.toFixed(2) + ' / ' + m.loyo_mae_clim.toFixed(2) + ' / ' + m.loyo_mae_zero.toFixed(2) + ' (r = ' + m.loyo_corr.toFixed(2) + ', ' + m.n_weeks + ' weeks)' + '</td></tr>'; });
  document.getElementById('cvtable').innerHTML = v + '</table>';
  document.getElementById('cnote').innerHTML =
    'Weather drivers come from the forecast at three points in each state&rsquo;s main growing areas (approximate locations): heat-stress degree days are daily maximum temperature above 30 &deg;C, summed over the week; vapour-pressure deficit is the 12:00 to 18:00 local mean; rainfall is the weekly total. ' +
    'The condition model is a ridge regression of the ten-state average week-on-week change in the share rated good or excellent on those drivers and a seasonal term, for ISO weeks 22 to 38 (about June to mid-September). Its skill is estimated by leaving each season out in turn (2015 to 2026), in the table above; the live columns score each issued forecast. Forecast drivers are adjusted for a small measured offset against ERA5 (about 0.5 &deg;C on daily maximum, 0.1 kPa on VPD). ' +
    'Weekly condition change is a noisy target (the ratings are survey-based), so the baselines to beat are the climatological change for that week of the year (the __CC__ average) and no change at all.';
})();
// Plotly sizes each chart to its container when it is created. The first charts are created while the page is still
// short and the grid has not settled (no scrollbar yet), so they come out too wide and spill into their neighbours.
// Resize every chart once layout is final, and again whenever the page or a grid changes size.
(function () {
  const resizeAll = () => document.querySelectorAll('.js-plotly-plot').forEach(p => Plotly.Plots.resize(p));
  window.addEventListener('load', resizeAll);
  [100, 400, 1200].forEach(ms => setTimeout(resizeAll, ms));
  if (window.ResizeObserver) {
    let raf = null;
    const ro = new ResizeObserver(() => { if (raf) cancelAnimationFrame(raf); raf = requestAnimationFrame(resizeAll); });
    ro.observe(document.body);
    document.querySelectorAll('.charts').forEach(g => ro.observe(g));
  }
  window.addEventListener('resize', resizeAll);
})();
</script></body></html>"""


def build(latest_path=None, out_path=None):
    latest_path = latest_path or os.path.join(ROOT, "data", "latest.json")
    out_path = out_path or os.path.join(ROOT, "docs", "index.html")
    data = open(latest_path).read()
    cl = json.loads(data).get("climatology", {})
    dash = "\u2013"
    fmt = lambda k, unit: (f"{cl[k]['years'].replace('-', dash)}, {cl[k]['n_years']} {unit}" if k in cl else "")
    html = (PAGE.replace("__CD__", fmt("demand", "years")).replace("__CR__", fmt("renewables", "years"))
            .replace("__CC__", fmt("crops", "seasons")))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(html.replace("__DATA__", data))
    return out_path


if __name__ == "__main__":
    print("wrote", build())
