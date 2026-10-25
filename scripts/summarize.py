"""Join the committed raw tables into the published numbers in docs/data/.

Inputs (all in the repo):
  data/raw/userops-daily-paymaster-<chain>.csv   from aggregate_userops.py
  data/raw/bundles-daily-<chain>.csv             from aggregate_userops.py
  data/raw/paymaster-mode-events-daily-<chain>.csv  from extract_paymaster_mode_events.py
  data/raw/chain-txcounts-daily.csv              from fetch_chain_txcounts.py
  data/raw/charged-tokens.csv                    from resolve_tokens.py
  data/raw/paymaster-token-getter.csv            from resolve_tokens.py
  data/paymaster-labels.csv                      one source URL per row, see data/paymaster-labels-notes.md
  data/stablecoins.csv                           hand-curated, one issuer source URL per row
  docs/evidence/work-file-<chain>.json           distinct senders over the window

Outputs: docs/data/summary-by-chain.csv, paymasters.csv, daily.csv, erc20-tokens.csv, summary.json
"""

import csv
import json
from collections import defaultdict

from common import CHAINS, EVIDENCE, OUT, RAW, ROOT, WINDOW_END, WINDOW_START

ZERO = "0x" + "0" * 40
TOP_PAYMASTERS_PER_CHAIN = 25


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def pct(a, b):
    return round(100.0 * a / b, 4) if b else None


