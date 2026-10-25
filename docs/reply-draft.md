# Draft reply to Rahul (AA Mafia, 2025-09-11 question)

Not posted. Kelvin reviews and posts. Numbers trace to `docs/data/summary-by-chain.csv` and `docs/data/summary.json`.

---

I took a shot at this with public data only: ERC-4337 EntryPoint v0.6 to v0.9 logs on Ethereum, Base, Arbitrum, OP and Polygon PoS for 30 days (Sep 24 to Oct 23, 2026). Repo with dashboard and scripts: https://github.com/KhaTruong123/paymaster-usage-dashboard
75% of userops (17.8M of 23.7M) had a paymaster pay the gas.
As a share of all transactions, 2.4% of all txs on these 5 chains were bundles with at least one paymaster-paid userop. By chain: Polygon 4.0%, Base 2.4%, Arbitrum 1.2%, Ethereum 1.0%, OP 0.2%.
Most of it looks sponsored. Only 4.4% of paymaster userops charged the user in a stablecoin, but that is 58% on Ethereum (USDT and USDC, mostly through Pimlico) and 42% on Arbitrum.
The ERC-20 split comes from each paymaster's own events, so it is a lower bound. Methodology and known gaps are in the repo, and corrections on the unlabeled paymasters are welcome.
