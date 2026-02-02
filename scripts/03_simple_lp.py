"""
03_simple_lp.py

Strategy 2: Simple Wide LP

Deposit tx fees into a single wide-range Uniswap V3 LP position.
Track liquidity accumulation and fee compounding over time.

Assumptions:
- Free swapping to match token ratio for deposits (at current sqrtPriceX96)
- Wide range: ticks 90000-94980 (~8,099 to ~13,327 OP/ETH)
- Fees compound daily into next day's budget

For each day:
1. Budget = previous day's tx fees + previous day's earned LP fees
2. Get current sqrtPriceX96 from last swap of previous day
3. Calculate token split needed for the range using match_tokens_to_range
4. Add liquidity to position

For each swap (fee calculation):
5. Calculate fee share = our_liquidity / (pool_liquidity + our_liquidity)
6. Earn fees proportionally from that swap's trading fees
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

from uniswap import (
    tick_to_price,
    sqrtpx96_to_price,
    price_to_sqrtpx96,
    get_liquidity,
    get_position_balance,
    match_tokens_to_range,
)


# Tick spacing for 0.3% pool is 60
TICK_LOWER = 90000  # ~8,099 OP/ETH (90000 % 60 = 0 ✓)
TICK_UPPER = 94980  # ~13,327 OP/ETH (94980 % 60 = 0 ✓)


@dataclass
class LPPosition:
    """Tracks state of our LP position."""
    tick_lower: int
    tick_upper: int
    liquidity: int = 0
    total_eth_deposited: float = 0
    total_op_deposited: float = 0
    total_fees_earned_eth: float = 0
    total_fees_earned_op: float = 0


@dataclass
class DailyLPResult:
    """Result from a single day's LP activity."""
    date: str
    sqrtpx96: str
    price_op_per_eth: float
    budget_eth: float
    eth_deposited: float
    op_deposited: float
    liquidity_added: int
    cumulative_liquidity: int
    median_pool_liquidity: int
    liquidity_share: float
    fees_earned_eth: float
    fees_earned_op: float
    cumulative_fees_eth: float
    cumulative_fees_op: float


