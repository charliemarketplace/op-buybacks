"""
Utility functions for Uniswap V3 calculations.
"""

import math
from typing import Optional, TypedDict, Union
import pandas as pd

from .tick import tick_to_price, get_closest_tick
from .price import sqrtpx96_to_price


class MatchTokensResult(TypedDict):
    """Result from match_tokens_to_range function."""
    amount_x: Optional[float]
    amount_y: Optional[float]
    sqrtpx96: int
    P: float
    tick_lower: int
    tick_upper: int
    price_lower: float
    price_upper: float


class PriceAllTokensResult(TypedDict):
    """Result from price_all_tokens function."""
    amount_x: float
    amount_y: float
    sqrtpx96: int
    P: float
    tick_lower: Optional[int]
    tick_upper: Optional[int]
    price_lower: Optional[float]
    price_upper: Optional[float]


def find_recalculation_price(
    ptbl: pd.DataFrame,
    p: float,
    price_up: bool = True,
    decimal_adjustment: float = 1.0,
    yx: bool = True
) -> float:
    """
    Find the next tick where liquidity must be recalculated.

    Identifies the next price where at least one position enters or exits being active.

    Args:
        ptbl: Liquidity positions table with columns tick_lower, tick_upper, liquidity.
        p: Current price in human readable format.
        price_up: Is the price rising (True) or falling (False). Default True.
        decimal_adjustment: The difference in the tokens decimals, e.g., 1e10 for ETH vs BTC.
        yx: Whether price is already in Token 1 / Token 0 format or inverted. Default True.

    Returns:
        Human readable price in the format provided (Y/X or X/Y).

    Examples:
        >>> import pandas as pd
        >>> ptbl = pd.DataFrame({
        ...     'tick_lower': [92100, 256000],
        ...     'tick_upper': [267180, 267500],
        ...     'liquidity': [1000000, 2000000]
        ... })
        >>> # At 39.36252 ETH/BTC, find next higher price for recalculation
        >>> find_recalculation_price(ptbl, p=39.36252, price_up=True,
        ...                          decimal_adjustment=1e10, yx=True)
        40.07743  # Position 92100-267180 falls out of range
    """
    if "tick_lower" not in ptbl.columns or "tick_upper" not in ptbl.columns:
        raise ValueError("Expected tick_lower and tick_upper columns")

    # For making positions, tick_spacing=1 is only valid for 0.01% pools,
    # but this works for inside a valid range
    tick_target = get_closest_tick(p, tick_spacing=1, decimal_adjustment=decimal_adjustment, yx=yx)
    target_tick = tick_target["tick"]

    relevant_ticks = sorted(set(ptbl["tick_lower"].tolist() + ptbl["tick_upper"].tolist()))

    # If price going up, get the closest price above current price where liquidity changes
    # If price going down, get the closest price below current price where liquidity changes
    if price_up and yx:
        ticks_above = [t for t in relevant_ticks if t > target_tick]
        if not ticks_above:
            raise ValueError("No ticks above current price")
        closest_tick = ticks_above[0]
    elif not price_up and yx:
        ticks_below = [t for t in relevant_ticks if t < target_tick]
        if not ticks_below:
            raise ValueError("No ticks below current price")
        closest_tick = ticks_below[-1]
    else:
        # If yx is False, invert everything, re-calculate, and invert the result
        result = find_recalculation_price(
            ptbl, 1.0 / p, not price_up, decimal_adjustment, not yx
        )
        return 1.0 / result

    closest_price = tick_to_price(closest_tick, decimal_adjustment=decimal_adjustment, yx=yx)
    return closest_price


def match_tokens_to_range(
    x: Optional[float],
    y: Optional[float],
    sqrtpx96: Union[int, str],
    decimal_x: float = 1e18,
    decimal_y: float = 1e18,
    tick_lower: int = 0,
    tick_upper: int = 0
) -> MatchTokensResult:
    """
    Given one token amount and a price range, calculate how much of the other token is needed.

    Given current price, a price range, and an amount of one token, identify how much
    of the other token is required to create the Uniswap V3 position.

    Args:
        x: Number of token 0. Should be None if y is provided.
        y: Number of token 1. Should be None if x is provided.
        sqrtpx96: Current price in uint160 format.
        decimal_x: The decimals used in token 0, e.g., 1e6 for USDC, 1e8 for WBTC.
        decimal_y: The decimals used in token 1, e.g., 1e18 for WETH.
        tick_lower: The low tick in a liquidity position.
        tick_upper: The upper tick in a liquidity position.

    Returns:
        A dict with amount_x, amount_y, sqrtpx96, P, tick_lower, tick_upper,
        price_lower, price_upper. The unknown token amount (x or y) is calculated.

    Examples:
        >>> # Match 1 BTC to ETH in range 257760-258900 at price 16.52921 ETH/BTC
        >>> match_tokens_to_range(
        ...     x=1, y=None,
        ...     sqrtpx96='32211102662183904786754519772954624',
        ...     decimal_x=1e8, decimal_y=1e18,
        ...     tick_lower=257760, tick_upper=258900
        ... )
        # Returns amount_y = 16.117809469 ETH
    """
    if x is None and y is None:
        raise ValueError("Amount of token x OR amount of token y must be provided")

    if x is not None and y is not None:
        raise ValueError("One of amount x or amount y should be unknown (None)")

    sqrtpx96_int = int(sqrtpx96)
    decimal_adjustment = max(decimal_y / decimal_x, decimal_x / decimal_y)

    P = sqrtpx96_to_price(sqrtpx96_int, decimal_adjustment=decimal_adjustment)
    price_lower = tick_to_price(tick=tick_lower, decimal_adjustment=decimal_adjustment)
    price_upper = tick_to_price(tick=tick_upper, decimal_adjustment=decimal_adjustment)

    result: MatchTokensResult = {
        "amount_x": x,
        "amount_y": y,
        "sqrtpx96": sqrtpx96_int,
        "P": P,
        "tick_lower": tick_lower,
        "tick_upper": tick_upper,
        "price_lower": price_lower,
        "price_upper": price_upper
    }

    # If x is provided, calculate y
    if x is not None:
        # Use inverse of prices with the formula
        sqrt_pl_inv = math.sqrt(1.0 / price_lower)
        sqrt_p_inv = math.sqrt(1.0 / P)
        sqrt_pu_inv = math.sqrt(1.0 / price_upper)

        numerator = sqrt_pl_inv - sqrt_p_inv
        denominator = (sqrt_p_inv * sqrt_pl_inv) * (sqrt_p_inv - sqrt_pu_inv)

        result["amount_y"] = x * numerator / denominator

    # If y is provided, calculate x
    if y is not None:
        sqrt_pl_inv = math.sqrt(1.0 / price_lower)
        sqrt_p_inv = math.sqrt(1.0 / P)
        sqrt_pu_inv = math.sqrt(1.0 / price_upper)

        result["amount_x"] = (
            y * sqrt_p_inv * sqrt_pl_inv /
            (sqrt_pl_inv - sqrt_p_inv) *
            (sqrt_p_inv - sqrt_pu_inv)
        )

    return result


