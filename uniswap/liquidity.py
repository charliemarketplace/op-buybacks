"""
Liquidity calculation functions for Uniswap V3.
"""

from typing import TypedDict, Union
import pandas as pd

from .tick import tick_to_price, get_closest_tick
from .price import price_to_sqrtpx96


class PositionBalance(TypedDict):
    """Result from get_position_balance function."""
    token0: float
    token1: float


def get_liquidity(
    x: float,
    y: float,
    sqrtpx96: Union[int, str],
    decimal_x: float = 1e18,
    decimal_y: float = 1e18,
    tick_lower: int = 0,
    tick_upper: int = 0
) -> int:
    """
    Calculate the liquidity provided by a range using its amount of tokens.

    Args:
        x: Number of token 0, e.g., WBTC in ETH-WBTC 0.3% pool on ETH Mainnet.
        y: Number of token 1, e.g., ETH in ETH-WBTC 0.3% pool on ETH Mainnet.
        sqrtpx96: Current price in uint160 format. See price_to_sqrtpx96 or read
            a pool contract's sqrtPriceX96 within its slot0 on etherscan.
        decimal_x: The decimals used in token 0, e.g., 1e6 for USDC, 1e8 for WBTC.
        decimal_y: The decimals used in token 1, e.g., 1e18 for WETH.
        tick_lower: The low tick in a liquidity position.
        tick_upper: The upper tick in a liquidity position.

    Returns:
        A big integer value representing the liquidity contributed by the position.

    Examples:
        >>> # See: https://etherscan.io/tx/0xc10cddba3df56e6fba4f9a88b132cc9d4440ff31bb0c4926dc9d9ca652faf376
        >>> # In Block 12,376,757: 1 BTC and 16.117809469 ETH were added to pool
        >>> # with range 257760 to 258900
        >>> # Price: 16.52921 ETH/BTC (sqrtpx96 = 32211102662183904786754519772954624)
        >>> # Result: NFT Position 1005 with liquidity 1429022393248418
        >>> get_liquidity(
        ...     x=1, y=16.117809469,
        ...     sqrtpx96='32211102662183904786754519772954624',
        ...     decimal_x=1e8, decimal_y=1e18,
        ...     tick_lower=257760, tick_upper=258900
        ... )
        1429022393248418  # Within 0.0001%
    """
    sqrtpx96 = int(sqrtpx96)
    decimal_adjustment = max(decimal_y / decimal_x, decimal_x / decimal_y)

    mintickx96 = price_to_sqrtpx96(
        p=tick_to_price(tick=tick_lower, decimal_adjustment=decimal_adjustment),
        decimal_adjustment=decimal_adjustment
    )
    maxtickx96 = price_to_sqrtpx96(
        p=tick_to_price(tick=tick_upper, decimal_adjustment=decimal_adjustment),
        decimal_adjustment=decimal_adjustment
    )

    if mintickx96 == maxtickx96:
        return 0

    def get_liq_amount0(mintickx96: int, maxtickx96: int, amount0: float) -> int:
        if mintickx96 > maxtickx96:
            mintickx96, maxtickx96 = maxtickx96, mintickx96
        intermediate = (mintickx96 * maxtickx96) // (2 ** 96)
        return int(amount0 * intermediate // (maxtickx96 - mintickx96))

    def get_liq_amount1(mintickx96: int, maxtickx96: int, amount1: float) -> int:
        if mintickx96 > maxtickx96:
            mintickx96, maxtickx96 = maxtickx96, mintickx96
        return int(amount1 * (2 ** 96) // (maxtickx96 - mintickx96))

    def get_liq(
        current_pricex96: int,
        mintickx96: int,
        maxtickx96: int,
        amount0: float,
        amount1: float
    ) -> int:
        if mintickx96 > maxtickx96:
            mintickx96, maxtickx96 = maxtickx96, mintickx96

        if current_pricex96 <= mintickx96:
            return get_liq_amount0(mintickx96, maxtickx96, amount0)
        elif current_pricex96 < maxtickx96:
            liq0 = get_liq_amount0(current_pricex96, maxtickx96, amount0)
            liq1 = get_liq_amount1(mintickx96, current_pricex96, amount1)
            return min(liq0, liq1)
        else:
            return get_liq_amount1(mintickx96, maxtickx96, amount1)

    return get_liq(
        current_pricex96=sqrtpx96,
        mintickx96=mintickx96,
        maxtickx96=maxtickx96,
        amount0=x * decimal_x,
        amount1=y * decimal_y
    )


def get_position_balance(
    position_l: Union[int, str],
    sqrtpx96: Union[int, str],
    tick_lower: int,
    tick_upper: int,
    decimal_x: float = 1e18,
    decimal_y: float = 1e18
) -> PositionBalance:
    """
    Get the balance of assets in a position given its liquidity and current price.

    Args:
        position_l: The marginal liquidity provided by a position.
        sqrtpx96: Current price in uint160 format.
        tick_lower: The low tick in a liquidity position.
        tick_upper: The upper tick in a liquidity position.
        decimal_x: The decimals used in token 0, e.g., 1e6 for USDC, 1e8 for WBTC.
        decimal_y: The decimals used in token 1, e.g., 1e18 for WETH.

    Returns:
        A dict with token0 (x) balance and token1 (y) balance adjusted for decimals.

    Examples:
        >>> # MKR/LINK position on Optimism in range 0.00667 - 0.02 MKR/LINK
        >>> # Liquidity 343255264548669212, price 0.00928 MKR/LINK
        >>> # Expected: 1.136317 LINK and 0.005027558 MKR
        >>> get_position_balance(
        ...     position_l='343255264548669212',
        ...     sqrtpx96='7632249339194475209177795127',
        ...     tick_lower=-50100, tick_upper=-39120,
        ...     decimal_x=1e18, decimal_y=1e18
        ... )
        {'token0': 1.136317, 'token1': 0.005027558}
    """
    # Import here to avoid circular dependency
    from .swap import size_price_change_in_tick

    position_l = int(position_l)
    sqrtpx96 = int(sqrtpx96)
    decimal_adjustment = max(decimal_y / decimal_x, decimal_x / decimal_y)

    price_lower = price_to_sqrtpx96(
        p=tick_to_price(tick_lower, decimal_adjustment=decimal_adjustment),
        decimal_adjustment=decimal_adjustment
    )
    price_upper = price_to_sqrtpx96(
        p=tick_to_price(tick_upper, decimal_adjustment=decimal_adjustment),
        decimal_adjustment=decimal_adjustment
    )

    # If price is above range, you're all token 1
    if sqrtpx96 >= price_upper:
        token0 = 0.0
        token1 = size_price_change_in_tick(
            l=position_l,
            sqrtpx96=price_lower,
            sqrtpx96_target=price_upper,
            dx=False,
            decimal_scale=decimal_y,
            fee=0
        )

    # If price is below range, you're all token 0
    elif sqrtpx96 <= price_lower:
        token0 = size_price_change_in_tick(
            l=position_l,
            sqrtpx96=price_upper,
            sqrtpx96_target=price_lower,
            dx=True,
            decimal_scale=decimal_x,
            fee=0
        )
        token1 = 0.0

    # Position is in range
    elif price_lower <= sqrtpx96 <= price_upper:
        token0 = size_price_change_in_tick(
            l=position_l,
            sqrtpx96=sqrtpx96,
            sqrtpx96_target=price_upper,
            dx=True,
            decimal_scale=decimal_x,
            fee=0
        )
        token1 = size_price_change_in_tick(
            l=position_l,
            sqrtpx96=sqrtpx96,
            sqrtpx96_target=price_lower,
            dx=False,
            decimal_scale=decimal_y,
            fee=0
        )
    else:
        raise ValueError("Double check tick_upper > tick_lower.")

    return PositionBalance(
        token0=abs(float(token0)),
        token1=abs(float(token1))
    )


def check_positions(
    ptbl: pd.DataFrame,
    p: float,
    decimal_adjustment: float = 1.0,
    yx: bool = True
) -> pd.DataFrame:
    """
    Flag liquidity positions as active or not active at a specific price.

    Args:
        ptbl: Liquidity positions table with columns tick_lower, tick_upper, liquidity.
        p: Specific price in human readable format.
        decimal_adjustment: The difference in the tokens decimals, e.g., 1e10 for ETH vs BTC.
        yx: Whether price is already in Token 1 / Token 0 format or inverted. Default True.

    Returns:
        The liquidity positions table with a new 'active' column indicating whether
        the liquidity is active at price P.

    Examples:
        >>> import pandas as pd
        >>> ptbl = pd.DataFrame({
        ...     'tick_lower': [256400, 256000],
        ...     'tick_upper': [256520, 256100],
        ...     'liquidity': [1000000, 2000000]
        ... })
        >>> check_positions(ptbl, p=0.10, decimal_adjustment=1e10, yx=False)
    """
    if "tick_lower" not in ptbl.columns or "tick_upper" not in ptbl.columns:
        raise ValueError("Expected tick_lower and tick_upper columns")

    # For making positions, tick_spacing=1 is only valid for 0.01% pools,
    # but this works for inside a valid range
    tick_target = get_closest_tick(p, tick_spacing=1, decimal_adjustment=decimal_adjustment, yx=yx)
    target_tick = tick_target["tick"]

    result = ptbl.copy()
    result["active"] = (result["tick_lower"] <= target_tick) & (result["tick_upper"] >= target_tick)

    return result
