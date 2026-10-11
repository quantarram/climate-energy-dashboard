"""Daily summary of the Climate Signals dashboard: what changed since the previous day's committed payload.

  python pipelines/daily_summary.py            # compare data/signals.json with the version committed about a day earlier
  python pipelines/daily_summary.py --prev REV # compare with data/signals.json at git revision REV

Reads only committed data (data/signals.json and its git history), so it can be run after the daily workflow has pushed.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True).stdout


def load_prev(rev):
    if rev is None:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rev = git("log", f"--before={cutoff}", "-n1", "--format=%H", "--", "data/signals.json").strip()
    if not rev:
        return None, None
    txt = git("show", f"{rev}:data/signals.json")
    return (json.loads(txt) if txt else None), git("show", "-s", "--format=%cs %h", rev).strip()


def fire_set(d):
    out = {}
    for b in d["cpe"]["books"]:
        for w in b["watch"]:
            if w["firing"]:
                out[(b["id"], w["condition"], w["direction"])] = [t["name"] for t in w["targets"]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prev")
    args = ap.parse_args()
    cur = json.load(open(os.path.join(ROOT, "data", "signals.json")))
    prev, prev_tag = load_prev(args.prev)
    A, D = cur["cpe"], cur["decisions"]
    L = []
    L.append(f"CLIMATE SIGNALS: daily summary (data through {A['asof']}, page updated {cur['generated_utc']} UTC; compared with {prev_tag or 'no earlier version'})")
    E = A["enso"]
    L.append(f"\nClimate state: ONI {E['oni']:+.2f} C ({E['state']}, published {E['oni_available']}); Nino 3.4 {E['nino34_anom']:+.2f} C (published {E['nino34_available']})")
    if prev:
        pe = prev["cpe"]["enso"]
        if (pe["oni"], pe["nino34_anom"]) != (E["oni"], E["nino34_anom"]):
            L.append(f"  changed since last version: ONI {pe['oni']:+.2f} -> {E['oni']:+.2f}, Nino 3.4 {pe['nino34_anom']:+.2f} -> {E['nino34_anom']:+.2f}")
    # conditions
    tot = sum(len(b["watch"]) for b in A["books"]); fire = sum(sum(w["firing"] for w in b["watch"]) for b in A["books"])
    L.append(f"\nConditions: {fire} of {tot} firing across {len(A['books'])} frozen tables")
    for b in A["books"]:
        L.append(f"  {b['id']}: {sum(w['firing'] for w in b['watch'])} of {len(b['watch'])} firing ({b['stats']['n_table_rows']} rows, frozen {b['frozen_on']})")
    if prev:
        c, p = fire_set(cur), fire_set(prev)
        new, gone = [k for k in c if k not in p], [k for k in p if k not in c]
        L.append(f"\nSince the last version: {len(new)} newly firing, {len(gone)} stopped firing, {sum(b['stats']['n_events'] for b in A['books']) - sum(b['stats']['n_events'] for b in prev['cpe']['books'])} new entry event(s) logged")
        for k in new:
            L.append(f"  NEW   [{k[0]}] {k[1]} -> {', '.join(c[k])} ({'rises' if k[2] == 'bullish' else 'falls'})")
        for k in gone:
            L.append(f"  ENDED [{k[0]}] {k[1]} -> {', '.join(p[k])}")
    # outcomes
    res = sum(b["stats"]["n_resolved"] for b in A["books"]); pend = sum(b["stats"]["n_pending"] for b in A["books"])
    L.append(f"\nOutcomes: {res} resolved, {pend} pending")
    firsts = sorted({r["first_pending"] for b in A["books"] for r in b["stats"]["by_horizon"] if r.get("first_pending")})
    if firsts:
        L.append(f"  first outcomes resolve about {firsts[0]}")
    for b in A["books"]:
        for r in b["stats"]["by_horizon"]:
            if r.get("n"):
                L.append(f"  [{b['id']}] {r['horizon']}d: {r['n']} resolved, realised {r['hit']:.2f} vs claimed {r['claimed']:.2f}, live base {r['live_base']:.2f}")
    # decision experiment
    L.append(f"\nRegistered decision experiment: {D['status'].replace('_', ' ')}, {D['n_days']} trading day(s) scored (next review at {next((r for r in D['review_points'] if r > D['n_days']), '')})")
    for t in D["today"]:
        L.append(f"  {t['side'].upper():5s} {t['name']} weight {t['weight']:+.2f} ({t['supporting_rows']} row(s), until about {t['expires_about']})")
    if prev:
        a, b2 = {t["target"]: t["side"] for t in D["today"]}, {t["target"]: t["side"] for t in prev["decisions"]["today"]}
        if a != b2:
            L.append(f"  POSITION CHANGE: {b2} -> {a}")
    lv = D.get("live", {})
    if lv.get("strategy"):
        s, h, x = lv["strategy"], lv["hold_same"], lv["excess_vs_drift"]
        L.append(f"  live net return {s['ann_return']*100:+.1f}% annualised, total {s['total']*100:+.2f}%; same targets held {h['total']*100:+.2f}%; drift-adjusted excess {x['total']*100:+.2f}%")
    else:
        L.append("  no live return yet (needs at least 5 scored days)")
    L.append("\nThe dashboard is a research record, not advice. The decision experiment gives a verdict only at its reviews (125, 250, 500 trading days).")
    print("\n".join(L))


if __name__ == "__main__":
    main()
