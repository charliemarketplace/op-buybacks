"""
01_processing.py

Processes raw swap data from OP/WETH 0.3% pool to create hourly aggregated data:
- OHLC prices (OP per ETH)
- Buy/sell volumes for each token
- LP fees earned (0.3% of sold token amounts)

Input: data/opweth03-swaps-jan2026.csv
Output: data/hourly_ohlcv.csv
"""

import sys
from pathlib import Path

# Add parent directory to path for uniswap package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from uniswap import sqrtpx96_to_price


def load_swaps(filepath: str) -> pd.DataFrame:
    """Load and parse swap data."""
    df = pd.read_csv(filepath)

    # Parse timestamp
    df["BLOCK_TIMESTAMP"] = pd.to_datetime(df["BLOCK_TIMESTAMP"])

    # Extract hour bucket
    df["HOUR_"] = df["BLOCK_TIMESTAMP"].dt.floor("h")

    return df


def calculate_price(sqrtpx96: str) -> float:
    """
    Convert sqrtPriceX96 to OP/ETH price.

    In this pool:
    - token0 = WETH (18 decimals)
    - token1 = OP (18 decimals)
    - decimal_adjustment = 1 (same decimals)
    - sqrtpx96_to_price returns token1/token0 = OP/ETH
    """
    return sqrtpx96_to_price(sqrtpx96, invert=False, decimal_adjustment=1.0)


def process_swaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process swaps to calculate prices and categorize buy/sell amounts.

    Amount conventions:
    - Positive = token received by pool (user sells to pool)
    - Negative = token sent by pool (user buys from pool)
    - AMOUNT0_RAW = ETH
    - AMOUNT1_RAW = OP
    """
    # Calculate OP/ETH price for each swap
    df["price_op_per_eth"] = df["SQRTPRICEX96"].apply(calculate_price)

    # Convert raw amounts to human readable (18 decimals for both)
    df["eth_amount"] = df["AMOUNT0_RAW"] / 1e18
    df["op_amount"] = df["AMOUNT1_RAW"] / 1e18

    # Categorize buys and sells
    # OP bought by users = negative OP amounts (sent by pool)
    # OP sold by users = positive OP amounts (received by pool)
    df["op_bought"] = df["op_amount"].apply(lambda x: abs(x) if x < 0 else 0)
    df["op_sold"] = df["op_amount"].apply(lambda x: x if x > 0 else 0)

    # ETH bought by users = negative ETH amounts (sent by pool)
    # ETH sold by users = positive ETH amounts (received by pool)
    df["eth_bought"] = df["eth_amount"].apply(lambda x: abs(x) if x < 0 else 0)
    df["eth_sold"] = df["eth_amount"].apply(lambda x: x if x > 0 else 0)

    # Calculate fees (0.3% of sold amounts)
    # Fees are paid in the token being sold to the pool
    df["op_fees"] = df["op_sold"] * 0.003
    df["eth_fees"] = df["eth_sold"] * 0.003

    return df


def aggregate_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate swap data to hourly OHLCV.

    Output columns:
    - HOUR_: hourly timestamp
    - open, low, high, close: OP/ETH prices
    - vwap: volume-weighted average price within the hour
    - op_bought, op_sold: OP volumes
    - eth_bought, eth_sold: ETH volumes
    - op_fees, eth_fees: LP fees earned
    """
    # Sort by timestamp for proper OHLC calculation
    df = df.sort_values("BLOCK_TIMESTAMP").copy()

    # Calculate ETH volume (absolute value) and price*volume for VWAP
    df["eth_volume"] = df["eth_amount"].abs()
    df["price_x_volume"] = df["price_op_per_eth"] * df["eth_volume"]

    # OHLC aggregation
    ohlc = df.groupby("HOUR_").agg(
        open=("price_op_per_eth", "first"),
        high=("price_op_per_eth", "max"),
        low=("price_op_per_eth", "min"),
        close=("price_op_per_eth", "last"),
    )

    # Volume aggregation including VWAP components
    volumes = df.groupby("HOUR_").agg(
        op_bought=("op_bought", "sum"),
        op_sold=("op_sold", "sum"),
        eth_bought=("eth_bought", "sum"),
        eth_sold=("eth_sold", "sum"),
        op_fees=("op_fees", "sum"),
        eth_fees=("eth_fees", "sum"),
        trade_count=("TX_HASH", "count"),
        sum_price_x_volume=("price_x_volume", "sum"),
        sum_eth_volume=("eth_volume", "sum"),
    )

    # Calculate within-hour VWAP: Σ(price × |eth_volume|) / Σ(|eth_volume|)
    volumes["vwap"] = volumes["sum_price_x_volume"] / volumes["sum_eth_volume"]

    # Drop intermediate columns
    volumes = volumes.drop(columns=["sum_price_x_volume", "sum_eth_volume"])

    # Combine
    hourly = ohlc.join(volumes).reset_index()

    return hourly


def main():
    """Main processing pipeline."""
    # Paths
    project_root = Path(__file__).parent.parent
    input_path = project_root / "data" / "opweth03-swaps-jan2026.csv"
    output_path = project_root / "data" / "hourly_ohlcv.csv"

    print(f"Loading swaps from {input_path}...")
    df = load_swaps(input_path)
    print(f"  Loaded {len(df):,} swaps")

    print("Processing swaps...")
    df = process_swaps(df)

    print("Aggregating to hourly...")
    hourly = aggregate_hourly(df)

    # Save output
    print(f"Saving to {output_path}...")
    hourly.to_csv(output_path, index=False)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Date range: {hourly['HOUR_'].min()} to {hourly['HOUR_'].max()}")
    print(f"Hours: {len(hourly)}")
    print(f"Total trades: {hourly['trade_count'].sum():,}")
    print(f"\nPrice range (OP/ETH):")
    print(f"  Low:  {hourly['low'].min():.2f}")
    print(f"  High: {hourly['high'].max():.2f}")
    print(f"\nTotal volumes:")
    print(f"  OP bought:  {hourly['op_bought'].sum():,.2f}")
    print(f"  OP sold:    {hourly['op_sold'].sum():,.2f}")
    print(f"  ETH bought: {hourly['eth_bought'].sum():,.2f}")
    print(f"  ETH sold:   {hourly['eth_sold'].sum():,.2f}")
    print(f"\nTotal LP fees earned:")
    print(f"  OP fees:  {hourly['op_fees'].sum():,.2f}")
    print(f"  ETH fees: {hourly['eth_fees'].sum():,.2f}")

    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()
