"""
03_simple_lp.py

Strategy 2: Simple Wide LP

Deposit tx fees into a single wide-range Uniswap V3 LP position.
Track liquidity accumulation and fee compounding over time.

Assumptions:
- Free swapping to match token ratio for deposits
- Wide range that stays in-range throughout the period
- Fees compound daily into next day's budget

For each day:
1. Budget = previous day's tx fees + previous day's earned LP fees
2. Calculate token split needed for the range at current price
3. Add liquidity to position
4. Calculate fee share = our_liquidity / total_pool_liquidity
5. Earn fees proportionally from pool trading fees
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List

from uniswap import (
    tick_to_price,
    get_closest_tick,
    sqrtpx96_to_price,
    price_to_sqrtpx96,
    get_liquidity,
    get_position_balance,
    match_tokens_to_range,
)


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
    budget_eth: float
    eth_deposited: float
    op_deposited: float  # From "free swap"
    liquidity_added: int
    cumulative_liquidity: int
    pool_liquidity: int
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


def get_daily_pool_stats(hourly: pd.DataFrame, swaps: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate pool stats to daily level.

    Returns DataFrame with:
    - date
    - avg_price: average OP/ETH price
    - pool_fees_eth: total ETH fees earned by pool
    - pool_fees_op: total OP fees earned by pool
    - avg_liquidity: average active liquidity
    """
    # Daily price from hourly (use VWAP or simple average of close)
    daily_price = hourly.groupby("date").agg(
        avg_price=("close", "mean"),
        pool_fees_eth=("eth_fees", "sum"),
        pool_fees_op=("op_fees", "sum"),
    ).reset_index()

    # Average liquidity from swaps
    daily_liq = swaps.groupby("date").agg(
        avg_liquidity=("LIQUIDITY", "mean"),
    ).reset_index()

    daily = daily_price.merge(daily_liq, on="date", how="left")
    daily["avg_liquidity"] = daily["avg_liquidity"].fillna(daily["avg_liquidity"].mean())

    return daily


def calculate_deposit(
    budget_eth: float,
    current_price: float,
    tick_lower: int,
    tick_upper: int,
) -> tuple[float, float, int]:
    """
    Calculate how to split ETH budget for LP deposit.

    Uses "free swap" assumption - converts some ETH to OP at current price
    to match the required ratio for the range.

    Returns:
        (eth_to_deposit, op_to_deposit, liquidity_added)
    """
    if budget_eth <= 0:
        return 0, 0, 0

    # Get sqrtPriceX96 for current price
    # decimal_adjustment = 1 for same-decimal tokens
    sqrtpx96 = price_to_sqrtpx96(current_price, invert=False, decimal_adjustment=1)

    # Try depositing all ETH first, see how much OP needed
    result = match_tokens_to_range(
        x=budget_eth,  # ETH (token0)
        y=None,  # Calculate OP needed
        sqrtpx96=sqrtpx96,
        decimal_x=1e18,
        decimal_y=1e18,
        tick_lower=tick_lower,
        tick_upper=tick_upper,
    )

    op_needed = result["amount_y"]

    if op_needed is None or op_needed <= 0:
        # Price might be outside range, deposit as single-sided
        # For simplicity, just use all ETH
        op_needed = 0

    # Cost of OP in ETH terms
    eth_for_op = op_needed / current_price if current_price > 0 else 0

    if eth_for_op > budget_eth:
        # Not enough ETH to match, scale down
        scale = budget_eth / (budget_eth + eth_for_op) if eth_for_op > 0 else 1
        eth_to_deposit = budget_eth * scale
        op_to_deposit = (budget_eth - eth_to_deposit) * current_price
    else:
        eth_to_deposit = budget_eth - eth_for_op
        op_to_deposit = op_needed

    # Calculate liquidity from deposit
    if eth_to_deposit > 0 or op_to_deposit > 0:
        liquidity = get_liquidity(
            x=eth_to_deposit,
            y=op_to_deposit,
            sqrtpx96=sqrtpx96,
            decimal_x=1e18,
            decimal_y=1e18,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
        )
    else:
        liquidity = 0

    return eth_to_deposit, op_to_deposit, liquidity


