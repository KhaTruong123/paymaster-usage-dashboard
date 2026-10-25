# Paymaster labels: research notes

Companion to `paymaster-labels.csv` (99 rows: 79 from the first pass, 19 from the second pass, 1 from the addendum). Researched 2026-10-25.

## How the table was built

- Every row has a public source that names the address. First-party provider docs or repos were used where they exist. Where they don't, the source is a third-party label file and the note says so.
- The best open label file is BundleBear's dbt model, not a seed: https://github.com/Jam516/BundleBear/blob/16bfc764fd595e7064f423a61b523fc82be402f8/models/erc4337/labels/erc4337_labels_paymasters.sql (last changed 2025-06-12). Pimlico runs a second one: https://github.com/pimlicolabs/4337-stats/blob/91b029376b3f50699645094d2d3346611d34b87b/data/paymasters.csv (last changed 2025-07-07). Some BundleBear rows were added by provider staff: Circle rows by `ccai-circle`, Candide rows by `sednaoui`, thirdweb rows by `0xFirekeeper`.
- `chains` and `entrypoint_version` are checked on-chain, not copied. For each address I read `eth_getCode` on the 5 chains, called `entryPoint()`, called `token()`, and looked up the verified contract name on Sourcify (v2 API) and Etherscan (via Routescan, Ethereum only). `all` means code exists on Ethereum, Base, Arbitrum One, Optimism and Polygon PoS. A label is only safe on chains where the code matches. For example, 0x810f...4a40 is Etherspot on Base but an unrelated "Gateway" contract on Ethereum.
- EntryPoint addresses come from the eth-infinitism release notes: v0.6 `0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789`, v0.7 `0x0000000071727De22E5E9d8BAf0edAc6f37da032`, v0.8 `0x4337084d9e255ff0702461cf8895ce9e3b5ff108`, v0.9 `0x433709009B8330FDa32311DF1C2AFA402eD8D009`.

## Per-userop events that reveal mode or token

All text below is copied from the source file. Line numbers refer to the linked file. Sourcify links use `https://sourcify.dev/server/v2/contract/{chainId}/{address}?fields=sources`, and the source path is the key inside `sources`.

### Pimlico SingletonPaymaster V6 / V7 / V8 (0x6666..., 0x7777..., 0x8888..., 0x...39cd5, 0x...fb866)

Source: https://github.com/pimlicolabs/singleton-paymaster/blob/1e2305d1102242379b582142f62bd17add12b8c2/src/base/BaseSingletonPaymaster.sol#L118 (V8 inherits V7). The deployed older 0x...39cd5 and 0x...fb866 have the same declaration, confirmed in their Sourcify sources (`src/base/BaseSingletonPaymaster.sol`).

```solidity
    event UserOperationSponsored(
        bytes32 indexed userOpHash,
        /// @param The user that requested sponsorship.
        address indexed user,
        /// @param The paymaster mode that was used.
        uint8 paymasterMode,
        /// @param The token that was used during sponsorship (ERC-20 mode only).
        address token,
        /// @param The amount of token paid during sponsorship (ERC-20 mode only).
        uint256 tokenAmountPaid,
        /// @param The exchange rate of the token at time of sponsorship (ERC-20 mode only).
        uint256 exchangeRate
    );
```

Indexed: `userOpHash`, `user`. Mode constants are in the same file: `uint8 immutable VERIFYING_MODE = 0;` and `uint8 immutable ERC20_MODE = 1;`. Verifying mode emits `token = address(0)` and zeros (SingletonPaymasterV7.sol L175). ERC-20 mode emits the token and amount (L291).

### Pimlico PimlicoERC20Paymaster, deprecated, one contract per token (0x...fabfa8, 0x...fce661, 0x...58e13d, 0x...3011ee, 0x49ee...)

Source: Sourcify, chain 1, 0x0000000000fabfa8079ab313d1d14dcf4d15582a, file `lib/erc20-paymaster-contracts/src/PimlicoERC20Paymaster.sol` L38. Same text on chain 42161, 0x49ee41bc..., file `src/PimlicoERC20Paymaster.sol` L38.

```solidity
    event UserOperationSponsored(address indexed user, uint256 actualTokenNeeded, uint256 actualGasCost);
```

