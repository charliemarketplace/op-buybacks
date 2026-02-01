"""
Uniswap V3 concentrated liquidity math.

Core formulas for V3 positions:
- Liquidity L is constant within a price range [p_low, p_high]
- Real reserves: x (token0), y (token1)
- Virtual reserves follow x * y = L^2

Key relationships:
    L = x * sqrt(p) * sqrt(p_high) / (sqrt(p_high) - sqrt(p))  [when p < p_high]
    L = y / (sqrt(p) - sqrt(p_low))  [when p > p_low]

For OP/WETH pool:
    token0 = WETH (x)
    token1 = OP (y)
    price = OP per WETH
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Position:
    """A Uniswap V3 liquidity position."""
    liquidity: float
    price_low: float
    price_high: float
    amount_eth: float
    amount_op: float


def price_to_sqrt_price(price: float) -> float:
    """Convert price to sqrt(price) used in V3 math."""
    return math.sqrt(price)


def sqrt_price_to_price(sqrt_price: float) -> float:
    """Convert sqrt(price) back to price."""
    return sqrt_price ** 2


def get_amounts_for_liquidity(
    liquidity: float,
    current_price: float,
    price_low: float,
    price_high: float,
) -> Tuple[float, float]:
    """
    Calculate token amounts for a given liquidity and price range.

    Returns:
        (amount_eth, amount_op)
    """
    sqrt_p = price_to_sqrt_price(current_price)
    sqrt_p_low = price_to_sqrt_price(price_low)
    sqrt_p_high = price_to_sqrt_price(price_high)

    if current_price <= price_low:
        # Position is entirely in ETH (below range)
        amount_eth = liquidity * (1 / sqrt_p_low - 1 / sqrt_p_high)
        amount_op = 0.0
    elif current_price >= price_high:
        # Position is entirely in OP (above range)
        amount_eth = 0.0
        amount_op = liquidity * (sqrt_p_high - sqrt_p_low)
    else:
        # Position is in range, has both tokens
        amount_eth = liquidity * (1 / sqrt_p - 1 / sqrt_p_high)
        amount_op = liquidity * (sqrt_p - sqrt_p_low)

    return (amount_eth, amount_op)


def get_liquidity_for_amounts(
    amount_eth: float,
    amount_op: float,
    current_price: float,
    price_low: float,
    price_high: float,
) -> float:
    """
    Calculate liquidity for given token amounts and price range.

    Returns the minimum liquidity that can be minted from the given amounts.
    """
    sqrt_p = price_to_sqrt_price(current_price)
    sqrt_p_low = price_to_sqrt_price(price_low)
    sqrt_p_high = price_to_sqrt_price(price_high)

    if current_price <= price_low:
        # Only ETH matters
        liquidity = amount_eth / (1 / sqrt_p_low - 1 / sqrt_p_high)
    elif current_price >= price_high:
        # Only OP matters
        liquidity = amount_op / (sqrt_p_high - sqrt_p_low)
    else:
        # Both tokens matter, take minimum
        liquidity_eth = amount_eth / (1 / sqrt_p - 1 / sqrt_p_high)
        liquidity_op = amount_op / (sqrt_p - sqrt_p_low)
        liquidity = min(liquidity_eth, liquidity_op)

    return liquidity


def match_tokens_to_range(
    current_price: float,
    price_low: float,
    price_high: float,
    amount_op: Optional[float] = None,
    amount_eth: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Given current price, one token amount, and a price range,
    calculate the required amount of the other token for a balanced LP position.

    Args:
        current_price: Current OP/ETH price
        price_low: Lower bound of position range
        price_high: Upper bound of position range
        amount_op: Amount of OP (provide this OR amount_eth)
        amount_eth: Amount of ETH (provide this OR amount_op)

    Returns:
        (amount_eth, amount_op) - the full position amounts
    """
    if (amount_op is None) == (amount_eth is None):
        raise ValueError("Provide exactly one of amount_op or amount_eth")

    sqrt_p = price_to_sqrt_price(current_price)
    sqrt_p_low = price_to_sqrt_price(price_low)
    sqrt_p_high = price_to_sqrt_price(price_high)

    if current_price <= price_low:
        # Only ETH needed
        if amount_eth is not None:
            return (amount_eth, 0.0)
        else:
            raise ValueError("Position below range requires only ETH")
    elif current_price >= price_high:
        # Only OP needed
        if amount_op is not None:
            return (0.0, amount_op)
        else:
            raise ValueError("Position above range requires only OP")
    else:
        # In range: need both tokens in specific ratio
        # Ratio: amount_eth / amount_op = (1/sqrt_p - 1/sqrt_p_high) / (sqrt_p - sqrt_p_low)
        eth_factor = 1 / sqrt_p - 1 / sqrt_p_high
        op_factor = sqrt_p - sqrt_p_low
        ratio = eth_factor / op_factor  # ETH per OP

        if amount_op is not None:
            return (amount_op * ratio, amount_op)
        else:
            return (amount_eth, amount_eth / ratio)


