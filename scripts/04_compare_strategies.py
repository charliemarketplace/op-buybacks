"""
04_compare_strategies.py

Compare Monte Carlo random buys vs Simple Wide LP strategies.

Metrics:
- Total OP accumulated (or OP equivalent)
- Average cost basis
- Risk/variance
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def main():
    project_root = Path(__file__).parent.parent

    # Load results
    mc_results = pd.read_csv(project_root / "data" / "monte_carlo_results.csv")
    lp_results = pd.read_csv(project_root / "data" / "lp_daily_results.csv")
    fees = pd.read_csv(project_root / "data" / "op-mainnet-daily-fees-jan2026.csv")

    # Get final price from LP results (approximate)
    # Last day's price based on OP/ETH deposited ratio
    final_price = 10464  # From LP simulation output

    print("=" * 70)
    print("STRATEGY COMPARISON: January 2026")
    print("=" * 70)

    # Total budget
    total_fees = fees["fees_eth"].sum()
    # First day's fees not used (no T-1), so actual budget is sum minus first day
    actual_budget = fees["fees_eth"].iloc[1:].sum()

    print(f"\nBudget:")
    print(f"  Total tx fees collected: {total_fees:.4f} ETH")
    print(f"  Fees available for strategies (T-1 rule): {actual_budget:.4f} ETH")

    print("\n" + "-" * 70)
    print("STRATEGY 1: Monte Carlo Random Buys")
    print("-" * 70)

    print(f"\n  Simulations run: {len(mc_results)}")
    print(f"\n  OP Accumulated:")
    print(f"    Mean:   {mc_results['total_op_bought'].mean():>12,.2f} OP")
    print(f"    Median: {mc_results['total_op_bought'].median():>12,.2f} OP")
    print(f"    Std:    {mc_results['total_op_bought'].std():>12,.2f} OP")
    print(f"    Min:    {mc_results['total_op_bought'].min():>12,.2f} OP")
    print(f"    Max:    {mc_results['total_op_bought'].max():>12,.2f} OP")

    mc_avg_price = mc_results['avg_price'].mean()
    print(f"\n  Average Execution Price: {mc_avg_price:,.2f} OP/ETH")

    print("\n" + "-" * 70)
    print("STRATEGY 2: Simple Wide LP")
    print("-" * 70)

    lp_eth_deposited = lp_results["eth_deposited"].sum()
    lp_op_deposited = lp_results["op_deposited"].sum()
    lp_fees_eth = lp_results["fees_earned_eth"].sum()
    lp_fees_op = lp_results["fees_earned_op"].sum()

    print(f"\n  Deposits:")
    print(f"    ETH deposited: {lp_eth_deposited:>12.4f} ETH")
    print(f"    OP deposited:  {lp_op_deposited:>12,.2f} OP")

    print(f"\n  Fees Earned:")
    print(f"    ETH fees:      {lp_fees_eth:>12.6f} ETH")
    print(f"    OP fees:       {lp_fees_op:>12,.2f} OP")

    # Estimate position value (simplified - actual would use get_position_balance)
    # From LP simulation: 5.2335 ETH + 94,871.22 OP at end
    lp_final_eth = 5.2335
    lp_final_op = 94871.22

    print(f"\n  Final Position Value:")
    print(f"    ETH in position: {lp_final_eth:>10.4f} ETH")
    print(f"    OP in position:  {lp_final_op:>10,.2f} OP")

    # Total OP equivalent
    lp_total_op_equiv = (
        lp_final_op +
        lp_fees_op +
        (lp_final_eth + lp_fees_eth) * final_price
    )

    print(f"\n  Total OP Equivalent (at {final_price:,} OP/ETH):")
    print(f"    Position OP:     {lp_final_op:>12,.2f}")
    print(f"    Fee OP:          {lp_fees_op:>12,.2f}")
    print(f"    Position ETH:    {lp_final_eth * final_price:>12,.2f} (as OP)")
    print(f"    Fee ETH:         {lp_fees_eth * final_price:>12,.2f} (as OP)")
    print(f"    ─────────────────────────────")
    print(f"    TOTAL:           {lp_total_op_equiv:>12,.2f} OP equiv")

    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)

    mc_mean = mc_results['total_op_bought'].mean()

    print(f"\n  {'Strategy':<25} {'OP Equivalent':>15} {'vs MC':>12}")
    print(f"  {'-'*25} {'-'*15} {'-'*12}")
    print(f"  {'Monte Carlo (mean)':<25} {mc_mean:>15,.2f} {'baseline':>12}")
    print(f"  {'Simple Wide LP':<25} {lp_total_op_equiv:>15,.2f} {(lp_total_op_equiv/mc_mean - 1)*100:>+11.1f}%")

    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)

    if lp_total_op_equiv > mc_mean:
        winner = "LP"
        diff = lp_total_op_equiv - mc_mean
    else:
        winner = "Monte Carlo"
        diff = mc_mean - lp_total_op_equiv

    print(f"""
  Winner: {winner} by {diff:,.0f} OP ({abs(lp_total_op_equiv/mc_mean - 1)*100:.1f}%)

  Monte Carlo:
    + Simple to execute
    + 100% exposure to OP price appreciation
    + Low variance (~0.1% std dev across simulations)
    - No fee income
    - Subject to timing within price range

  Simple Wide LP:
    + Earns trading fees ({lp_fees_op:,.0f} OP + {lp_fees_eth:.4f} ETH)
    + Maintains ETH exposure (diversification)
    - Impermanent loss when price moves
    - More complex to manage
    - Lower OP accumulation in trending market

  Note: This is a {len(lp_results)}-day simulation. LP advantages may
  compound more favorably over longer periods with higher volume.
""")


if __name__ == "__main__":
    main()