def run_lp_simulation(
    hourly: pd.DataFrame,
    fees: pd.DataFrame,
    swaps: pd.DataFrame,
    tick_lower: int = 90000,
    tick_upper: int = 94000,
) -> tuple[LPPosition, List[DailyLPResult]]:
    """
    Run LP simulation over the entire period.

    Returns:
        (final_position, daily_results)
    """
    daily_pool = get_daily_pool_stats(hourly, swaps)
    dates = sorted(fees["block_date"].unique())

    position = LPPosition(tick_lower=tick_lower, tick_upper=tick_upper)
    daily_results = []

    pending_fees_eth = 0  # Fees earned yesterday, added to today's budget
    pending_fees_op = 0

    for i, date in enumerate(dates):
        if i == 0:
            # No budget for first day
            continue

        # Budget from previous day's tx fees
        prev_date = dates[i - 1]
        tx_fees_eth = fees[fees["block_date"] == prev_date]["fees_eth"].values[0]

        # Total budget = tx fees + earned LP fees (converted to ETH equivalent)
        # For simplicity, treat OP fees as already converted at avg price
        pool_data = daily_pool[daily_pool["date"] == date]
        if len(pool_data) == 0:
            continue

        current_price = pool_data["avg_price"].values[0]
        pool_fees_eth = pool_data["pool_fees_eth"].values[0]
        pool_fees_op = pool_data["pool_fees_op"].values[0]
        pool_liquidity = int(pool_data["avg_liquidity"].values[0])

        # Convert pending OP fees to ETH equivalent for budget
        pending_fees_eth_equiv = pending_fees_eth + (pending_fees_op / current_price if current_price > 0 else 0)
        budget_eth = tx_fees_eth + pending_fees_eth_equiv

        # Calculate deposit
        eth_deposited, op_deposited, liquidity_added = calculate_deposit(
            budget_eth=budget_eth,
            current_price=current_price,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
        )

        # Update position
        position.liquidity += liquidity_added
        position.total_eth_deposited += eth_deposited
        position.total_op_deposited += op_deposited

        # Calculate fee share
        # Our share of pool = our_liquidity / pool_liquidity
        if pool_liquidity > 0 and position.liquidity > 0:
            liquidity_share = position.liquidity / pool_liquidity
        else:
            liquidity_share = 0

        # Fees earned today (will be added to tomorrow's budget)
        fees_earned_eth = pool_fees_eth * liquidity_share
        fees_earned_op = pool_fees_op * liquidity_share

        position.total_fees_earned_eth += fees_earned_eth
        position.total_fees_earned_op += fees_earned_op

        # Store for next day's budget
        pending_fees_eth = fees_earned_eth
        pending_fees_op = fees_earned_op

        daily_results.append(DailyLPResult(
            date=str(date),
            budget_eth=budget_eth,
            eth_deposited=eth_deposited,
            op_deposited=op_deposited,
            liquidity_added=liquidity_added,
            cumulative_liquidity=position.liquidity,
            pool_liquidity=pool_liquidity,
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

    # Define wide range
    tick_lower = 90000
    tick_upper = 94000
    price_lower = tick_to_price(tick_lower, decimal_adjustment=1, yx=True)
    price_upper = tick_to_price(tick_upper, decimal_adjustment=1, yx=True)

    print(f"\nLP Range:")
    print(f"  Ticks: {tick_lower} to {tick_upper}")
    print(f"  Prices: {price_lower:.2f} to {price_upper:.2f} OP/ETH")

    print("\nRunning LP simulation...")
    position, daily_results = run_lp_simulation(
        hourly=hourly,
        fees=fees,
        swaps=swaps,
        tick_lower=tick_lower,
        tick_upper=tick_upper,
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

    # Get final position value
    if daily_results:
        # Use last day's pool data
        daily_pool = get_daily_pool_stats(hourly, swaps)
        last_date = pd.to_datetime(daily_results[-1].date).date()
        final_price_data = daily_pool[daily_pool["date"] == last_date]
        if len(final_price_data) > 0:
            final_price = final_price_data["avg_price"].values[0]

            # Calculate position value at final price
            sqrtpx96 = price_to_sqrtpx96(final_price, invert=False, decimal_adjustment=1)
            balance = get_position_balance(
                position_l=position.liquidity,
                sqrtpx96=sqrtpx96,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
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
    print(daily_df[["date", "budget_eth", "eth_deposited", "op_deposited",
                    "liquidity_share", "fees_earned_eth", "fees_earned_op"]].to_string(index=False))


if __name__ == "__main__":
    main()