Indexed: `user`. The event has no token field. The token is the contract's immutable `token()`, so it is listed per row in the CSV.

There is a third Pimlico shape in the archived `pimlicolabs/erc20-paymaster` repo (ERC20PaymasterV06/V07, `src/base/BaseERC20Paymaster.sol` L59):

```solidity
    event UserOperationSponsored(
        bytes32 indexed userOpHash,
        address indexed user,
        address indexed guarantor,
        uint256 tokenAmountPaid,
        uint256 tokenPrice,
        bool paidByGuarantor
    );
```

I did not confirm any deployed address in the CSV that uses this version. All three Pimlico events are named `UserOperationSponsored` but have different topic0 values, so decode by full signature, not by name.

### Circle Paymaster TokenPaymasterV07 / V08 (0x6C97..., 0x0578...)

Source: verified implementations on Sourcify. V08: chain 8453, 0x46d166896d9465a809a44a8e4d41a98ed7979772. V07: chain 8453, 0xb25854909a849cf1335a0b1c13cb946634125fbb. File `src/paymaster/BaseTokenPaymaster.sol` L98, identical text in both.

```solidity
    event UserOperationSponsored(
        IERC20 indexed token,
        address indexed sender,
        bytes32 userOpHash,
        uint256 nativeTokenPrice,
        uint256 actualTokenNeeded,
        uint256 feeTokenAmount
    );
```

Indexed: `token`, `sender`. `userOpHash` is not indexed. Circle's docs page (https://developers.circle.com/paymaster/addresses-and-events) lists the same fields but doesn't say which are indexed. `IERC20` is `address` in the ABI.

### Coinbase VerifyingPaymaster (CDP) (0x2FAE..., 0xdCBE..., and the 0x8bf5... copy)

Source: https://github.com/coinbase/verifying-paymaster/blob/f42791eb05e911d52474e5fc16cfa70ccb7d3ca8/src/VerifyingPaymaster.sol#L84 and L93. Tag v1.0.0 (EntryPoint v0.6) has the same two declarations.

```solidity
    event UserOperationSponsored(bytes32 indexed userOperationHash, uint128 indexed sponsorUUID, address token);
```

```solidity
    event UserOperationSponsoredWithERC20(
        bytes32 indexed userOperationHash, uint128 indexed sponsorUUID, address indexed token, address receiver, uint256 amount
    );
```

Mode logic (`_postOp`): `UserOperationSponsoredWithERC20` means the ERC-20 transfer succeeded. `UserOperationSponsored` with `token = address(0)` means plain sponsorship. `UserOperationSponsored` with a nonzero `token` means the token transfer failed and the sponsor ate the cost.

### Alchemy Gas Manager VerifyingPaymaster (0x2cc0..., 0x4fd9...)

Source: verified implementations on Sourcify. v0.7: chain 8453, 0xa4f070629058767c0d5d70465082ec1b7d9ca5a4. v0.6: chain 137, 0x50b5171d2d950d474dd9ea581f78c1a326133793. File `src/VerifyingPaymaster.sol` L44.

```solidity
    event TokenSponsored(bytes32 indexed userOpHash, address tokenAddress, uint256 tokenAmount);
```

Indexed: `userOpHash`. The event is emitted only in ERC-20 mode. Sponsor mode returns early with no event. So Alchemy ERC-20 gas payment uses the same contract as sponsorship. The v0.6 implementation also has `event PostOpReverted();`.

### Candide Paymaster, all versions (0x3fe2..., 0x36f4..., 0x8b1f..., 0xa815..., 0xca94...)

Source: Sourcify, chain 1. `contracts/paymaster/CandidePaymaster06.sol` L66, `contracts/CandidePaymaster07.sol` L67, `project/contracts/CandidePaymasterCore.sol` L60 (v0.9), and `contracts/paymaster/CandidePaymaster.sol` L44 (old 0x3fe2...). The v0.8 source is from Etherscan, `contracts/CandidePaymaster08.sol` L67. The text is the same in every version.

```solidity
    event UserOperationSponsored(bytes32 indexed userOpHash, address indexed sender, address indexed token, uint256 cost);
```

```solidity
    event PostOpReverted(bytes32 indexed userOpHash, address indexed sender, address indexed token);
```

