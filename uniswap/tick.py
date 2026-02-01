"""
Tick-related conversion functions for Uniswap V3.
"""

import math
from typing import TypedDict


class ClosestTickResult(TypedDict):
    """Result from get_closest_tick function."""
    desired_price: float
    actual_price: float
    tick: int


def tick_to_price(tick: int, decimal_adjustment: float = 1.0, yx: bool = True) -> float:
    """
    Convert a Uniswap V3 tick to a human readable price.

    Accounts for differences in token decimals and whether price is desired in
    Token 1 / Token 0 (y/x) or inverted (x/y) format.

    Args:
        tick: The numeric tick, e.g., 204232.
        decimal_adjustment: The difference in the tokens decimals, e.g., 1e10 for ETH vs BTC,
            1e12 for USDC vs ETH.
        yx: Whether to return tick in Token 1 / Token 0 format or inverted.
            The USDC/ETH 0.05% pool on Ethereum mainnet at the contract level is
            ETH per USDC, but this is harder to interpret than the inverse. Default True.

    Returns:
        A numeric price in desired format.

    Examples:
        >>> # 1,351.327 USDC per ETH (yx=False because pool is actually ETH/USDC)
        >>> tick_to_price(204232, decimal_adjustment=1e12, yx=False)
        1351.327...

        >>> # 19.98232 ETH per WBTC (yx=True); 8 decimals vs 18 decimals
        >>> tick_to_price(260220, decimal_adjustment=1e10, yx=True)
        19.98232...
    """
    p = math.sqrt(1.0001) ** (2 * tick)

    if yx:
        p = p / decimal_adjustment
    else:
        p = (1.0 / p) * decimal_adjustment

    return p


def get_closest_tick(
    desired_price: float,
    tick_spacing: int = 60,
    decimal_adjustment: float = 1.0,
    yx: bool = True
) -> ClosestTickResult:
    """
    Get the closest allowable tick for a desired price.

    Depending on the Uniswap V3 Pool fee tier, only specific ticks are allowed to be
    used in positions. In 0.05% pools, the tick spacing is 10 minimum. In 0.3% pools,
    the minimum is 60 ticks.

    Args:
        desired_price: Your desired price. Note it's important to know the unit of account.
            0.05 BTC/ETH is 20 ETH/BTC.
        tick_spacing: The pool's minimum tick spacing. Default is 60 (0.3% pool).
            Use tick_spacing=1 to inverse tick_to_price.
            Generally for V3: 0.01% pools are 1, 0.05% pools are 10, 1% pools are 200.
        decimal_adjustment: The difference in the tokens decimals, e.g., 1e10 for ETH vs BTC,
            1e12 for USDC vs ETH.
        yx: Whether price is already in Token 1 / Token 0 format or inverted.
            ETH per USDC is how the ETH Mainnet 0.05% pool works but is not friendly
            for human interpretation. Default True.

    Returns:
        A dict with desired_price (input), actual_price (closest allowable), and tick.

    Examples:
        >>> # 0.05 BTC/ETH is NOT Y/X accounting for the pool, so yx=False. Result is 260220.
        >>> get_closest_tick(0.05, tick_spacing=60, decimal_adjustment=1e10, yx=False)
        {'desired_price': 0.05, 'actual_price': ..., 'tick': 260220}

        >>> # Same as above where price is inverted
        >>> get_closest_tick(20, tick_spacing=60, decimal_adjustment=1e10, yx=True)
        {'desired_price': 20, 'actual_price': ..., 'tick': 260220}
    """
    # If price is NOT Y/X formatted already, invert for tick calculation,
    # then invert prices for human readability. Results in same exact tick.
    if not yx:
        result = get_closest_tick(
            desired_price=1.0 / desired_price,
            tick_spacing=tick_spacing,
            decimal_adjustment=decimal_adjustment,
            yx=True
        )
        result["desired_price"] = 1.0 / result["desired_price"]
        result["actual_price"] = 1.0 / result["actual_price"]
        return result

    initial_tick = math.log(math.sqrt(desired_price * decimal_adjustment)) / math.log(math.sqrt(1.0001))

    if initial_tick % tick_spacing == 0:
        actual_price = desired_price
        tick = int(initial_tick)
    else:
        final_tick = round(initial_tick / tick_spacing) * tick_spacing
        tick = final_tick
        actual_price = (math.sqrt(1.0001) ** (2 * final_tick)) / decimal_adjustment

    return ClosestTickResult(
        desired_price=desired_price,
        actual_price=actual_price,
        tick=tick
    )