def load_data(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load hourly OHLCV, daily fees, and raw swaps data."""
    hourly = pd.read_csv(project_root / "data" / "hourly_ohlcv.csv")
    hourly["HOUR_"] = pd.to_datetime(hourly["HOUR_"])
    hourly["date"] = hourly["HOUR_"].dt.date

    fees = pd.read_csv(project_root / "data" / "op-mainnet-daily-fees-jan2026.csv")
    fees["block_date"] = pd.to_datetime(fees["block_date"]).dt.date

    swaps = pd.read_csv(project_root / "data" / "opweth03-swaps-jan2026.csv")
    swaps["BLOCK_TIMESTAMP"] = pd.to_datetime(swaps["BLOCK_TIMESTAMP"])
    swaps["date"] = swaps["BLOCK_TIMESTAMP"].dt.date

    return hourly, fees, swaps


def get_end_of_day_sqrtpx96(swaps: pd.DataFrame, date) -> Optional[str]:
    """Get the sqrtPriceX96 from the last swap of a given day."""
    day_swaps = swaps[swaps["date"] == date].sort_values("BLOCK_TIMESTAMP")
    if len(day_swaps) == 0:
        return None
    return str(day_swaps.iloc[-1]["SQRTPRICEX96"])


def calculate_fees_from_swaps(
    swaps: pd.DataFrame,
    date,
    our_liquidity: int,
    tick_lower: int,
    tick_upper: int,
    fee_rate: float = 0.003,  # 0.3% pool
) -> tuple[float, float]:
    """
    Calculate our fee earnings from each swap on a given day.

    For each swap:
    - Check if swap price is in our range
    - Calculate our share: our_liq / (pool_liq + our_liq)
    - Calculate fees from that swap (fee_rate of input amount)
    - Sum our share of fees

    Returns: (total_eth_fees, total_op_fees)
    """
    if our_liquidity <= 0:
        return 0.0, 0.0

    day_swaps = swaps[swaps["date"] == date]
    if len(day_swaps) == 0:
        return 0.0, 0.0

    # Get price bounds for our range
    price_lower = tick_to_price(tick_lower, decimal_adjustment=1, yx=True)
    price_upper = tick_to_price(tick_upper, decimal_adjustment=1, yx=True)

    total_eth_fees = 0.0
    total_op_fees = 0.0

    for _, swap in day_swaps.iterrows():
        # Get price after this swap
        sqrtpx96 = int(float(swap["SQRTPRICEX96"]))
        price = sqrtpx96_to_price(sqrtpx96, invert=False, decimal_adjustment=1)

        # Only earn fees if swap is in our range
        if price < price_lower or price > price_upper:
            continue

        pool_liquidity = int(swap["LIQUIDITY"])
        if pool_liquidity <= 0:
            continue

        # Our share of fees - we deepen the pool
        total_liquidity = pool_liquidity + our_liquidity
        our_share = our_liquidity / total_liquidity

        # Calculate fees from this swap
        # AMOUNT0_RAW = WETH change, AMOUNT1_RAW = OP change
        # Positive = token flows INTO pool (user sells that token)
        # Fee is paid on the token being sold
        amount0 = float(swap["AMOUNT0_RAW"]) / 1e18  # WETH (18 decimals)
        amount1 = float(swap["AMOUNT1_RAW"]) / 1e18  # OP (18 decimals)

        if amount0 > 0:
            # User sold ETH, fee in ETH
            swap_fee_eth = amount0 * fee_rate
            total_eth_fees += swap_fee_eth * our_share

        if amount1 > 0:
            # User sold OP, fee in OP
            swap_fee_op = amount1 * fee_rate
            total_op_fees += swap_fee_op * our_share

    return total_eth_fees, total_op_fees


def calculate_deposit(
    budget_eth: float,
    sqrtpx96: str,
    tick_lower: int,
    tick_upper: int,
) -> tuple[float, float, int]:
    """
    Calculate how to split ETH budget for LP deposit.

    Given:
    - budget_eth: total ETH available
    - sqrtpx96: current pool price
    - tick range for the position

    We need to split budget into:
    - eth_deposit: ETH to deposit directly
    - eth_swap: ETH to swap for OP at current price

    Uses match_tokens_to_range to find the required ratio.

    Returns:
        (eth_deposited, op_deposited, liquidity_added)
    """
    if budget_eth <= 0:
        return 0.0, 0.0, 0

    sqrtpx96_int = int(float(sqrtpx96))

    # Current price in OP/ETH
    price = sqrtpx96_to_price(sqrtpx96_int, invert=False, decimal_adjustment=1)

    # Find the ratio: how much OP do we need per 1 ETH deposited?
    # Use match_tokens_to_range with x=1 to get the ratio
    try:
        ratio_result = match_tokens_to_range(
            x=1.0,  # 1 ETH
            y=None,  # Calculate OP needed
            sqrtpx96=sqrtpx96_int,
            decimal_x=1e18,
            decimal_y=1e18,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
        )
        op_per_eth = ratio_result["amount_y"]
    except Exception:
        # If price is outside range or other error, handle gracefully
        op_per_eth = None

    if op_per_eth is None or op_per_eth <= 0 or not np.isfinite(op_per_eth):
        # Price might be outside range - deposit single-sided
        # If price is below range, deposit all as ETH
        # If price is above range, convert all to OP
        price_lower = tick_to_price(tick_lower, decimal_adjustment=1, yx=True)
        price_upper = tick_to_price(tick_upper, decimal_adjustment=1, yx=True)

        if price <= price_lower:
            # All ETH (price below range)
            eth_deposited = budget_eth
            op_deposited = 0.0
        elif price >= price_upper:
            # All OP (price above range)
            eth_deposited = 0.0
            op_deposited = budget_eth * price
        else:
            # Shouldn't happen, but fallback
            eth_deposited = budget_eth / 2
            op_deposited = (budget_eth / 2) * price
    else:
        # Normal case: price is in range
        # We need op_per_eth OP for each ETH deposited
        # Cost of that OP in ETH = op_per_eth / price
        # Total ETH needed = eth_deposit + (eth_deposit * op_per_eth / price)
        #                  = eth_deposit * (1 + op_per_eth / price)
        # So: eth_deposit = budget / (1 + op_per_eth / price)

        eth_deposit = budget_eth / (1 + op_per_eth / price)
        eth_swap = budget_eth - eth_deposit
        op_deposited = eth_swap * price
        eth_deposited = eth_deposit

    # Calculate liquidity from deposit
    if eth_deposited > 0 or op_deposited > 0:
        liquidity = get_liquidity(
            x=eth_deposited,
            y=op_deposited,
            sqrtpx96=sqrtpx96_int,
            decimal_x=1e18,
            decimal_y=1e18,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
        )
    else:
        liquidity = 0

    return eth_deposited, op_deposited, liquidity


def run_lp_simulation(
    fees: pd.DataFrame,
    swaps: pd.DataFrame,
    tick_lower: int = TICK_LOWER,
    tick_upper: int = TICK_UPPER,
) -> tuple[LPPosition, List[DailyLPResult]]:
    """
    Run LP simulation over the entire period.

    Fee calculation is done per-swap with correct share formula:
    our_share = our_liquidity / (pool_liquidity + our_liquidity)

    Returns:
        (final_position, daily_results)
    """
    dates = sorted(fees["block_date"].unique())

    position = LPPosition(tick_lower=tick_lower, tick_upper=tick_upper)
    daily_results = []

    pending_fees_eth = 0.0
    pending_fees_op = 0.0

    for i, date in enumerate(dates):
        if i == 0:
            # No budget for first day (no T-1 fees)
            continue

        # Budget from previous day's tx fees
        prev_date = dates[i - 1]
        tx_fees_eth = fees[fees["block_date"] == prev_date]["fees_eth"].values[0]

        # Get sqrtPriceX96 from end of previous day (the price we'd see at start of today)
        sqrtpx96 = get_end_of_day_sqrtpx96(swaps, prev_date)
        if sqrtpx96 is None:
            # No swaps on previous day, try to get from current day's first swap
            sqrtpx96 = get_end_of_day_sqrtpx96(swaps, date)
            if sqrtpx96 is None:
                continue

        price = sqrtpx96_to_price(int(float(sqrtpx96)), invert=False, decimal_adjustment=1)

        # Convert pending OP fees to ETH equivalent for budget
        pending_fees_eth_equiv = pending_fees_eth + (pending_fees_op / price if price > 0 else 0)
        budget_eth = tx_fees_eth + pending_fees_eth_equiv

        # Calculate deposit
        eth_deposited, op_deposited, liquidity_added = calculate_deposit(
            budget_eth=budget_eth,
            sqrtpx96=sqrtpx96,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
        )

        # Update position BEFORE calculating fees (we deposit at start of day)
        position.liquidity += liquidity_added
        position.total_eth_deposited += eth_deposited
        position.total_op_deposited += op_deposited

        # Calculate fees from each swap on this day
        # Uses our_liq / (pool_liq + our_liq) formula
        fees_earned_eth, fees_earned_op = calculate_fees_from_swaps(
            swaps=swaps,
            date=date,
            our_liquidity=position.liquidity,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
        )

        position.total_fees_earned_eth += fees_earned_eth
        position.total_fees_earned_op += fees_earned_op

        # Store for next day's budget
        pending_fees_eth = fees_earned_eth
        pending_fees_op = fees_earned_op

        # For reporting, calculate median liquidity share for the day
        day_swaps = swaps[swaps["date"] == date]
        if len(day_swaps) > 0 and position.liquidity > 0:
            median_pool_liq = day_swaps["LIQUIDITY"].astype(float).median()
            liquidity_share = position.liquidity / (median_pool_liq + position.liquidity)
        else:
            median_pool_liq = 0
            liquidity_share = 0

        daily_results.append(DailyLPResult(
            date=str(date),
            sqrtpx96=sqrtpx96,
            price_op_per_eth=price,
            budget_eth=budget_eth,
            eth_deposited=eth_deposited,
            op_deposited=op_deposited,
            liquidity_added=liquidity_added,
            cumulative_liquidity=position.liquidity,
            median_pool_liquidity=int(median_pool_liq),
            liquidity_share=liquidity_share,
            fees_earned_eth=fees_earned_eth,
            fees_earned_op=fees_earned_op,
            cumulative_fees_eth=position.total_fees_earned_eth,
            cumulative_fees_op=position.total_fees_earned_op,
        ))

    return position, daily_results


def main():
    project_root = Path(__file__).parent.parent

    print("Loading data...")
    hourly, fees, swaps = load_data(project_root)

    # Range info
    price_lower = tick_to_price(TICK_LOWER, decimal_adjustment=1, yx=True)
    price_upper = tick_to_price(TICK_UPPER, decimal_adjustment=1, yx=True)

    print(f"\nLP Range (tick spacing = 60 for 0.3% pool):")
    print(f"  Ticks: {TICK_LOWER} to {TICK_UPPER}")
    print(f"  Prices: {price_lower:.2f} to {price_upper:.2f} OP/ETH")

    print("\nRunning LP simulation...")
    position, daily_results = run_lp_simulation(
        fees=fees,
        swaps=swaps,
        tick_lower=TICK_LOWER,
        tick_upper=TICK_UPPER,
    )

    # Summary
    print("\n" + "=" * 60)
    print("LP STRATEGY RESULTS")
    print("=" * 60)

    print(f"\nDeposits:")
    print(f"  Total ETH deposited: {position.total_eth_deposited:.4f}")
    print(f"  Total OP deposited:  {position.total_op_deposited:,.2f}")

    print(f"\nFees Earned:")
    print(f"  ETH fees: {position.total_fees_earned_eth:.6f}")
    print(f"  OP fees:  {position.total_fees_earned_op:,.2f}")

    print(f"\nFinal Position:")
    print(f"  Liquidity: {position.liquidity:,}")

    # Get final position value using last day's end price
    if daily_results:
        last_result = daily_results[-1]
        final_sqrtpx96 = int(float(last_result.sqrtpx96))
        final_price = last_result.price_op_per_eth

        # Get actual end-of-month price
        dates = sorted(swaps["date"].unique())
        final_sqrtpx96_str = get_end_of_day_sqrtpx96(swaps, dates[-1])
        if final_sqrtpx96_str:
            final_sqrtpx96 = int(float(final_sqrtpx96_str))
            final_price = sqrtpx96_to_price(final_sqrtpx96, invert=False, decimal_adjustment=1)

        balance = get_position_balance(
            position_l=position.liquidity,
            sqrtpx96=final_sqrtpx96,
            tick_lower=TICK_LOWER,
            tick_upper=TICK_UPPER,
            decimal_x=1e18,
            decimal_y=1e18,
        )

        print(f"\nPosition Value at Final Price ({final_price:.2f} OP/ETH):")
        print(f"  ETH in position: {balance['token0']:.4f}")
        print(f"  OP in position:  {balance['token1']:,.2f}")

        # Total OP equivalent
        total_op_equiv = balance["token1"] + (balance["token0"] * final_price)
        total_op_equiv += position.total_fees_earned_op + (position.total_fees_earned_eth * final_price)
        print(f"\nTotal OP Equivalent (position + fees): {total_op_equiv:,.2f}")

    # Save daily results
    daily_df = pd.DataFrame([vars(r) for r in daily_results])
    output_path = project_root / "data" / "lp_daily_results.csv"
    daily_df.to_csv(output_path, index=False)
    print(f"\nDaily results saved to: {output_path}")

    # Print daily breakdown
    print("\n" + "=" * 60)
    print("DAILY BREAKDOWN")
    print("=" * 60)
    print(daily_df[["date", "price_op_per_eth", "budget_eth", "eth_deposited", "op_deposited",
                    "liquidity_share", "fees_earned_eth", "fees_earned_op"]].to_string(index=False))


if __name__ == "__main__":
    main()