In v0.6/v0.7/v0.8/v0.9, sponsored mode emits `token = address(0), cost = 0`. In the old 0x3fe2... contract, sponsored (FREE / GAS_BACK) emits the real token address with `cost = 0`. Use `cost == 0` as the sponsor test.

### Biconomy

v0.6 BiconomyTokenPaymaster (0x00000f73...). Source: https://github.com/bcnmy/biconomy-paymasters/blob/0fdbe668c5c47dad4d1219c0e229f2bb27a2ba78/contracts/token/BiconomyTokenPaymaster.sol#L112. It matches the verified source on Sourcify chain 1.

```solidity
    event TokenPaymasterOperation(
        address indexed sender,
        address indexed token,
        uint256 indexed totalCharge,
        address oracleAggregator,
        uint32 priceMarkup,
        bytes32 userOpHash,
        uint256 exchangeRate,
        ExchangeRateSource priceSource
    );
```

`ExchangeRateSource` is an enum, so it is `uint8` in the ABI. The same contract also has `event TokenPaymentDue(address indexed token, address indexed account, uint256 indexed charge);` (L126), emitted when the token pull fails.

v0.7 BiconomyTokenPaymaster (0x00000000301515...). Source: Sourcify chain 1, file `contracts/interfaces/IBiconomyTokenPaymaster.sol` L26.

```solidity
    event PaidGasInTokens(
        address indexed userOpSender,
        address indexed token,
        uint256 gasCostBeforePostOpAndPenalty,
        uint256 tokenCharge,
        uint32 priceMarkup,
        uint256 tokenPrice,
        bytes32 userOpHash
    );
```

The sponsor-only Biconomy paymasters emit a per-op event that names the dapp's paymasterId. This is useful for attribution but not needed for mode.
- v0.6 VerifyingSingletonPaymaster, `contracts/verifying/VerifyingSingletonPaymaster.sol` L55: `event GasBalanceDeducted(address indexed _paymasterId, uint256 indexed _charge);` (written over multiple lines in the source).
- v0.7 BiconomySponsorshipPaymaster, Sourcify chain 1 0x00000072a5..., `contracts/interfaces/IBiconomySponsorshipPaymaster.sol` L20: `event GasBalanceDeducted(address indexed _paymasterId, uint256 indexed _charge, uint256 indexed _premium);`

### Etherspot

MultiTokenPaymaster v0.6 (0x33fa..., Sourcify chain 137, `contracts/oracle/MultiTokenPaymaster/MultiTokenPaymaster.sol` L104). The v0.7 contract (0x5e6c..., Etherscan source `src/MultiTokenPaymaster/MultiTokenPaymaster.sol` L92) has the same declaration. Etherspot's MTP uses Biconomy's v0.6 event shape exactly, so topic0 is identical. Tell them apart by contract address, not by event.

```solidity
    event TokenPaymasterOperation(
        address indexed sender,
        address indexed token,
        uint256 indexed totalCharge,
        address oracleAggregator,
        uint32 priceMarkup,
        bytes32 userOpHash,
        uint256 exchangeRate,
        ExchangeRateSource priceSource
    );
```

EtherspotPaymaster v0.6 (sponsor), Sourcify chain 137 0x26fe..., `src/paymaster/EtherspotPaymaster.sol` L31: `event SponsorSuccessful(address paymaster, address sender);`

### thirdweb and Send TokenPaymaster (both are eth-infinitism TokenPaymaster derivatives)

thirdweb 0x2222... (Sourcify chain 8453, `contracts/prebuilts/account/token-paymaster/TokenPaymaster.sol` L42):

```solidity
    event UserOperationSponsored(
        address indexed user,
        uint256 actualTokenCharge,
        uint256 actualGasCost,
        uint256 actualTokenPriceWithMarkup
    );
```

Send 0x592e... (Sourcify chain 8453, `src/TokenPaymaster.sol` L51):

```solidity
    event UserOperationSponsored(
        address indexed user,
        uint256 actualTokenCharge,
        uint256 actualGasCost,
        uint256 actualTokenPriceWithMarkup,
        uint256 baseFee
    );
```

Both are single-token (USDC on Base). The event has no token field.

### Openfort OpenfortPaymasterV2 (0x5103...)

Source: Sourcify chain 1, `contracts/paymaster/OpenfortPaymasterV2.sol` L48 and L57.

