"""Find the first and last block of the fixed UTC window on each chain.

Writes docs/evidence/window-blocks.json. Block timestamps come from the SQD portal.
"""

import json

from common import CHAINS, EVIDENCE, WINDOW_END, WINDOW_START, block_timestamp, first_block_at_or_after, head, ts


def main():
    start, end = ts(WINDOW_START), ts(WINDOW_END)
    path = EVIDENCE / "window-blocks.json"
    out = {"window_start_utc": WINDOW_START, "window_end_utc_exclusive": WINDOW_END, "chains": {}}
    if path.exists():  # resume: keep chains already found for this same window
        prev = json.loads(path.read_text())
        if prev["window_start_utc"] == WINDOW_START and prev["window_end_utc_exclusive"] == WINDOW_END:
            out = prev
    for chain, (dataset, *_rest) in CHAINS.items():
        if chain in out["chains"]:
            continue
        hi = head(dataset)
        first = first_block_at_or_after(dataset, start, hi // 2, hi)
        after = first_block_at_or_after(dataset, end, first, hi)
        last = after - 1
        out["chains"][chain] = {
            "dataset": dataset,
            "from_block": first,
            "to_block": last,
            "from_block_timestamp": block_timestamp(dataset, first),
            "to_block_timestamp": block_timestamp(dataset, last),
            "previous_block_timestamp": block_timestamp(dataset, first - 1),
            "next_block_timestamp": block_timestamp(dataset, after),
        }
        print(chain, out["chains"][chain], flush=True)
        path.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