def price_all_tokens(
    x: float,
    y: float,
    sqrtpx96: Union[int, str],
    decimal_x: float = 1e18,
    decimal_y: float = 1e18,
    tick_lower: Optional[int] = None,
    tick_upper: Optional[int] = None
) -> PriceAllTokensResult:
    """
    Given both token amounts and one tick boundary, find the other tick boundary.

    Given an amount of tokens, a current price, and either the min or max price
    of a range, identify the corresponding max or min price for the Uniswap V3
    position to use all tokens x and y.

    Note: Not all pools allow all prices. See get_closest_tick for more info.

    Args:
        x: Number of token 0, e.g., WBTC.
        y: Number of token 1, e.g., ETH.
        sqrtpx96: Current price in uint160 format.
        decimal_x: The decimals used in token 0.
        decimal_y: The decimals used in token 1.
        tick_lower: The low tick. None if tick_upper is provided.
        tick_upper: The upper tick. None if tick_lower is provided.

    Returns:
        A dict with amount_x, amount_y, sqrtpx96, P, tick_lower, tick_upper,
        price_lower, price_upper. The unknown tick is calculated.

    Examples:
        >>> # Find tick_lower given x=1, y=16.11781, and tick_upper=258900
        >>> price_all_tokens(
        ...     x=1, y=16.11781,
        ...     sqrtpx96='32211102662183904786754519772954624',
        ...     decimal_x=1e8, decimal_y=1e18,
        ...     tick_lower=None, tick_upper=258900
        ... )
        # Returns tick_lower = 257760
    """
    if x is None or y is None:
        raise ValueError("Both amount of token x and amount of token y must be provided")

    if tick_lower is not None and tick_upper is not None:
        raise ValueError("One of tick_lower or tick_upper should be unknown (None)")

    if tick_lower is None and tick_upper is None:
        raise ValueError("One of tick_lower or tick_upper must be provided")

    sqrtpx96_int = int(sqrtpx96)
    decimal_adjustment = max(decimal_y / decimal_x, decimal_x / decimal_y)

    P = sqrtpx96_to_price(sqrtpx96_int, decimal_adjustment=decimal_adjustment)

    result: PriceAllTokensResult = {
        "amount_x": x,
        "amount_y": y,
        "sqrtpx96": sqrtpx96_int,
        "P": P,
        "tick_lower": tick_lower,
        "tick_upper": tick_upper,
        "price_lower": None,
        "price_upper": None
    }

    # If tick_lower is given, calculate tick_upper
    if tick_lower is not None:
        price_lower = tick_to_price(tick=tick_lower, decimal_adjustment=decimal_adjustment)
        result["price_lower"] = price_lower

        f1 = (y ** 2) / (x ** 2)
        f2 = math.sqrt(price_lower) - math.sqrt(P) + (y / (math.sqrt(P) * x))
        pb = f1 * (f2 ** -2)

        result["price_upper"] = pb
        result["tick_upper"] = get_closest_tick(pb, tick_spacing=1, decimal_adjustment=decimal_adjustment)["tick"]

    # If tick_lower is NOT given, calculate it from tick_upper
    else:
        price_upper = tick_to_price(tick=tick_upper, decimal_adjustment=decimal_adjustment)
        result["price_upper"] = price_upper

        f1 = y / (math.sqrt(price_upper) * x)
        f2 = y / (math.sqrt(P) * x)
        pa = (f1 + math.sqrt(P) - f2) ** 2

        result["price_lower"] = pa
        result["tick_lower"] = get_closest_tick(pa, tick_spacing=1, decimal_adjustment=decimal_adjustment)["tick"]

    return result