```solidity
    event GasPaidInERC20(address erc20Token, uint256 actualGasCost, uint256 actualTokensSent);
```

```solidity
    event GasBalanceDeducted(address depositor, uint256 actualOpCost);
```

`GasPaidInERC20` appears only in ERC-20 modes. In FixedRate mode the third argument is the fixed token amount (L170). `GasBalanceDeducted` fires in every mode when the depositor is not the owner, so it does not mark sponsorship by itself.

### Others with a per-op event

- thirdweb ShieldedVerifyingPaymasterV7 (0x5fa6..., Etherscan source `src/paymaster/ShieldedVerifyingPaymasterV7.sol` L20): `event TransactionSponsored(bytes32 identifier, bytes extraData);`
- Coinbase MagicSpend (0x011a..., Etherscan source `src/MagicSpend.sol` L51): `event MagicSpendWithdrawal(address indexed account, address indexed asset, uint256 amount, uint256 nonce);`

### No per-op event (mode must come from paymasterAndData or token transfers)

These have no per-op event: Stackup VerifyingPaymaster (0xe93e..., 0x9d6a...), UXLink UXPaymaster, AmbirePaymaster, and the eth-infinitism sample VerifyingPaymaster (0x504e...). For Stackup the ERC-20 address sits in the signed paymasterAndData. A fallback that works for any ERC-20 paymaster is to look for an ERC-20 `Transfer` from `sender` to the paymaster (or its receiver) in the same userop's logs.

## Gas sponsorship that never shows up as a paymaster

