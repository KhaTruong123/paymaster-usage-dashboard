"""Shared config and helpers for the paymaster usage pipeline.

Data source: SQD Network public portal (https://portal.sqd.dev), no API key.
Docs: https://docs.sqd.dev/en/portal/evm/overview
"""

import gzip
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
WORK = ROOT / "data" / "work"  # large local files, git-ignored, hashed in evidence
EVIDENCE = ROOT / "docs" / "evidence"
OUT = ROOT / "docs" / "data"

PORTAL = "https://portal.sqd.dev/datasets"
USER_AGENT = "paymaster-usage-dashboard/0.1 (+https://github.com/KhaTruong123/paymaster-usage-dashboard)"

# Fixed window: 30 full UTC days. End is exclusive.
WINDOW_START = "2026-09-24"
WINDOW_END = "2026-10-24"

# chain key -> (SQD dataset, growthepie origin_key, l2beat project slug or None, native symbol)
CHAINS = {
    "ethereum": ("ethereum-mainnet", "ethereum", None, "ETH"),
    "base": ("base-mainnet", "base", "base", "ETH"),
    "arbitrum": ("arbitrum-one", "arbitrum", "arbitrum", "ETH"),
    "optimism": ("optimism-mainnet", "optimism", "op-mainnet", "ETH"),
    "polygon": ("polygon-mainnet", "polygon_pos", None, "POL"),
}

# Canonical ERC-4337 EntryPoint deployments (same address on every chain).
# Source: https://github.com/eth-infinitism/account-abstraction/releases
ENTRYPOINTS = {
    "0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789": "v0.6",
    "0x0000000071727de22e5e9d8baf0edac6f37da032": "v0.7",
    "0x4337084d9e255ff0702461cf8895ce9e3b5ff108": "v0.8",
    "0x433709009b8330fda32311df1c2afa402ed8d009": "v0.9",
}

# keccak256("UserOperationEvent(bytes32,address,address,uint256,bool,uint256,uint256)")
# Topics: [sig, userOpHash, sender, paymaster]. Data: nonce, success, actualGasCost, actualGasUsed.
USER_OPERATION_EVENT = "0x49628fd1471006c1482da88028e9ce4dbb080b815c9b0344d39e5a8e6ec1419f"
# keccak256("Transfer(address,address,uint256)")
ERC20_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

ZERO_TOPIC = "0x" + "0" * 64


def ts(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def utc_day(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=timezone.utc).strftime("%Y-%m-%d")


def topic_to_address(topic: str) -> str:
    return "0x" + topic[-40:]


def address_to_topic(address: str) -> str:
    return "0x" + "0" * 24 + address.lower()[2:]


def post_stream(dataset: str, query: dict, retries: int = 20) -> bytes:
    """POST one query to the portal stream endpoint, return decompressed NDJSON bytes."""
    body = json.dumps(query).encode()
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{PORTAL}/{dataset}/stream",
            data=body,
            headers={"content-type": "application/json", "accept-encoding": "gzip", "user-agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                raw = resp.read()
                if resp.headers.get("content-encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return b""
            why = f"HTTP {e.code}"
            wait = int(e.headers.get("retry-after") or 0) or 2 ** attempt
            if e.code not in (429, 500, 502, 503, 504, 529):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, gzip.BadGzipFile) as e:
            wait = 2 ** attempt
            why = e.__class__.__name__
        print(f"retry {attempt + 1}/{retries} {dataset} from {query.get('fromBlock')} after {why}",
              file=sys.stderr, flush=True)
        time.sleep(min(wait, 60) + random.random() * 3)
    raise RuntimeError(f"portal request failed after {retries} tries: {dataset}")


def stream_range(dataset: str, from_block: int, to_block: int, query_body: dict, on_chunk=None):
    """Yield block dicts for [from_block, to_block], following the portal's partial responses.

    The portal may stop early; the last returned header is the cursor. It always returns
    the first and last block of what it served, even when nothing matched.
    """
    cursor = from_block
    while cursor <= to_block:
        query = dict(query_body, type="evm", fromBlock=cursor, toBlock=to_block)
        raw = post_stream(dataset, query)
        if on_chunk:
            on_chunk(query, raw)
        last = None
        for line in raw.splitlines():
            if not line:
                continue
            block = json.loads(line)
            last = block["header"]["number"]
            yield block
        if last is None:
            raise RuntimeError(f"empty portal response {dataset} {cursor}-{to_block}")
        cursor = last + 1


def block_timestamp(dataset: str, number: int) -> int:
    q = {"type": "evm", "fromBlock": number, "toBlock": number, "includeAllBlocks": True,
         "fields": {"block": {"number": True, "timestamp": True}}}
    raw = post_stream(dataset, q)
    return json.loads(raw.splitlines()[0])["header"]["timestamp"]


def head(dataset: str) -> int:
    req = urllib.request.Request(f"{PORTAL}/{dataset}/finalized-head", headers={"user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["number"]


def first_block_at_or_after(dataset: str, unix: int, lo: int, hi: int) -> int:
    """Interpolation search for the first block with timestamp >= unix in [lo, hi]."""
    t_lo, t_hi = block_timestamp(dataset, lo), block_timestamp(dataset, hi)
    if t_lo >= unix:
        return lo
    while hi - lo > 1:
        # invariant: ts(lo) < unix <= ts(hi)
        guess = lo + int((unix - t_lo) * (hi - lo) / max(t_hi - t_lo, 1))
        mid = min(max(guess, lo + 1), hi - 1)
        if hi - lo > 64:  # keep shrinking even when block times are uneven
            mid = min(max(mid, lo + (hi - lo) // 16), hi - (hi - lo) // 16)
        else:
            mid = (lo + hi) // 2
        t_mid = block_timestamp(dataset, mid)
        if t_mid < unix:
            lo, t_lo = mid, t_mid
        else:
            hi, t_hi = mid, t_mid
    return hi


def load_window_blocks() -> dict:
    return json.loads((EVIDENCE / "window-blocks.json").read_text())