def main():
    labels = {r["address"].lower(): r for r in read(ROOT / "data" / "paymaster-labels.csv")}
    stables = {(r["chain"], r["address"].lower()): r for r in read(ROOT / "data" / "stablecoins.csv")}
    symbols = {(r["chain"], r["token"]): r["onchain_symbol"] for r in read(RAW / "charged-tokens.csv")}
    getter = {(r["chain"], r["paymaster"]): r["token"] for r in read(RAW / "paymaster-token-getter.csv")}
    txcounts = defaultdict(dict)
    for r in read(RAW / "chain-txcounts-daily.csv"):
        txcounts[r["chain"]][r["day"]] = r

    summary_rows, paymaster_rows, daily_rows, token_rows = [], [], [], []
    for chain in CHAINS:
        ops_rows = read(RAW / f"userops-daily-paymaster-{chain}.csv")
        bundle_rows = read(RAW / f"bundles-daily-{chain}.csv")
        mode_rows = read(RAW / f"paymaster-mode-events-daily-{chain}.csv")
        work = json.loads((EVIDENCE / f"work-file-{chain}.json").read_text())

        pm_ops = defaultdict(int)
        pm_eps = defaultdict(set)
        day_ops, day_pm_ops = defaultdict(int), defaultdict(int)
        pm_day_ops = defaultdict(lambda: defaultdict(int))
        total = success = 0
        for r in ops_rows:
            n = int(r["ops"])
            total += n
            success += int(r["ops_success"])
            day_ops[r["day"]] += n
            if r["paymaster"] != ZERO:
                pm_ops[r["paymaster"]] += n
                pm_eps[r["paymaster"]].add(r["entrypoint"])
                day_pm_ops[r["day"]] += n
                pm_day_ops[r["paymaster"]][r["day"]] += n
        with_pm = sum(pm_ops.values())

        # ERC-20 mode events only count when the emitter is a paymaster seen in UserOperationEvent.
        erc20_by_pm = defaultdict(int)
        mode_events_by_pm = defaultdict(int)
        token_ops = defaultdict(int)
        day_erc20, day_stable = defaultdict(int), defaultdict(int)
        for r in mode_rows:
            if r["emitter"] not in pm_ops:
                continue
            n = int(r["events"])
            if r["token"] == "token()":
                r["token"] = getter.get((chain, r["emitter"])) or "unknown"
            mode_events_by_pm[r["emitter"]] += n
            if r["erc20_mode"] == "1":
                erc20_by_pm[r["emitter"]] += n
                token_ops[r["token"]] += n
                day_erc20[r["day"]] += n
                if (chain, r["token"]) in stables:
                    day_stable[r["day"]] += n
        # ERC-20-only contracts (by sourced label) that emit no recognized per-op event: every op is
        # ERC-20 by construction, but the token is not visible in logs.
        def label_for(pm):
            lab = labels.get(pm, {})
            return lab if lab and (lab["chains"] == "all" or chain in lab["chains"].split(",")) else {}

        for pm, n in pm_ops.items():
            if label_for(pm).get("type") == "erc20" and mode_events_by_pm.get(pm, 0) == 0:
                erc20_by_pm[pm] += n
                token_ops["unknown (erc20-only paymaster, no per-op event)"] += n
                for day, k in pm_day_ops[pm].items():
                    day_erc20[day] += k
        erc20 = sum(erc20_by_pm.values())
        stable = sum(n for t, n in token_ops.items() if (chain, t) in stables)

        bundles = sum(int(r["bundle_txs"]) for r in bundle_rows)
        bundles_pm = sum(int(r["bundle_txs_with_paymaster_op"]) for r in bundle_rows)
        gtp = sum(int(v["growthepie_txcount"]) for v in txcounts[chain].values() if v["growthepie_txcount"])
        l2b_vals = [int(v["l2beat_txcount"]) for v in txcounts[chain].values() if v["l2beat_txcount"]]
        l2b = sum(l2b_vals) if len(l2b_vals) == len(txcounts[chain]) else None

        summary_rows.append({
            "chain": chain, "window_start_utc": WINDOW_START, "window_end_utc_exclusive": WINDOW_END,
            "chain_txs_growthepie": gtp, "chain_txs_l2beat": l2b if l2b is not None else "",
            "userops": total, "userops_success": success, "userops_with_paymaster": with_pm,
            "pct_userops_with_paymaster": pct(with_pm, total),
            "bundle_txs": bundles, "bundle_txs_with_paymaster_op": bundles_pm,
            "pct_chain_txs_that_are_bundles": pct(bundles, gtp),
            "pct_chain_txs_that_are_bundles_with_paymaster_op": pct(bundles_pm, gtp),
            "userops_per_100_chain_txs": pct(total, gtp),
            "paymaster_ops_erc20_mode": erc20, "paymaster_ops_stablecoin": stable,
            "paymaster_ops_not_erc20_mode": with_pm - erc20,
            "pct_paymaster_ops_erc20_mode": pct(erc20, with_pm),
            "pct_paymaster_ops_stablecoin": pct(stable, with_pm),
            "distinct_senders": work["distinct_senders_window"],
            "distinct_paymasters": len(pm_ops),
        })

        ranked = sorted(pm_ops.items(), key=lambda kv: -kv[1])
        for rank, (pm, n) in enumerate(ranked, 1):
            if rank > TOP_PAYMASTERS_PER_CHAIN:
                break
            lab = label_for(pm)  # empty when the same address is a different contract on this chain
            paymaster_rows.append({
                "chain": chain, "rank": rank, "paymaster": pm, "entrypoints": " ".join(sorted(pm_eps[pm])),
                "provider": lab.get("provider", "unlabeled"), "contract_name": lab.get("contract_name", ""),
                "type": lab.get("type", "unknown"), "label_source": lab.get("source_url", ""),
                "ops": n, "pct_of_chain_paymaster_ops": pct(n, with_pm),
                "mode_events": mode_events_by_pm.get(pm, 0), "erc20_mode_ops": erc20_by_pm.get(pm, 0),
            })
        rest = ranked[TOP_PAYMASTERS_PER_CHAIN:]
        if rest:
            n = sum(v for _, v in rest)
            paymaster_rows.append({
                "chain": chain, "rank": "", "paymaster": f"{len(rest)} other paymasters", "entrypoints": "",
                "provider": "", "contract_name": "", "type": "", "label_source": "", "ops": n,
                "pct_of_chain_paymaster_ops": pct(n, with_pm),
                "mode_events": sum(mode_events_by_pm.get(p, 0) for p, _ in rest),
                "erc20_mode_ops": sum(erc20_by_pm.get(p, 0) for p, _ in rest),
            })

        for t, n in sorted(token_ops.items(), key=lambda kv: -kv[1]):
            s = stables.get((chain, t))
            token_rows.append({
                "chain": chain, "token": t, "onchain_symbol": symbols.get((chain, t), ""),
                "stablecoin": int(bool(s)), "issuer": s["issuer"] if s else "", "issuer_source": s["source_url"] if s else "",
                "erc20_mode_ops": n, "pct_of_chain_erc20_mode_ops": pct(n, erc20),
            })

        bundles_by_day = {r["day"]: r for r in bundle_rows}
        for day in sorted(txcounts[chain]):
            b = bundles_by_day.get(day, {})
            daily_rows.append({
                "chain": chain, "day": day, "chain_txs_growthepie": txcounts[chain][day]["growthepie_txcount"],
                "userops": day_ops.get(day, 0), "userops_with_paymaster": day_pm_ops.get(day, 0),
                "bundle_txs": b.get("bundle_txs", 0), "bundle_txs_with_paymaster_op": b.get("bundle_txs_with_paymaster_op", 0),
                "paymaster_ops_erc20_mode": day_erc20.get(day, 0), "paymaster_ops_stablecoin": day_stable.get(day, 0),
            })

    tot = defaultdict(int)
    for r in summary_rows:
        for k in ("chain_txs_growthepie", "userops", "userops_with_paymaster", "bundle_txs",
                  "bundle_txs_with_paymaster_op", "paymaster_ops_erc20_mode", "paymaster_ops_stablecoin"):
            tot[k] += r[k]
    combined = {
        "window_start_utc": WINDOW_START, "window_end_utc_exclusive": WINDOW_END, "chains": list(CHAINS),
        **tot,
        "pct_userops_with_paymaster": pct(tot["userops_with_paymaster"], tot["userops"]),
        "pct_chain_txs_that_are_bundles": pct(tot["bundle_txs"], tot["chain_txs_growthepie"]),
        "pct_chain_txs_that_are_bundles_with_paymaster_op": pct(tot["bundle_txs_with_paymaster_op"], tot["chain_txs_growthepie"]),
        "pct_paymaster_ops_erc20_mode": pct(tot["paymaster_ops_erc20_mode"], tot["userops_with_paymaster"]),
        "pct_paymaster_ops_stablecoin": pct(tot["paymaster_ops_stablecoin"], tot["userops_with_paymaster"]),
        "pct_erc20_mode_ops_in_stablecoins": pct(tot["paymaster_ops_stablecoin"], tot["paymaster_ops_erc20_mode"]),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("summary-by-chain", summary_rows), ("paymasters", paymaster_rows),
                       ("daily", daily_rows), ("erc20-tokens", token_rows)):
        with open(OUT / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps({"combined": combined, "by_chain": summary_rows}, indent=2) + "\n")
    print(json.dumps(combined, indent=2))


if __name__ == "__main__":
    main()
