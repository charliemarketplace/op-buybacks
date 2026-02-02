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

## Data

All data covers **January 2026** as a simulation period.

### Raw Data (`data/`)

| File | Description |
|------|-------------|
| `opweth03-swaps-jan2026.csv` | 17,201 swaps from Uni V3 OP/WETH 0.3% pool |
| `op-mainnet-daily-fees-jan2026.csv` | Daily OP Mainnet transaction fees in ETH |

### Processed Data

| File | Description |
|------|-------------|
| `hourly_ohlcv.csv` | Hourly aggregated OHLCV data |
| `monte_carlo_results.csv` | Results from 1,000 MC simulations |
| `lp_daily_results.csv` | Daily LP position and fee data |

**Hourly OHLCV columns:**
- `HOUR_` — Hourly timestamp
- `open`, `high`, `low`, `close` — OP/ETH prices (higher = more OP per ETH)
- `vwap` — Volume-weighted average price within the hour
- `op_bought`, `op_sold` — OP volume by direction
- `eth_bought`, `eth_sold` — ETH volume by direction
- `op_fees`, `eth_fees` — LP fees earned (0.3% of sold amounts)
- `trade_count` — Number of swaps in hour

### Queries (`queries/`)

SQL queries used to extract raw data from on-chain sources.

---

## Code

### Uniswap V3 Math (`uniswap/`)

Python package with Uniswap V3 calculation utilities:

```python
from uniswap import (
    tick_to_price,           # Convert tick to human-readable price
    get_closest_tick,        # Find nearest valid tick for a price
    sqrtpx96_to_price,       # Convert sqrtPriceX96 to price
    price_to_sqrtpx96,       # Convert price to sqrtPriceX96
    get_liquidity,           # Calculate liquidity from token amounts
    get_position_balance,    # Get token balances for a position
    match_tokens_to_range,   # Match one token to a range, get other amount
    price_all_tokens,        # Find tick boundary to use all tokens
    swap_within_tick,        # Simulate swap within single tick
    swap_across_ticks,       # Simulate swap across tick boundaries
)
```

### Scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `01_processing.py` | Process raw swaps → hourly OHLCV with VWAP |
| `02_monte_carlo_buys.py` | Monte Carlo simulation of random daily buys |
| `03_simple_lp.py` | Simple wide LP strategy simulation |
| `04_compare_strategies.py` | Compare strategy outcomes |

### Visualizations (`visuals/`)

Interactive Highcharts HTML files:

| File | Description |
|------|-------------|
| `01_daily_tx_fees.html` | Daily transaction fees bar chart |
| `02_monte_carlo_histogram.html` | Distribution of OP accumulated across simulations |
| `03_lp_results.html` | LP fees, cumulative growth, and liquidity share |

---

## Strategies

Two buyback strategies to compare, each using Day T-1 tx fees as Day T budget:

### 1. Monte Carlo Random Purchases

Execute random purchases at random times throughout the day. Simulates naive DCA approach — buy OP directly with ETH fees.

- 1,000 simulations with 1-10 random buys per day
- Prices sampled from hourly low-high range

### 2. Simple Wide LP

Deposit fees into a single wide-range LP position. All future deposits go to the same range (assume free swapping to match token ratio). Track liquidity accumulation and fee compounding over time.

- Tick range: 90000 to 94980 (~8,099 to ~13,327 OP/ETH)
- Fee earnings calculated per-swap: `our_liq / (pool_liq + our_liq)`
- Fees compound into next day's deposit

---

## Results

| Strategy | OP Equivalent | vs Baseline |
|----------|---------------|-------------|
| Monte Carlo (mean) | ~218,923 OP | — |
| Simple Wide LP | ~232,617 OP | +6.3% |

The LP strategy wins by earning trading fees (~1,738 OP + 0.17 ETH) while maintaining diversified exposure to both tokens.
