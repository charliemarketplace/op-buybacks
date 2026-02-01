"""
Fee calculation functions for Uniswap V3.
"""

from typing import TypedDict, Union
import pandas as pd


class FeesResult(TypedDict):
    """Result from calc_fees_from_trades function."""
    amount0_fees: float
    amount1_fees: float


def calc_fees_from_trades(
    position_l: Union[int, str],
    tick_lower: int,
    tick_upper: int,
    trades: pd.DataFrame,
    fee: float = 0.003
) -> FeesResult:
    """
    Calculate fee rewards from trades occurring within a position's range.

    Given a position's marginal liquidity and range (tick_lower, tick_upper),
    calculate the fee rewards from trades occurring in a set of blocks.

    Args:
        position_l: The marginal liquidity provided by a position.
        tick_lower: The low tick in a liquidity position.
        tick_upper: The upper tick in a liquidity position.
        trades: Trades table with columns: tick, amount0_adjusted, amount1_adjusted, liquidity.
            Negative values = tokens bought, Positive values = tokens sold by user to pool.
        fee: The pool fee, default 0.3% (0.003). Generally one of: 0.0001, 0.0005, 0.003, 0.01

    Returns:
        A dict with amount0_fees (in x units, e.g., WBTC) and amount1_fees (in y units, e.g., WETH).

    Examples:
        >>> # Calculate fees from 1,000 blocks of trades between 16M to 16,001,000
        >>> import pandas as pd
        >>> trades = pd.DataFrame({
        ...     'tick': [256450, 256460],
        ...     'amount0_adjusted': [0.1, -0.05],
        ...     'amount1_adjusted': [-1.5, 0.8],
        ...     'liquidity': [1000000000000000, 1000000000000000]
        ... })
        >>> calc_fees_from_trades(
        ...     position_l='1429022391989675',
        ...     tick_lower=256400, tick_upper=256520,
        ...     trades=trades, fee=0.003
        ... )
        # Returns fees in token 0 and token 1 units
    """
    position_l = int(position_l)

    # Filter to relevant trades within the tick range
    relevant_trades = trades[
        (trades["tick"] >= tick_lower) & (trades["tick"] <= tick_upper)
    ].copy()

    if len(relevant_trades) == 0:
        return FeesResult(amount0_fees=0.0, amount1_fees=0.0)

    # Calculate liquidity fraction for each trade
    relevant_trades["liquidity_fraction"] = position_l / (
        relevant_trades["liquidity"].astype(float) + position_l
    )

    # Calculate fees from positive amounts (tokens sold to pool by traders)
    positive_amount0 = relevant_trades[relevant_trades["amount0_adjusted"] > 0]
    amount0_fees = (
        (positive_amount0["amount0_adjusted"] * positive_amount0["liquidity_fraction"]).sum()
        * fee
    )

    positive_amount1 = relevant_trades[relevant_trades["amount1_adjusted"] > 0]
    amount1_fees = (
        (positive_amount1["amount1_adjusted"] * positive_amount1["liquidity_fraction"]).sum()
        * fee
    )

    return FeesResult(
        amount0_fees=float(amount0_fees),
        amount1_fees=float(amount1_fees)
    )
