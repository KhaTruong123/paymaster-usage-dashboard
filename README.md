# paymaster-usage-dashboard

How much ERC-4337 activity uses a paymaster on Ethereum, Base, Arbitrum, OP Mainnet and Polygon PoS, and how much of that gas is paid in stablecoins. Built only from public onchain data.

It answers a question asked in the AA Mafia group on 2025-09-11: is there a dashboard that shows how much paymasters are used across L1 and L2s, as a percentage of all transactions?

- Dashboard: `docs/index.html` (static, GitHub Pages ready, not enabled yet)
- Methodology, definitions and known gaps: `docs/methodology.html`
- Numbers as CSV: `docs/data/`

## Headline numbers

Window: 2026-09-24 to 2026-10-24 (30 full UTC days, end exclusive). Source: `UserOperationEvent` logs from EntryPoint v0.6, v0.7, v0.8 and v0.9 via the SQD public portal. Chain transaction totals come from growthepie.

__HEADLINES__

## How it works

1. `scripts/find_window_blocks.py` finds the first and last block of the window on each chain.
2. `scripts/extract_userops.py` streams every `UserOperationEvent` from the four canonical EntryPoints. `scripts/aggregate_userops.py` turns them into daily tables per paymaster.
3. `scripts/extract_paymaster_mode_events.py` counts the per-userop events that paymaster contracts emit, which say whether the user paid in an ERC-20 token and which one.
4. `scripts/fetch_chain_txcounts.py` pulls daily transaction counts per chain from growthepie, with L2BEAT as a cross-check.
5. `scripts/resolve_tokens.py` reads token symbols onchain. `data/stablecoins.csv` says which tokens are stablecoins, with the issuer page for each.
6. `scripts/summarize.py` joins everything into `docs/data/`. `scripts/build_dashboard.py` renders `docs/index.html`.

Paymaster labels are in `data/paymaster-labels.csv`, one public source per row. `data/paymaster-labels-notes.md` explains each source and every label that is weak or inferred.

Python 3 standard library only. No API keys.

## Evidence

- `docs/evidence/window-blocks.json`: window boundary blocks and timestamps.
- `docs/evidence/portal-responses-*.csv`: requested block range and SHA-256 of every portal response.
- `docs/evidence/work-file-*.json`: SHA-256 and row count of each per-userop file. These files are too large to commit (`data/work/` is git-ignored) and can be rebuilt with the scripts.
- `docs/evidence/run-*.log`: run logs, including the portal's rate-limit retries.

## Known gaps

The short list is below. The full list is in `docs/methodology.html`.

- The ERC-20 share is a lower bound. A paymaster that charges a token without emitting a recognized event counts as "no ERC-20 event".
- Sponsorship that sets no paymaster (Gelato Gas Tank, Alchemy bundler-sponsored userops) looks like a self-paid userop.
- Only canonical ERC-4337 EntryPoints are counted. Native account abstraction and EIP-7702 accounts sending normal transactions are out of scope.
- Only USDC, EURC, USDT and USDT0 count as stablecoins. DAI, USAT and bridged USDC show up in the token table with small counts and are not counted.

## License

MIT
