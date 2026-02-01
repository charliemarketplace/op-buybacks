"""
OP Buybacks Strategy Analysis

Compare strategies for deploying OP Mainnet tx fees:
1. Naive buyback - swap ETH → OP at market
2. Timing buyback - wait for favorable prices
3. POL - deploy as Uniswap V3 liquidity

Usage:
    python analysis.py
"""

import pandas as pd
from pathlib import Path

from src.data.loaders import load_swaps, load_ohlc, load_daily_fees
from src.strategies.buyback import (
    NaiveBuybackStrategy,
    TimingBuybackStrategy,
    POLStrategy,
    compare_strategies,
)


def main():
    print("=" * 60)
    print("OP Buybacks Strategy Analysis")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    try:
        swaps = load_swaps()
        ohlc = load_ohlc("1D")
        daily_fees = load_daily_fees()
        print(f"  Swaps: {len(swaps):,} records")
        print(f"  OHLC: {len(ohlc):,} days")
        print(f"  Fees: {len(daily_fees):,} days")
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}")
        print("\n  Please populate the data/ directory with:")
        print("    - swaps.parquet (Uni V3 OP/WETH swaps)")
        print("    - ohlc_1D.parquet (daily OHLC)")
        print("    - daily_fees.parquet (OP Mainnet fees)")
        return

    # Summary stats
    print("\nData Summary:")
    print(f"  Date range: {daily_fees['date'].min()} to {daily_fees['date'].max()}")
    print(f"  Total ETH fees: {daily_fees['total_fees_eth'].sum():,.2f} ETH")
    print(f"  Avg daily fees: {daily_fees['total_fees_eth'].mean():,.4f} ETH")
    print(f"  Price range: {ohlc['low'].min():,.2f} - {ohlc['high'].max():,.2f} OP/ETH")

    # Define strategies
    strategies = [
        NaiveBuybackStrategy(execution_time="close"),
        NaiveBuybackStrategy(execution_time="open"),
        NaiveBuybackStrategy(execution_time="vwap"),
        TimingBuybackStrategy(lookback_days=7),
        TimingBuybackStrategy(lookback_days=30),
        POLStrategy(mode="single_wide", range_width_pct=0.5),
        POLStrategy(mode="single_wide", range_width_pct=0.25),
        POLStrategy(mode="multiple", range_width_pct=0.1),
    ]

    # Run comparison
    print("\nRunning strategies...")
    results = compare_strategies(strategies, daily_fees, ohlc, swaps)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(results.to_string(index=False))

    # Save results
    output_path = Path("results")
    output_path.mkdir(exist_ok=True)
    results.to_csv(output_path / "strategy_comparison.csv", index=False)
    print(f"\nResults saved to {output_path / 'strategy_comparison.csv'}")

    # POL vs Naive comparison
    print("\n" + "=" * 60)
    print("POL vs NAIVE COMPARISON")
    print("=" * 60)

    naive_result = results[results["strategy"] == "naive_close"].iloc[0]
    pol_result = results[results["strategy"] == "pol_single_wide"].iloc[0]

    print(f"\nNaive (close):")
    print(f"  OP acquired: {naive_result['op_acquired']:,.2f}")
    print(f"  Avg price: {naive_result['avg_price']:,.2f} OP/ETH")

    print(f"\nPOL (50% range):")
    print(f"  OP acquired: {pol_result['op_acquired']:,.2f}")
    print(f"  Fees earned (ETH): {pol_result['fees_eth']:,.4f}")
    print(f"  Fees earned (OP): {pol_result['fees_op']:,.2f}")
    net_op = pol_result["op_acquired"] + pol_result["fees_op"]
    print(f"  Net OP (incl fees): {net_op:,.2f}")

    advantage = (net_op - naive_result["op_acquired"]) / naive_result["op_acquired"] * 100
    print(f"\n  POL advantage: {advantage:+.2f}%")


if __name__ == "__main__":
    main()
