"""Read symbol() and decimals() for every token that paymasters charged in the window,
and token() for single-token paymasters whose event has no token field.

Uses free public RPC endpoints (publicnode.com, no key). Writes data/raw/charged-tokens.csv and
data/raw/paymaster-token-getter.csv.
Stablecoin status does not come from here: it comes from data/stablecoins.csv, which lists
each address with the issuer page that names it.
"""

import csv
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common import CHAINS, RAW, USER_AGENT

RPC = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "base": "https://base-rpc.publicnode.com",
    "arbitrum": "https://arbitrum-one-rpc.publicnode.com",
    "optimism": "https://optimism-rpc.publicnode.com",
    "polygon": "https://polygon-bor-rpc.publicnode.com",
}
SYMBOL, DECIMALS, TOKEN = "0x95d89b41", "0x313ce567", "0xfc0c546a"


def eth_call(chain, to, data):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]})
    req = urllib.request.Request(RPC[chain], data=body.encode(),
                                 headers={"content-type": "application/json", "user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("result") or "0x"


def decode_string(hexdata):
    b = bytes.fromhex(hexdata[2:])
    if len(b) == 32:  # some old tokens return bytes32
        return b.rstrip(b"\0").decode(errors="replace")
    if len(b) < 64:
        return ""
    n = int.from_bytes(b[32:64], "big")
    return b[64:64 + n].decode(errors="replace")


def main():
    tokens, getters = set(), set()
    for chain in CHAINS:
        path = RAW / f"paymaster-mode-events-daily-{chain}.csv"
        if not path.exists():
            continue
        for r in csv.DictReader(open(path)):
            if r["erc20_mode"] == "1" and r["token"].startswith("0x"):
                tokens.add((chain, r["token"]))
            elif r["erc20_mode"] == "1" and r["token"] == "token()":
                getters.add((chain, r["emitter"]))

    # Single-token paymasters: their event has no token field, so read the contract's token().
    getter_rows = []
    for chain, pm in sorted(getters):
        res = eth_call(chain, pm, TOKEN)
        token = "0x" + res[-40:] if len(res) >= 42 else ""
        getter_rows.append([chain, pm, token])
        if token:
            tokens.add((chain, token))
        print("token()", chain, pm, token, flush=True)
    with open(RAW / "paymaster-token-getter.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chain", "paymaster", "token"])
        w.writerows(getter_rows)
    out = RAW / "charged-tokens.csv"
    cache = {}
    if out.exists():  # token metadata does not change; reuse earlier lookups that succeeded
        for r in csv.DictReader(open(out)):
            if not r["onchain_symbol"].startswith("error"):
                cache[(r["chain"], r["token"])] = [r["chain"], r["token"], r["onchain_symbol"], r["decimals"]]

    def lookup(key):
        if key in cache:
            return cache[key]
        chain, token = key
        try:
            sym = decode_string(eth_call(chain, token, SYMBOL))
            dec = eth_call(chain, token, DECIMALS)
            dec = int(dec, 16) if dec not in ("0x", "") else ""
        except Exception as e:  # keep going; record the failure
            sym, dec = f"error: {e.__class__.__name__}", ""
        return [chain, token, sym, dec]

    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(lookup, sorted(tokens)))
    print(f"{len(rows)} tokens, {len(cache)} from cache, "
          f"{sum(r[2].startswith('error') for r in rows)} lookups failed", flush=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chain", "token", "onchain_symbol", "decimals"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
