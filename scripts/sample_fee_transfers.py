"""Discover how each paymaster is paid, from a sample of full bundle transactions.

Usage: python3 scripts/sample_fee_transfers.py <chain> <first_block> <block_count>

For every userop with a paymaster in the sample, look at ERC-20 Transfer logs in the same
transaction whose `from` is the userop sender. Tally (paymaster, token, recipient). A paymaster
that charges in ERC-20 shows up as many distinct senders sending one token to the paymaster
itself or to one fee collector. Writes data/raw/fee-transfer-sample-<chain>.csv and a
response hash log to docs/evidence/.
"""

import csv
import hashlib
import json
import sys
from collections import defaultdict

from common import (CHAINS, ENTRYPOINTS, ERC20_TRANSFER, EVIDENCE, RAW, USER_OPERATION_EVENT, ZERO_TOPIC,
                    stream_range, topic_to_address)

QUERY = {
    "fields": {
        "block": {"number": True, "timestamp": True},
        "log": {"address": True, "topics": True, "data": True, "transactionIndex": True, "logIndex": True},
    },
    "logs": [{"address": list(ENTRYPOINTS), "topic0": [USER_OPERATION_EVENT], "transactionLogs": True}],
}


def main():
    chain, first, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    dataset = CHAINS[chain][0]
    responses = []

    def on_chunk(query, raw):
        responses.append([query["fromBlock"], query["toBlock"], len(raw), hashlib.sha256(raw).hexdigest()])

    ops_by_pm = defaultdict(int)
    senders_by_pm = defaultdict(set)
    tally = defaultdict(lambda: [0, set()])  # (pm, token, to) -> [transfers, senders]
    emitted = defaultdict(int)  # (pm, topic0) -> logs emitted by the paymaster contract itself
    for block in stream_range(dataset, first, first + count - 1, QUERY, on_chunk):
        by_tx = defaultdict(list)
        for lg in block.get("logs", []):
            by_tx[lg["transactionIndex"]].append(lg)
        for logs in by_tx.values():
            pms_in_tx = {topic_to_address(l["topics"][3]) for l in logs if l["address"] in ENTRYPOINTS
                         and l["topics"] and l["topics"][0] == USER_OPERATION_EVENT}
            for l in logs:
                if l["address"] in pms_in_tx and l["topics"]:
                    emitted[(l["address"], l["topics"][0])] += 1
            transfers = [l for l in logs if l["topics"] and l["topics"][0] == ERC20_TRANSFER and len(l["topics"]) == 3]
            for op in logs:
                t = op["topics"]
                if op["address"] not in ENTRYPOINTS or not t or t[0] != USER_OPERATION_EVENT or t[3] == ZERO_TOPIC:
                    continue
                pm, sender = topic_to_address(t[3]), topic_to_address(t[2])
                ops_by_pm[pm] += 1
                senders_by_pm[pm].add(sender)
                for tr in transfers:
                    if topic_to_address(tr["topics"][1]) == sender:
                        k = (pm, tr["address"], topic_to_address(tr["topics"][2]))
                        tally[k][0] += 1
                        tally[k][1].add(sender)

    with open(RAW / f"fee-transfer-sample-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_from_block", "sample_to_block", "paymaster", "paymaster_ops_in_sample",
                    "paymaster_distinct_senders", "token", "recipient", "recipient_is_paymaster",
                    "transfers_from_sender", "distinct_senders"])
        for (pm, token, to), (n, senders) in sorted(tally.items(), key=lambda kv: -kv[1][0]):
            if len(senders) < 3:
                continue  # one-off user payments, not a fee pattern
            w.writerow([first, first + count - 1, pm, ops_by_pm[pm], len(senders_by_pm[pm]), token, to,
                        int(to == pm), n, len(senders)])
    with open(RAW / f"paymaster-emitted-events-sample-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_from_block", "sample_to_block", "paymaster", "paymaster_ops_in_sample", "topic0", "logs"])
        for (pm, t0), n in sorted(emitted.items(), key=lambda kv: (-ops_by_pm[kv[0][0]], -kv[1])):
            w.writerow([first, first + count - 1, pm, ops_by_pm[pm], t0, n])
    with open(EVIDENCE / f"portal-responses-fee-sample-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_block", "requested_to_block", "bytes", "sha256"])
        w.writerows(responses)
    print(json.dumps({"chain": chain, "blocks": [first, first + count - 1], "paymasters": len(ops_by_pm),
                      "paymaster_ops": sum(ops_by_pm.values())}))


if __name__ == "__main__":
    main()
