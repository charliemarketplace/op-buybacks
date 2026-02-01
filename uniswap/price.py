"""
Price conversion functions for Uniswap V3 sqrtPriceX96 format.

Uniswap stores prices as square roots in 64.96 fixed-point format
(64 bits integer, 96 bits fractional).
"""

import math
from typing import Union


def price_to_sqrtpx96(
    p: float,
    invert: bool = False,
    decimal_adjustment: float = 1.0
) -> int:
    """
    Convert a human-readable price to Uniswap's sqrtPriceX96 format.

    Args:
        p: Price in human readable form (e.g., 0.05 BTC/ETH).
        invert: Whether to invert the price. Uniswap uses Token 1 / Token 0.
            You must know which token is which at the pool level. Default False.
        decimal_adjustment: 10^(decimal difference). WBTC has 8 decimals,
            ETH has 18, so it'd be 1e10.

    Returns:
        Big integer price in sqrtPriceX96 format.

    Note:
        Small amount of precision loss (<0.001%) possible due to not adjusting for
        Solidity implementation of Chinese Remainder Theorem as Solidity uses
        fixed-point math.

    Examples:
        >>> # For Ethereum Mainnet ETH-USDC 0.05% V3 Pool:
        >>> # $1,825.732 USDC/ETH -> 1854219362252931989533640458424264 (Slot0)
        >>> # invert=True because pool is actually ETH/USDC (Token 1 / Token 0)
        >>> # USDC is 6 decimals while ETH is 18 decimals (18-6 = 12)
        >>> price_to_sqrtpx96(1825.732, invert=True, decimal_adjustment=1e12)
        1854219183615346559398951258161152  # 99.99999% accurate
    """
    if invert:
        p = 1.0 / p

    # sqrt(P * decimal_adjustment) * 2^96
    sqrt_price = math.sqrt(p * decimal_adjustment)
    return int(sqrt_price * (2 ** 96))


def sqrtpx96_to_price(
    sqrtpx96: Union[int, str],
    invert: bool = False,
    decimal_adjustment: float = 1.0
) -> float:
    """
    Convert Uniswap's sqrtPriceX96 format to a human-readable price.

    Args:
        sqrtpx96: The Uniswap 64.96 square root price to convert.
        invert: Whether to invert the result. Uniswap uses Token 1 / Token 0.
            You must know which token is which at the pool level. Default False.
        decimal_adjustment: 10^(decimal difference). WBTC has 8 decimals,
            ETH has 18, so it'd be 1e10.

    Returns:
        Human readable decimal price in desired format (1/0 or 0/1 if invert=True).

    Note:
        Small amount of precision loss (<0.01%) possible due to not adjusting for
        Solidity implementation of Chinese Remainder Theorem as Solidity uses
        fixed-point math.

    Examples:
        >>> # For Ethereum Mainnet ETH-USDC 0.05% V3 Pool:
        >>> # 1854219362252931989533640458424264 (Slot0) -> $1,825.732 USDC/ETH
        >>> # invert=True because pool is actually ETH/USDC (Token 1 / Token 0)
        >>> sqrtpx96_to_price('1854219362252931989533640458424264', invert=True, decimal_adjustment=1e12)
        1825.732...  # 99.99999% accurate
    """
    sqrtpx96 = int(sqrtpx96)
    p = sqrtpx96 / (2 ** 96)

    if invert:
        return (1.0 / (p ** 2)) * decimal_adjustment
    else:
        return (p ** 2) / decimal_adjustment
