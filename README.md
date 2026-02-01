# OP Buybacks

A case study on Optimism's token buyback program.

## Background

In January 2026, Optimism governance [approved](https://www.coindesk.com/business/2026/01/28/optimism-governance-approves-op-token-buyback-plan-tied-to-superchain-revenue) a proposal to allocate **50% of net Superchain sequencer revenue** toward recurring OP token buybacks. The measure passed with 84.4% approval and marks Optimism's first formal effort to tie OP token demand directly to network activity.

### Key Details

- **Duration**: 12-month pilot starting February 2026
- **Allocation**: 50% of sequencer revenue → buybacks; 50% → ecosystem funding, grants, and operations
- **Scope**: Revenue from the Superchain — OP Mainnet, Base, Unichain, World Chain, Soneium, Ink, and other OP Stack chains
- **Scale**: Based on the prior year's 5,868 ETH in revenue, roughly 2,700 ETH (~$8M) would flow to buybacks annually
- **Token handling**: Purchased OP held in treasury; future governance will decide on burns, staking incentives, or redistribution

### Strategic Significance

The Superchain currently captures **61% of L2 fee market share** and processes 13% of all crypto transactions. This buyback mechanism transitions OP from a pure governance token to one with value accrual tied to Superchain growth.

---

## Analysis Scope

This case study focuses on:

- **Revenue source**: OP Mainnet transaction fees only (denominated in ETH)
- **Execution venue**: Uniswap V3 OP/WETH 0.3% pool on OP Mainnet

### Contracts

| Contract | Address |
|----------|---------|
| Uniswap V3 OP/WETH Pool (0.3%) | [`0x68f5c0a2de713a54991e01858fd27a3832401849`](https://optimistic.etherscan.io/address/0x68f5c0a2de713a54991e01858fd27a3832401849) |
| OP Token | [`0x4200000000000000000000000000000000000042`](https://optimistic.etherscan.io/address/0x4200000000000000000000000000000000000042) |
| WETH | [`0x4200000000000000000000000000000000000006`](https://optimistic.etherscan.io/address/0x4200000000000000000000000000000000000006) |

---

## Strategies Compared

| Strategy | Mechanism | Outcome |
|----------|-----------|---------|
| **Naive buyback** | Swap ETH → OP at random time/price | Accumulate OP, subject to timing luck |
| **Timing buyback** | Swap when OP is relatively low (OHLC signals) | Potentially better avg price, more complexity |
| **POL (Protocol Owned Liquidity)** | Deploy ETH + OP as Uniswap V3 liquidity | Accumulate both tokens + trading fees |

---

## The POL Pitch

Instead of simply buying OP from the pool (being a liquidity *taker*), the protocol could become a liquidity *maker*:

1. **Deepen the pool** — More liquidity enables larger trades with less slippage
2. **Enable more volume** — Better execution attracts more trading activity
3. **More volume = more revenue** — Trading fees flow back to LPs (including the protocol)
4. **Compound the gains** — Use accumulated fees to grow the position over time
5. **Accumulate both ETH and OP** — Diversified treasury growth vs. single-asset accumulation
6. **Grow OP usability** — A deeper, more liquid market makes OP more useful as a token

### POL Implementation Options

**Single wide position**: Continuously add to one wide-range position. Variable amounts of ETH (from tx fees) and OP (from partial conversion) get deposited into the same range. Simpler to manage.

**Multiple parallel positions**: Create new positions periodically, each fully deploying that period's tx fees. More granular control, but requires active management of many positions.

---

## Data Requirements

To backtest these strategies against 2025 data:

| Dataset | Description |
|---------|-------------|
| **(a) Swaps** | All swaps in Uni V3 OP/WETH pool — price, amounts, liquidity at tick |
| **(b) OHLC** | OP/ETH open-high-low-close derived from swaps |
| **(c) Daily fees** | OP Mainnet transaction fees in ETH at daily level |
| **(d) V3 math** | Functions to create/measure liquidity: `match_tokens_to_range()`, `match_range_to_tokens()`, etc. |
