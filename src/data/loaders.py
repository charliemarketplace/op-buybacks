"""
Data loaders for OP buybacks analysis.

Data inputs (to be populated):
- (a) Uni V3 OP/WETH swaps in 2025 with price and liquidity
- (b) OP/ETH OHLC data derived from swaps
- (c) Daily OP Mainnet tx fees in ETH
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_swaps() -> pd.DataFrame:
    """
    Load all Uni V3 OP/WETH swaps in 2025.

    Expected columns:
        - timestamp: datetime
        - block_number: int
        - price: float (OP per ETH)
        - amount_op: float (signed, + = buy OP, - = sell OP)
        - amount_eth: float (signed)
        - liquidity: float (active liquidity at trade tick)
        - tick: int (price tick at time of swap)
    """
    path = DATA_DIR / "swaps.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Swaps data not found at {path}. "
            "Please populate with 2025 Uni V3 OP/WETH swap data."
        )
    return pd.read_parquet(path)


def load_ohlc(freq: str = "1D") -> pd.DataFrame:
    """
    Load OP/ETH OHLC data aggregated from swaps.

    Args:
        freq: Pandas frequency string ('1D', '1H', etc.)

    Expected columns:
        - timestamp: datetime (period start)
        - open: float
        - high: float
        - low: float
        - close: float
        - volume_op: float
        - volume_eth: float
        - num_trades: int
    """
    path = DATA_DIR / f"ohlc_{freq}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"OHLC data not found at {path}. "
            "Please generate from swap data."
        )
    return pd.read_parquet(path)


def load_daily_fees() -> pd.DataFrame:
    """
    Load daily OP Mainnet transaction fees in ETH.

    Expected columns:
        - date: datetime.date
        - total_fees_eth: float
        - tx_count: int
    """
    path = DATA_DIR / "daily_fees.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Daily fees data not found at {path}. "
            "Please populate with 2025 OP Mainnet fee data."
        )
    return pd.read_parquet(path)


def generate_ohlc_from_swaps(swaps: pd.DataFrame, freq: str = "1D") -> pd.DataFrame:
    """
    Generate OHLC data from raw swap data.
    """
    df = swaps.set_index("timestamp").sort_index()

    ohlc = df["price"].resample(freq).ohlc()
    volume = df.resample(freq).agg({
        "amount_op": lambda x: x.abs().sum(),
        "amount_eth": lambda x: x.abs().sum(),
    }).rename(columns={"amount_op": "volume_op", "amount_eth": "volume_eth"})
    counts = df.resample(freq).size().rename("num_trades")

    result = pd.concat([ohlc, volume, counts], axis=1).reset_index()
    result = result.rename(columns={"timestamp": "timestamp"})

    return result
