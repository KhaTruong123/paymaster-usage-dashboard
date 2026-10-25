"""Aggregate the per-userop work file into small daily tables that are committed.

Usage: python3 scripts/aggregate_userops.py <chain>

Outputs:
  data/raw/userops-daily-paymaster-<chain>.csv  day, entrypoint, paymaster, ops, ops_success, actual_gas_cost_wei
  data/raw/bundles-daily-<chain>.csv            day, bundle_txs, bundle_txs_with_paymaster_op, distinct_senders
  docs/evidence/work-file-<chain>.json          sha256 + row count of the work file
"""

import csv
import gzip
import hashlib
import json
import sys
from collections import defaultdict

from common import EVIDENCE, RAW, WORK

ZERO = "0x" + "0" * 40


def main():
    chain = sys.argv[1]
    path = WORK / f"{chain}-userops.csv.gz"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()

    agg = defaultdict(lambda: [0, 0, 0])
    bundles = defaultdict(lambda: [0, 0, set()])
    window_senders = set()
    rows = 0
    prev_tx, prev_has_pm = None, False
    with gzip.open(path, "rt", newline="") as f:
        for r in csv.DictReader(f):
            rows += 1
            day, pm = r["day"], r["paymaster"]
            a = agg[(day, r["entrypoint"], pm)]
            a[0] += 1
            a[1] += int(r["success"])
            a[2] += int(r["actual_gas_cost_wei"])
            b = bundles[day]
            b[2].add(r["sender"])
            window_senders.add(r["sender"])
            # Rows of one transaction are adjacent: the extractor writes logs in block/log order.
            tx = (r["block"], r["tx_index"])
            if tx != prev_tx:
                b[0] += 1
                prev_tx, prev_has_pm = tx, False
            if pm != ZERO and not prev_has_pm:
                b[1] += 1
                prev_has_pm = True

    with open(RAW / f"userops-daily-paymaster-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "entrypoint", "paymaster", "ops", "ops_success", "actual_gas_cost_wei"])
        for (day, ep, pm), (n, ok, gas) in sorted(agg.items()):
            w.writerow([day, ep, pm, n, ok, gas])
    with open(RAW / f"bundles-daily-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "bundle_txs", "bundle_txs_with_paymaster_op", "distinct_senders"])
        for day, (n, n_pm, senders) in sorted(bundles.items()):
            w.writerow([day, n, n_pm, len(senders)])
    (EVIDENCE / f"work-file-{chain}.json").write_text(json.dumps({
        "file": f"data/work/{chain}-userops.csv.gz", "sha256": sha, "userop_rows": rows,
        "distinct_senders_window": len(window_senders),
        "note": "Not committed (size). Rebuild with scripts/extract_userops.py; per-response hashes in "
                f"docs/evidence/portal-responses-userops-{chain}.csv.",
    }, indent=2) + "\n")
    print(f"{chain}: {rows} userops, {len(agg)} day/entrypoint/paymaster groups, sha256 {sha}")


if __name__ == "__main__":
    main()
