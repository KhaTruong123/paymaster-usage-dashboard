"""Fetch daily total transaction counts per chain for the window.

Primary source: growthepie public API (https://api.growthepie.com/v1/fundamentals.json, metric txcount).
Cross-check: L2BEAT public activity API (https://l2beat.com/api/scaling/activity/<slug>), L2s only.

Saves the filtered raw rows to data/raw/ and the daily table to data/raw/chain-txcounts-daily.csv.
"""

import csv
import json
import urllib.request
from datetime import datetime, timedelta, timezone

from common import CHAINS, RAW, WINDOW_END, WINDOW_START, ts, utc_day

UA = {"user-agent": "Mozilla/5.0 (paymaster-usage-dashboard; +https://github.com/KhaTruong123/paymaster-usage-dashboard)"}
GROWTHEPIE = "https://api.growthepie.com/v1/fundamentals.json"
L2BEAT = "https://l2beat.com/api/scaling/activity/{slug}?range=180d"


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.loads(r.read())


def window_days():
    d = datetime.strptime(WINDOW_START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(WINDOW_END, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    while d < end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def main():
    days = list(window_days())
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    gtp = get_json(GROWTHEPIE)
    keys = {v[1]: k for k, v in CHAINS.items()}
    gtp_rows = [r for r in gtp if r["metric_key"] in ("txcount", "aa_last7d") and r["origin_key"] in keys
                and WINDOW_START <= r["date"] < WINDOW_END]
    (RAW / "growthepie-fundamentals-window.json").write_text(
        json.dumps({"source": GROWTHEPIE, "fetched_at_utc": fetched_at, "rows": gtp_rows}, indent=1) + "\n")

    l2b = {}
    for chain, (_ds, _gk, slug, _sym) in CHAINS.items():
        if not slug:
            continue
        data = get_json(L2BEAT.format(slug=slug))["data"]["chart"]
        rows = [r for r in data["data"] if ts(WINDOW_START) <= r[0] < ts(WINDOW_END)]
        l2b[chain] = {"types": data["types"], "rows": rows}
    (RAW / "l2beat-activity-window.json").write_text(
        json.dumps({"source": L2BEAT, "fetched_at_utc": fetched_at, "chains": l2b}, indent=1) + "\n")

    table = {}
    for r in gtp_rows:
        if r["metric_key"] == "txcount":
            table[(keys[r["origin_key"]], r["date"])] = {"growthepie_txcount": int(r["value"])}
    for chain, v in l2b.items():
        i_count = v["types"].index("count")
        for row in v["rows"]:
            table.setdefault((chain, utc_day(row[0])), {})["l2beat_txcount"] = row[i_count]

    with open(RAW / "chain-txcounts-daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chain", "day", "growthepie_txcount", "l2beat_txcount"])
        for chain in CHAINS:
            for day in days:
                v = table.get((chain, day), {})
                w.writerow([chain, day, v.get("growthepie_txcount", ""), v.get("l2beat_txcount", "")])
    missing = [(c, d) for c in CHAINS for d in days if "growthepie_txcount" not in table.get((c, d), {})]
    print(f"fetched {fetched_at}; growthepie rows {len(gtp_rows)}; missing growthepie days: {missing}")


if __name__ == "__main__":
    main()
