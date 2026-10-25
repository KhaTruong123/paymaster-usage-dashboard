"""Count the per-userop events that paymaster contracts emit to say how gas was paid.

Usage: python3 scripts/extract_paymaster_mode_events.py <chain> [workers]

Which events paymasters emit was found with scripts/sample_fee_transfers.py. The exact Solidity
signatures and field meanings come from verified sources (data/paymaster-labels-notes.md).
Each rule says where the token sits and when the event means "user paid in an ERC-20 token".
An event only counts later (summarize.py) when its emitter is a paymaster seen in UserOperationEvent.

Writes data/raw/paymaster-mode-events-daily-<chain>.csv:
  day, emitter, event, erc20_mode, token, events
and docs/evidence/portal-responses-mode-events-<chain>.csv (response hashes).
"""

import csv
import hashlib
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from common import CHAINS, EVIDENCE, RAW, load_window_blocks, stream_range, topic_to_address, utc_day
from keccak import topic

ZERO = "0x" + "0" * 40


def word(data: str, i: int) -> str:
    return data[2 + 64 * i: 2 + 64 * (i + 1)]


def addr_word(data: str, i: int) -> str:
    return "0x" + word(data, i)[-40:]


TOKEN_GETTER = "token()"  # event has no token field; the token is the paymaster's token() (see resolve_tokens.py)

# Signature -> function(log) -> (erc20_mode, token). Signatures and field meanings are copied from
# the verified sources listed in data/paymaster-labels-notes.md. The topic0 is derived
# from the signature text, so a typo cannot silently match a different event.
SIGNATURES = {
    # Pimlico SingletonPaymaster V6/V7/V8: (bytes32 indexed userOpHash, address indexed user,
    # uint8 paymasterMode, address token, uint256 tokenAmountPaid, uint256 exchangeRate). Mode 1 = ERC-20.
    "UserOperationSponsored(bytes32,address,uint8,address,uint256,uint256)":
        lambda l: (int(word(l["data"], 0), 16) == 1, addr_word(l["data"], 1)),
    # Coinbase CDP VerifyingPaymaster, ERC-20 transfer succeeded: (bytes32 indexed userOperationHash,
    # uint128 indexed sponsorUUID, address indexed token, address receiver, uint256 amount).
    "UserOperationSponsoredWithERC20(bytes32,uint128,address,address,uint256)":
        lambda l: (True, topic_to_address(l["topics"][3])),
    # Coinbase CDP VerifyingPaymaster, sponsored (or token pull failed and the sponsor paid).
    "UserOperationSponsored(bytes32,uint128,address)":
        lambda l: (False, ZERO),
    # Alchemy Gas Manager: (bytes32 indexed userOpHash, address tokenAddress, uint256 tokenAmount).
    # Emitted only in ERC-20 mode.
    "TokenSponsored(bytes32,address,uint256)":
        lambda l: (True, addr_word(l["data"], 0)),
    # Circle Paymaster V07/V08: (IERC20 indexed token, address indexed sender, bytes32 userOpHash,
    # uint256 nativeTokenPrice, uint256 actualTokenNeeded, uint256 feeTokenAmount).
    "UserOperationSponsored(address,address,bytes32,uint256,uint256,uint256)":
        lambda l: (True, topic_to_address(l["topics"][1])),
    # Candide Paymaster: (bytes32 indexed userOpHash, address indexed sender, address indexed token,
    # uint256 cost). cost == 0 means sponsored.
    "UserOperationSponsored(bytes32,address,address,uint256)":
        lambda l: (int(word(l["data"], 0), 16) != 0, topic_to_address(l["topics"][3])),
    # Biconomy v0.6 BiconomyTokenPaymaster and Etherspot MultiTokenPaymaster (same shape):
    # (address indexed sender, address indexed token, uint256 indexed totalCharge, ...).
    "TokenPaymasterOperation(address,address,uint256,address,uint32,bytes32,uint256,uint8)":
        lambda l: (True, topic_to_address(l["topics"][2])),
    # Biconomy v0.7 BiconomyTokenPaymaster: (address indexed userOpSender, address indexed token, ...).
    "PaidGasInTokens(address,address,uint256,uint256,uint32,uint256,bytes32)":
        lambda l: (True, topic_to_address(l["topics"][2])),
    # Openfort OpenfortPaymasterV2: (address erc20Token, uint256 actualGasCost, uint256 actualTokensSent).
    "GasPaidInERC20(address,uint256,uint256)":
        lambda l: (True, addr_word(l["data"], 0)),
    # BIC token on Arbitrum is its own paymaster: ChargeFee(bytes32 indexed userOpHash, address sender,
    # uint256 fee), fee charged in BIC, so the token is the emitting contract.
    "ChargeFee(bytes32,address,uint256)": lambda l: (True, l["address"]),
    # Single-token paymasters whose event has no token field: Pimlico PimlicoERC20Paymaster (3 fields),
    # eth-infinitism TokenPaymaster derivatives such as thirdweb (4 fields) and Send (5 fields).
    "UserOperationSponsored(address,uint256,uint256)": lambda l: (True, TOKEN_GETTER),
    "UserOperationSponsored(address,uint256,uint256,uint256)": lambda l: (True, TOKEN_GETTER),
    "UserOperationSponsored(address,uint256,uint256,uint256,uint256)": lambda l: (True, TOKEN_GETTER),
}
RULES = {topic(sig): (sig, fn) for sig, fn in SIGNATURES.items()}

QUERY = {
    "fields": {"block": {"number": True, "timestamp": True}, "log": {"address": True, "topics": True, "data": True}},
    "logs": [{"topic0": list(RULES)}],
}


def run_slice(dataset, lo, hi, agg, responses, lock):
    local = defaultdict(int)

    def on_chunk(query, raw):
        with lock:
            responses.append([query["fromBlock"], query["toBlock"], len(raw), hashlib.sha256(raw).hexdigest()])

    for block in stream_range(dataset, lo, hi, QUERY, on_chunk):
        day = utc_day(block["header"]["timestamp"])
        for l in block.get("logs", []):
            name, decode = RULES[l["topics"][0]]
            try:
                erc20, token = decode(l)
            except (IndexError, ValueError):
                erc20, token = None, "undecodable"
            local[(day, l["address"], name, erc20, token)] += 1
    with lock:
        for k, v in local.items():
            agg[k] += v


def main():
    chain = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    dataset = CHAINS[chain][0]
    win = load_window_blocks()["chains"][chain]
    lo, hi = win["from_block"], win["to_block"]
    step = (hi - lo + 1) // (4 * workers) + 1
    bounds = [(a, min(hi, a + step - 1)) for a in range(lo, hi + 1, step)]
    agg, responses, lock = defaultdict(int), [], threading.Lock()
    with ThreadPoolExecutor(workers) as pool:
        for f in [pool.submit(run_slice, dataset, a, b, agg, responses, lock) for a, b in bounds]:
            f.result()
    with open(RAW / f"paymaster-mode-events-daily-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "emitter", "event", "erc20_mode", "token", "events"])
        for (day, em, name, erc20, token), n in sorted(agg.items(), key=lambda kv: [str(x) for x in kv[0]]):
            w.writerow([day, em, name, "" if erc20 is None else int(erc20), token, n])
    with open(EVIDENCE / f"portal-responses-mode-events-{chain}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_block", "requested_to_block", "bytes", "sha256"])
        w.writerows(sorted(responses))
    print(f"{chain}: {sum(agg.values())} mode events in {len(agg)} groups")


if __name__ == "__main__":
    main()
