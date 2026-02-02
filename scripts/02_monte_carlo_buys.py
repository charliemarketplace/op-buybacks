"""
02_monte_carlo_buys.py

Strategy 1: Monte Carlo Random Purchases

Simulates naive DCA approach where Day T-1 tx fees are used to buy OP
at random times during Day T.

For each day:
1. Budget = previous day's tx fees (ETH)
2. Randomly select purchase times throughout the day
3. Execute buys at prices sampled from hourly OHLC range
4. Track total OP accumulated

Runs multiple simulations to get distribution of outcomes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List


@dataclass
class SimulationResult:
    """Result from a single Monte Carlo simulation."""
    total_op_bought: float
    total_eth_spent: float
    avg_price: float  # OP per ETH
    daily_buys: pd.DataFrame


def load_data(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load hourly OHLCV and daily fees data."""
    hourly = pd.read_csv(project_root / "data" / "hourly_ohlcv.csv")
    hourly["HOUR_"] = pd.to_datetime(hourly["HOUR_"])
    hourly["date"] = hourly["HOUR_"].dt.date

    fees = pd.read_csv(project_root / "data" / "op-mainnet-daily-fees-jan2026.csv")
    fees["block_date"] = pd.to_datetime(fees["block_date"]).dt.date

    return hourly, fees


def sample_price_in_hour(row: pd.Series, rng: np.random.Generator) -> float:
    """
    Sample a random execution price within an hour's range.

    Uses uniform distribution between low and high.
    Returns OP per ETH (higher = more OP per ETH = better for buyer).
    """
    return rng.uniform(row["low"], row["high"])


def simulate_day(
    date,
    budget_eth: float,
    hourly_data: pd.DataFrame,
    rng: np.random.Generator,
    min_buys: int = 1,
    max_buys: int = 10,
) -> dict:
    """
    Simulate random purchases for a single day.

    Args:
        date: The date to simulate
        budget_eth: ETH budget for the day
        hourly_data: Hourly OHLCV data for this date
        rng: Random number generator
        min_buys: Minimum number of purchases
        max_buys: Maximum number of purchases

    Returns:
        Dict with date, eth_spent, op_bought, avg_price, num_buys
    """
    day_hours = hourly_data[hourly_data["date"] == date]

    if len(day_hours) == 0:
        return {
            "date": date,
            "eth_spent": 0,
            "op_bought": 0,
            "avg_price": 0,
            "num_buys": 0,
        }

    # Random number of buys
    num_buys = rng.integers(min_buys, max_buys + 1)

    # Split budget across buys (could be equal or random split)
    # Using random split for more variance
    splits = rng.random(num_buys)
    splits = splits / splits.sum()
    eth_per_buy = budget_eth * splits

    # Random hours for each buy (with replacement)
    buy_hours = rng.choice(len(day_hours), size=num_buys, replace=True)

    total_op = 0
    for i, hour_idx in enumerate(buy_hours):
        hour_row = day_hours.iloc[hour_idx]
        price = sample_price_in_hour(hour_row, rng)  # OP per ETH
        op_bought = eth_per_buy[i] * price
        total_op += op_bought

    avg_price = total_op / budget_eth if budget_eth > 0 else 0

    return {
        "date": date,
        "eth_spent": budget_eth,
        "op_bought": total_op,
        "avg_price": avg_price,
        "num_buys": num_buys,
    }


def run_simulation(
    hourly: pd.DataFrame,
    fees: pd.DataFrame,
    seed: int = None,
    min_buys: int = 1,
    max_buys: int = 10,
) -> SimulationResult:
    """
    Run a single Monte Carlo simulation over the entire period.

    Day T budget = Day T-1 fees.
    """
    rng = np.random.default_rng(seed)

    # Get sorted unique dates
    dates = sorted(fees["block_date"].unique())

    daily_results = []

    for i, date in enumerate(dates):
        if i == 0:
            # No budget for first day (no T-1 fees)
            continue

        # Budget from previous day
        prev_date = dates[i - 1]
        budget_eth = fees[fees["block_date"] == prev_date]["fees_eth"].values[0]

        result = simulate_day(
            date=date,
            budget_eth=budget_eth,
            hourly_data=hourly,
            rng=rng,
            min_buys=min_buys,
            max_buys=max_buys,
        )
        daily_results.append(result)

    daily_df = pd.DataFrame(daily_results)

    total_op = daily_df["op_bought"].sum()
    total_eth = daily_df["eth_spent"].sum()
    avg_price = total_op / total_eth if total_eth > 0 else 0

    return SimulationResult(
        total_op_bought=total_op,
        total_eth_spent=total_eth,
        avg_price=avg_price,
        daily_buys=daily_df,
    )


def run_monte_carlo(
    hourly: pd.DataFrame,
    fees: pd.DataFrame,
    n_simulations: int = 1000,
    min_buys: int = 1,
    max_buys: int = 10,
) -> pd.DataFrame:
    """
    Run multiple Monte Carlo simulations.

    Returns DataFrame with results from each simulation.
    """
    results = []

    for i in range(n_simulations):
        sim = run_simulation(
            hourly=hourly,
            fees=fees,
            seed=i,  # Reproducible but different each sim
            min_buys=min_buys,
            max_buys=max_buys,
        )
        results.append({
            "sim_id": i,
            "total_op_bought": sim.total_op_bought,
            "total_eth_spent": sim.total_eth_spent,
            "avg_price": sim.avg_price,
        })

    return pd.DataFrame(results)


def main():
    project_root = Path(__file__).parent.parent

    print("Loading data...")
    hourly, fees = load_data(project_root)

    print(f"  Hourly data: {len(hourly)} rows")
    print(f"  Daily fees: {len(fees)} days")
    print(f"  Total ETH fees: {fees['fees_eth'].sum():.4f}")

    # Run Monte Carlo
    n_sims = 1000
    print(f"\nRunning {n_sims} simulations...")

    results = run_monte_carlo(
        hourly=hourly,
        fees=fees,
        n_simulations=n_sims,
        min_buys=1,
        max_buys=10,
    )

    # Summary statistics
    print("\n" + "=" * 60)
    print("MONTE CARLO RESULTS: Random Purchases")
    print("=" * 60)

    print(f"\nTotal ETH spent: {results['total_eth_spent'].mean():.4f}")
    print(f"\nOP Accumulated:")
    print(f"  Mean:   {results['total_op_bought'].mean():,.2f}")
    print(f"  Median: {results['total_op_bought'].median():,.2f}")
    print(f"  Std:    {results['total_op_bought'].std():,.2f}")
    print(f"  Min:    {results['total_op_bought'].min():,.2f}")
    print(f"  Max:    {results['total_op_bought'].max():,.2f}")

    print(f"\nAverage Price (OP/ETH):")
    print(f"  Mean:   {results['avg_price'].mean():,.2f}")
    print(f"  Median: {results['avg_price'].median():,.2f}")
    print(f"  Std:    {results['avg_price'].std():,.2f}")

    # Save results
    output_path = project_root / "data" / "monte_carlo_results.csv"
    results.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")

    # Also run one detailed simulation for inspection
    print("\n" + "=" * 60)
    print("SAMPLE SIMULATION (seed=42)")
    print("=" * 60)

    sample_sim = run_simulation(hourly, fees, seed=42)
    print(f"\nDaily breakdown:")
    print(sample_sim.daily_buys.to_string(index=False))

    sample_output = project_root / "data" / "monte_carlo_sample_daily.csv"
    sample_sim.daily_buys.to_csv(sample_output, index=False)
    print(f"\nSample daily data saved to: {sample_output}")


if __name__ == "__main__":
    main()
