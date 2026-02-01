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

### Notes

- V3 concentrated liquidity requires consideration of position ranges and rebalancing
- For simplicity, analysis may assume wide/full-range positions where applicable

---

## Strategies Compared

| Strategy | Mechanism | Outcome |
|----------|-----------|---------|
| **Naive buyback** | Swap ETH → OP at market (open/close/vwap) | Accumulate OP, subject to timing luck |
| **Timing buyback** | Swap only when price < N-day avg low | Better avg price, holds ETH when expensive |
| **POL (Protocol Owned Liquidity)** | Deploy ETH + OP as V3 liquidity | Accumulate both tokens + trading fees |

The POL thesis: instead of being a liquidity *taker* (paying fees, moving price), become a liquidity *maker* (earning fees, deepening pool, flywheel effect).

---

## Project Structure

```
op-buybacks/
├── analysis.py              # Main analysis script
├── requirements.txt
├── data/                    # Data inputs (populate these)
│   ├── swaps.parquet        # (a) Uni V3 OP/WETH swaps 2025
│   ├── ohlc_1D.parquet      # (b) Daily OHLC from swaps
│   └── daily_fees.parquet   # (c) OP Mainnet daily tx fees
├── results/                 # Output directory
└── src/
    ├── data/
    │   └── loaders.py       # Data loading utilities
    ├── uniswap_v3/
    │   └── liquidity.py     # V3 math: match_tokens_to_range(), etc.
    └── strategies/
        └── buyback.py       # Strategy implementations
```

## Data Requirements

### (a) swaps.parquet
All Uniswap V3 OP/WETH 0.3% pool swaps in 2025.

| Column | Type | Description |
|--------|------|-------------|
| timestamp | datetime | Block timestamp |
| price | float | OP per ETH at swap |
| amount_op | float | Signed OP amount |
| amount_eth | float | Signed ETH amount |
| liquidity | float | Active liquidity at tick |

### (b) ohlc_1D.parquet
Daily OHLC derived from swaps.

| Column | Type | Description |
|--------|------|-------------|
| timestamp | datetime | Day start |
| open/high/low/close | float | Price in OP/ETH |
| volume_op | float | Daily OP volume |
| volume_eth | float | Daily ETH volume |

### (c) daily_fees.parquet
OP Mainnet transaction fees.

| Column | Type | Description |
|--------|------|-------------|
| date | date | Calendar date |
| total_fees_eth | float | Sum of tx fees in ETH |
| tx_count | int | Number of transactions |

---

## Usage

```bash
pip install -r requirements.txt

# Populate data/ with your parquet files, then:
python analysis.py
```

---

## V3 Liquidity Functions

Key functions in `src/uniswap_v3/liquidity.py`:

- **`match_tokens_to_range(current_price, price_low, price_high, amount_op=None, amount_eth=None)`**
  Given one token amount and a price range, calculate the other token needed for a balanced position.

- **`match_range_to_tokens(current_price, amount_eth, amount_op, price_low=None, price_high=None)`**
  Given both token amounts and one price bound, calculate the other bound to use all tokens.