def match_range_to_tokens(
    current_price: float,
    amount_eth: float,
    amount_op: float,
    price_low: Optional[float] = None,
    price_high: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Given token amounts, current price, and ONE price bound,
    calculate the other bound that uses all tokens exactly.

    Args:
        current_price: Current OP/ETH price
        amount_eth: Amount of ETH to deposit
        amount_op: Amount of OP to deposit
        price_low: Lower bound (provide this OR price_high)
        price_high: Upper bound (provide this OR price_low)

    Returns:
        (price_low, price_high) - the full range
    """
    if (price_low is None) == (price_high is None):
        raise ValueError("Provide exactly one of price_low or price_high")

    sqrt_p = price_to_sqrt_price(current_price)

    # From the ratio equation:
    # amount_eth / amount_op = (1/sqrt_p - 1/sqrt_p_high) / (sqrt_p - sqrt_p_low)

    if price_low is not None:
        sqrt_p_low = price_to_sqrt_price(price_low)

        if current_price <= price_low:
            raise ValueError("Current price must be above price_low")

        # Solve for sqrt_p_high:
        # R = amount_eth / amount_op
        # R * (sqrt_p - sqrt_p_low) = 1/sqrt_p - 1/sqrt_p_high
        # 1/sqrt_p_high = 1/sqrt_p - R * (sqrt_p - sqrt_p_low)
        R = amount_eth / amount_op
        inv_sqrt_p_high = 1 / sqrt_p - R * (sqrt_p - sqrt_p_low)

        if inv_sqrt_p_high <= 0:
            raise ValueError(
                "Cannot find valid price_high for these amounts. "
                "Try providing more OP or less ETH."
            )

        sqrt_p_high = 1 / inv_sqrt_p_high
        return (price_low, sqrt_price_to_price(sqrt_p_high))

    else:  # price_high is not None
        sqrt_p_high = price_to_sqrt_price(price_high)

        if current_price >= price_high:
            raise ValueError("Current price must be below price_high")

        # Solve for sqrt_p_low:
        # R = amount_eth / amount_op
        # R * (sqrt_p - sqrt_p_low) = 1/sqrt_p - 1/sqrt_p_high
        # sqrt_p_low = sqrt_p - (1/sqrt_p - 1/sqrt_p_high) / R
        R = amount_eth / amount_op
        sqrt_p_low = sqrt_p - (1 / sqrt_p - 1 / sqrt_p_high) / R

        if sqrt_p_low <= 0:
            raise ValueError(
                "Cannot find valid price_low for these amounts. "
                "Try providing more ETH or less OP."
            )

        return (sqrt_price_to_price(sqrt_p_low), price_high)


def create_position(
    current_price: float,
    price_low: float,
    price_high: float,
    amount_eth: float,
    amount_op: float,
) -> Position:
    """
    Create a V3 position from the given parameters.

    Note: May not use all of both tokens - uses maximum possible liquidity.
    """
    liquidity = get_liquidity_for_amounts(
        amount_eth, amount_op, current_price, price_low, price_high
    )
    actual_eth, actual_op = get_amounts_for_liquidity(
        liquidity, current_price, price_low, price_high
    )

    return Position(
        liquidity=liquidity,
        price_low=price_low,
        price_high=price_high,
        amount_eth=actual_eth,
        amount_op=actual_op,
    )


def simulate_swap_in_position(
    position: Position,
    current_price: float,
    amount_eth_in: Optional[float] = None,
    amount_op_in: Optional[float] = None,
) -> Tuple[float, float, float]:
    """
    Simulate a swap against a single position.

    Returns:
        (amount_out, new_price, price_impact)
    """
    # Simplified: assumes swap stays within position range
    # Full implementation would handle crossing tick boundaries

    if (amount_eth_in is None) == (amount_op_in is None):
        raise ValueError("Provide exactly one of amount_eth_in or amount_op_in")

    sqrt_p = price_to_sqrt_price(current_price)
    L = position.liquidity

    if amount_eth_in is not None:
        # Swapping ETH for OP (buying OP)
        # delta_sqrt_p = delta_x * sqrt_p^2 / L
        # Simplified: new_sqrt_p = L / (L/sqrt_p + amount_eth_in)
        new_sqrt_p = L / (L / sqrt_p + amount_eth_in)
        new_price = sqrt_price_to_price(new_sqrt_p)
        amount_op_out = L * (sqrt_p - new_sqrt_p)
        price_impact = (current_price - new_price) / current_price
        return (amount_op_out, new_price, price_impact)
    else:
        # Swapping OP for ETH (selling OP)
        new_sqrt_p = sqrt_p + amount_op_in / L
        new_price = sqrt_price_to_price(new_sqrt_p)
        amount_eth_out = L * (1 / sqrt_p - 1 / new_sqrt_p)
        price_impact = (new_price - current_price) / current_price
        return (amount_eth_out, new_price, price_impact)
