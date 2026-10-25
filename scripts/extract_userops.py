"""Stream every UserOperationEvent from the canonical EntryPoints in the window.

Usage: python3 scripts/extract_userops.py <chain> [workers] [slices]

Resumable: finished slices are kept in data/work/ and skipped on the next run.

Writes one row per userop to data/work/<chain>-userops.csv.gz (large, git-ignored) and
one row per portal response to docs/evidence/portal-responses-userops-<chain>.csv
(requested range, last block served, sha256 of the response body, log count).
"""

import csv
import gzip
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import (CHAINS, ENTRYPOINTS, EVIDENCE, ROOT, USER_OPERATION_EVENT, WORK, load_window_blocks,
                    stream_range, topic_to_address, utc_day)

QUERY = {
    "fields": {
        "block": {"number": True, "timestamp": True},
        "log": {"address": True, "topics": True, "data": True, "transactionIndex": True, "logIndex": True},
    },
    "logs": [{"address": list(ENTRYPOINTS), "topic0": [USER_OPERATION_EVENT]}],
}

COLUMNS = ["block", "tx_index", "log_index", "day", "entrypoint", "sender", "paymaster",
           "success", "actual_gas_cost_wei", "actual_gas_used"]


def extract_slice(dataset, lo, hi, part_path):
    """Extract one block slice. The part file only gets its final name once the slice is complete,
    so an interrupted run can resume by skipping finished slices."""
    evidence_path = part_path.with_suffix(".responses.json")
    if part_path.exists() and evidence_path.exists():
        return json.loads(evidence_path.read_text())["ops"]
    evidence_rows = []

    def on_chunk(query, raw):
        lines = [l for l in raw.splitlines() if l]
        last = json.loads(lines[-1])["header"]["number"] if lines else ""
        evidence_rows.append([query["fromBlock"], query["toBlock"], last,
                              len(raw), hashlib.sha256(raw).hexdigest(), raw.count(b'"logIndex"')])

    n = 0
    tmp = part_path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", newline="") as f:
        w = csv.writer(f)
        for block in stream_range(dataset, lo, hi, QUERY, on_chunk):
            day = utc_day(block["header"]["timestamp"])
            for lg in block.get("logs", []):
                t, d = lg["topics"], lg["data"][2:]
                w.writerow([block["header"]["number"], lg["transactionIndex"], lg["logIndex"], day,
                            ENTRYPOINTS[lg["address"]], topic_to_address(t[2]), topic_to_address(t[3]),
                            int(d[64:128], 16), int(d[128:192], 16), int(d[192:256], 16)])
                n += 1
    evidence_path.write_text(json.dumps({"from_block": lo, "to_block": hi, "ops": n, "responses": evidence_rows}))
    tmp.rename(part_path)
    return n


def main():
    chain = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    dataset = CHAINS[chain][0]
    win = load_window_blocks()["chains"][chain]
    lo, hi = win["from_block"], win["to_block"]
    WORK.mkdir(parents=True, exist_ok=True)

    slices = int(sys.argv[3]) if len(sys.argv) > 3 else 4 * workers
    step = (hi - lo + 1) // slices + 1
    bounds = [(lo + i * step, min(hi, lo + (i + 1) * step - 1)) for i in range(slices) if lo + i * step <= hi]
    t0 = time.time()
    print(f"{chain}: blocks {lo}-{hi}, {len(bounds)} slices, {workers} workers", flush=True)

    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(extract_slice, dataset, a, b, WORK / f"{chain}-userops.part{i:03d}.csv.gz")
                   for i, (a, b) in enumerate(bounds)]
        total = 0
        for i, fut in enumerate(futures):
            total += fut.result()
            print(f"{chain}: slice {i + 1}/{len(bounds)} done, {total} ops so far, {time.time() - t0:.0f}s", flush=True)

    out = WORK / f"{chain}-userops.csv.gz"
    with gzip.open(out, "wt", newline="") as f:
        csv.writer(f).writerow(COLUMNS)
    evidence_rows = []
    with open(out, "ab") as dst:
        for i in range(len(bounds)):
            part = WORK / f"{chain}-userops.part{i:03d}.csv.gz"
            dst.write(part.read_bytes())  # concatenated gzip members are a valid gzip stream
            ev = part.with_suffix(".responses.json")
            evidence_rows += json.loads(ev.read_text())["responses"]
            part.unlink()
            ev.unlink()

    evidence_rows.sort()
    with open(EVIDENCE / f"portal-responses-userops-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_block", "requested_to_block", "last_block_served", "bytes", "sha256", "log_count"])
        w.writerows(evidence_rows)
    print(f"{chain}: DONE {total} userops in {time.time() - t0:.0f}s -> {out.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