The dashboard will undercount sponsorship if it only counts `paymaster != 0x0`.
- Gelato: its docs say Gelato has no on-chain paymaster. Gas Tank / 1Balance sponsorship sets the fee fields to 0 and leaves the paymaster fields empty (https://docs.gelato.cloud/paymaster-&-bundler).
- Alchemy also runs "bundler sponsored operations" with no on-chain paymaster (https://www.alchemy.com/docs/reference/bundler-sponsored-operations, beta).
- ZeroDev does not run its own paymaster contract. Its meta-infrastructure proxies to Pimlico, Alchemy and others (`zerodevapp/docs` `docs/pages/api-and-toolings/infrastructure/intro.mdx`), so ZeroDev traffic shows up under those providers' addresses. UltraRelay merges relayer and sponsor and bypasses the 4337 paymaster path.
- Safe runs no paymaster. BundleBear's commented-out `safe` line points at a Pimlico address.
- CDP Paymaster supports Base and Base Sepolia only (CDP FAQ), so no Coinbase rows exist for the other chains.

## Conflicts found in the third-party label files

- Biconomy v0.6 is swapped in both BundleBear and Pimlico 4337-stats. Both call 0x00000f7365... `verifying` and 0x00000f79b7... `token`. The verified contract names, the Biconomy repo (`scripts/utils/index.ts`) and the Etherscan name tags say the opposite: 0x00000f7365 is BiconomyTokenPaymaster and 0x00000f79b7 is VerifyingSingletonPaymaster v1.1.0. The CSV follows the contracts.
- Send 0x592e... is `token` in BundleBear and `verifying` in 4337-stats. The contract is a TokenPaymaster with `token()` = Base USDC, so the CSV uses erc20.
- 0x504e... is `alchemy both` in 4337-stats, but the verified code is the eth-infinitism sample VerifyingPaymaster with no token logic, so the CSV uses sponsor.
- Candide 0x769f... is `both` in BundleBear and `verifying` in 4337-stats. The CSV leaves it unknown.
- pichain 0x72e4... is `verifying` in 4337-stats, but it answers `token()`. The CSV leaves it unknown.
- BundleBear maps `both` to "unlabeled" in its spend-type charts (`erc4337_paymaster_spend_type_metric.sql`). If you copy its approach, all hybrid volume (Pimlico, Candide, Coinbase, Alchemy) falls out of the sponsor/ERC-20 split. Decode the events above instead.

## Ten high-volume Base addresses

| Address | Who | Source |
| - | - | - |
| 0x777777777777AeC03fd955926DbF81597e66834C | Pimlico SingletonPaymasterV7 (hybrid) | Pimlico docs |
| 0x888888888888Ec68A58AB8094Cc1AD20Ba3D2402 | Pimlico SingletonPaymasterV8 (hybrid) | Pimlico docs |
| 0x8bf5b18b733a864c17cd92615cd45d833fcfe105 | "Central City", a self-hosted copy of Coinbase's VerifyingPaymaster (v0.6) | operator's own repo, bytecode identical to 0x2FAEB |
| 0x6442f4729ee8c890d310ef92845d43184a12ee6a | thirdweb ShieldedVerifyingPaymasterV6 (sponsor) | BundleBear only |
| 0x2cc0c7981d846b9f2a16276556f6e8cb52bfb633 | Alchemy Gas Manager v0.7 (hybrid) | Alchemy aa-sdk and docs |
| 0x5fa66dfe8a3983e55071e8c4631ab43b5f33a4ab | thirdweb ShieldedVerifyingPaymasterV7 (sponsor) | BundleBear only |
| 0x7a956fd329d0c616f2d1dde98bb35694f397df46 | TokenPocket (v0.8), mode unknown | BundleBear 7702 labels, RevokeCash |
| 0x886f51115829cb326b74e8a834fb93fe25e85050 | unknown | none found |
| 0xdcbe0c1a00e4cf24ae77c52125e6e6b4f7c6db4e | Coinbase CDP VerifyingPaymaster v0.7 (hybrid) | coinbase/verifying-paymaster README |
| 0x4fd9098af9ddcb41da48a1d78f91f1398965addc | Alchemy Gas Manager v0.6 (hybrid) | Alchemy aa-sdk |

## Known addresses left out of the CSV (not live on the 5 chains)

- Alchemy: 0xEF725Aa22d43Ea69FB22bE2EBe6ECa205a6BCf5B (v0.7, World Chain and others), 0xEaf0Cde110a5d503f2dD69B3a49E031e29b3F9D2 and 0x4f84a207A80c39E9e8BaE717c1F25bA7AD1fB08F (v0.6, other chains). Per aa-sdk v4.88.5 `gas-manager.ts`, none has code on the 5 chains. Also the "Unify" addresses 0x0000000000ce04e2359130e7d0204A5249958921 (v0.6) and 0x00000000000667F27D4DB42334ec11a25db7EBb4 (v0.7) exist on all 5 chains but only as an `AlchemyProxyLoader` placeholder proxy. The SDK only uses them for chains not otherwise listed.
- thirdweb TokenPaymasters 0x3fea3c5744d715ff46e91c4e5c9a94426dff2af9 (Celo cUSD) and 0x9eb8cf7fba5ed9eedcc97a0d52254cc0e9b1ac25 (Lisk LSK).
- Circle testnet paymasters 0x31BE08D380A21fc740883c0BC434FcFc88740b58 (v0.7) and 0x3BA9A96eE3eFf3A69E2B18886AcF52027EFF8966 (v0.8).

## Limits of this research

- I found no public Alchemy v0.8 paymaster address. aa-sdk v4.88.5 only maps v0.6 and v0.7, and the current docs repo shows only the v0.7 address.
- I did not find newer Openfort (v0.7+), ZeroDev-owned, Particle (first-party), Stackup (first-party) or Gelato paymaster addresses. Openfort has a v0.9 paymaster in its tests, but no deployed address is published.
- About 20 rows rest only on BundleBear and/or Pimlico 4337-stats. Each one says "third-party label only" or names the single source in its note. Both files stopped updating in mid-2025, so newer deployments (for example any Pimlico or Alchemy v0.9 paymaster) are missing.
- Basescan, Arbiscan and Blockscout block automated requests, so Base/Arbitrum/Optimism/Polygon contract names come from Sourcify only. Rows marked `unverified` may still be verified on an Etherscan-family explorer.
- `chains` reflects code present on 2026-10-25. It does not prove the contract has recent volume on that chain.

## Open questions

1. The operator of 0x886f51115829cb326b74e8a834fb93fe25e85050 is not public. It is a Base-only v0.7 proxy (implementation 0xa0b5e7caedf77cbb560c2144b75cd1655a388332, owner 0xe739076bd1dc734346cbe8bb90035ff50b4d3b31).
2. Central City 0x8bf5... was first deployed at Base block 53000665 (2026-10-23 21:24 UTC), after the window ends, so it has no userops in this dataset.
3. TokenPocket 0x7a956fd3... is not classified as sponsor or ERC-20. Its bytecode is unverified, and it emits no event that the pipeline decodes.
4. The seven retired single-token Pimlico ERC-20 paymasters (2023 to 2024) are kept as separate rows. They matter only for older history.

## Second pass (2026-10-25)

I added 19 rows to `paymaster-labels.csv`. The 79 existing rows are byte-for-byte unchanged. I used the same method: on-chain probe on the 5 chains, Sourcify/Etherscan names, GitHub search.

**Labelled with a source that names the address**
- Alchemy: 0x...0804 is "prod paymaster v0.8" and 0x813d...d0ee is "staging paymaster v0.8", both named in `alchemyplatform/alchemy-proxy-loader/script/DeployConstants.sol`. The same file names the v0.9 prod proxy 0x000000000937001DeAAa5529004a07F638Edb57f, which I did not probe. This corrects the first-pass note that no Alchemy v0.8 address was public. 0x3f22...9048 appears in an Alchemy repo example, and its owner is Alchemy's `stgProxyLoaderOwner`.
- Biconomy MEE node paymasters: 0xd4b5...6fa1 is named in Biconomy's mee-explorer repo. 0x00e1...075f has identical bytecode and appears in a third-party MEE quote fixture.
- Symphony 0xb1ba...ac8f comes from the Monad protocol registry. Superform SuperNativePaymaster 0xec6b...effd comes from `superform-xyz/v2-core` prod deployment output.

**Labelled from the verified contract name only (weaker)**
- MixinPaymaster 0x9ea4...ec6a (a Pimlico SingletonPaymasterV8 fork)
- BronPaymaster 0x1b41...dce1 (ERC-20, EntryPoint v0.9)
- BicTokenPaymaster 0xb1c3...8386
- NotusPaymaster 0x1107...ec9c
- AmbirePaymaster 0x364e...322d
- Inferred, not named anywhere: 0x2bd4...d84c is "alchemy (inferred)". It shares Alchemy's verified implementation on Polygon and Alchemy's staging owner.

**Unknown (no public source):** 0x8868...35d3 (eth-infinitism sample VerifyingPaymaster on Arbitrum), 0x5d0a...bbbb, 0x9e75...9465, 0x066a...8b20, 0xdbd8...80c5, 0x6c56...b4ac. Each row records owner() for later matching. 0x9e75 and 0x8868 hold different contracts on other chains, so keep those labels chain-scoped.

**Circle 0x7cea...0a25 on Arbitrum:** confirmed live. Code is deployed, the implementation is SponsorPaymaster, entryPoint() is v0.6, and it holds about 4.93 ETH on EntryPoint v0.6 (balanceOf, 2026-10-25). No change to its row.

**Central City 0x8bf5...e105:** it was not deployed before 2026-09-24. Base `eth_getCode` is empty at block 53000664 and returns code at block 53000665, which is 2026-10-23 21:24:37 UTC. This matches the operator's repo. A ~5% Base share in a sample on 2026-10-24 means about one day of activity, so it cannot be a 30-day share.

**BIC ChargeFee question:** yes, it is an ERC-20 paymaster, and the paymaster is the BIC token contract itself (`symbol()` = BIC). In `_postOp` it calls `_transfer(sender, gasTreasury, costInToken)`, then `emit ChargeFee(userOpHash, sender, costInToken)`. The address field is the userop sender who paid. `fee` is the amount in BIC. The token is always BIC, because the event has no token field.

### Second-pass events (exact text)

Alchemy v0.8 VerifyingPaymaster (0x...0804, 0x813d...). Source: Sourcify, chain 8453, implementation 0x7a776fe72e75fece6ecab154e823b30f28653caa, file `src/VerifyingPaymaster.sol` L44. It is the same text as Alchemy v0.6/v0.7, so one decoder covers all of them. 0x3f22...'s implementation (Base 0xabcdf071...) has the same line.

```solidity
    event TokenSponsored(bytes32 indexed userOpHash, address tokenAddress, uint256 tokenAmount);
```

MixinPaymaster (0x9ea4...). Source: Sourcify, chain 8453, 0x9ea4e12ba5549a5f47e953043480716437d5ec6a, file `src/base/BaseSingletonPaymaster.sol` L118. The text is identical to the Pimlico singleton event in the first pass (same topic0, `paymasterMode` 0 = verifying, 1 = ERC-20). Separate Mixin from Pimlico by contract address.

```solidity
    event UserOperationSponsored(
        bytes32 indexed userOpHash,
        /// @param The user that requested sponsorship.
        address indexed user,
        /// @param The paymaster mode that was used.
        uint8 paymasterMode,
        /// @param The token that was used during sponsorship (ERC-20 mode only).
        address token,
        /// @param The amount of token paid during sponsorship (ERC-20 mode only).
        uint256 tokenAmountPaid,
        /// @param The exchange rate of the token at time of sponsorship (ERC-20 mode only).
        uint256 exchangeRate
    );
```

BicTokenPaymaster (0xb1c3...). Source: Sourcify, chain 42161, 0xb1c3960aeeaf4c255a877da04b06487bba698386, file `src/base/TokenSingletonPaymaster.sol` L45. It is emitted at L396.

```solidity
    event ChargeFee(bytes32 indexed userOpHash, address sender, uint256 fee);
```

Superform SuperNativePaymaster (0xec6b...). Source: Sourcify, chain 1, 0xec6b5d04c195eea62ca2991a7db94aab3502effd, file `src/interfaces/ISuperNativePaymaster.sol` L62 and L69. Both are emitted in `_postOp` of `src/paymaster/SuperNativePaymaster.sol`. Payment is in native ETH, so these events carry no mode or token.

```solidity
    event SuperNativePaymasterPostOp(bytes context);
```

```solidity
    event SuperNativePaymasterRefund(address indexed sender, uint256 refundAmount, uint256 initialRefund);
```

No per-op event: BronPaymaster (ERC-20, so use token Transfer logs), NotusPaymaster (empty postOp), Biconomy NodePaymaster, AmbirePaymaster.

### Second pass addendum: Polygon 0x84ba896235059fe27727eaa2695a9f99220d9a7e

- **Who:** unknown. No doc, repo, Sourcify or label file names the operator. The only lead is that a public Polymarket indexer (`eabz/evm-indexer`, `src/predictions/fixtures_data.rs`) records two txs sent to this address whose userops hit Polymarket contracts: an UmaCtfAdapter `QuestionInitialized` (block 94046041) and a NegRiskAdapter `ConditionResolution` (block 94048405). Market creation and resolution traffic hints that the operator is Polymarket or a Polymarket operator, but that is an inference, so the provider column stays unknown. growthepie's gtp-backend lists the address (polygon_pos) in a label backfill with no name.
- **EntryPoint:** v0.7 (`entryPoint()`). Polygon only. It is not a proxy, and its bytecode is unverified on Sourcify.
- **How it runs:** relayer EOAs call this contract's own `handleOps` (selector 0x765e827f). It forwards the bundle to EntryPoint v0.7 and pays from its EntryPoint deposit (about 18,740 POL on 2026-10-25). This is the same pattern as Biconomy's MEEEntryPoint and Superform's SuperNativePaymaster. Only about 16% of its bytecode matches Biconomy's, so it is not a copy.
- **Sponsor vs ERC-20:** sponsor, inferred from bytecode, not from source. It has `validatePaymasterUserOp`/`postOp` (v0.7), `deposit` and `withdrawTo` selectors, but no ERC-20 `transfer`/`transferFrom` selector, so it cannot charge users in a token itself. In the sample tx the USDC.e transfers are between Polymarket contracts, not to this address.
- **Per-op event:** none. Sample tx 0x3570f7c6c6156aa75d96605d5cd92d3fb458f6a5c41a0ff2d8d3c804d0eacf81 has no log emitted by this address, only EntryPoint `BeforeExecution`/`UserOperationEvent` and Polymarket/USDC.e logs. This is why no mode event is counted for it. Count its userops from EntryPoint `UserOperationEvent` with `paymaster` = this address.
- **Open:** the operator could be found by looking up owner() 0x3f68d7f32d163d3044f93bd75816765222eedb89 and the relayer EOAs (e.g. 0x47cb829ef9b2ef5dbd7307fe6ad58bfb83f38170, 0x5b244854fa56483b9baab9e11a036647a02f9e9a) on Polygonscan.
