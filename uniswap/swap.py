"""
Swap calculation functions for Uniswap V3.
"""

from typing import Any, Optional, TypedDict, Union
from fractions import Fraction
import pandas as pd

from .tick import tick_to_price
from .price import price_to_sqrtpx96, sqrtpx96_to_price


class SwapResult(TypedDict, total=False):
    """Result from swap functions."""
    liquidity: int
    dx: float
    dy: float
    price1: int
    price2: int
    fee: float


class TradeRecord(TypedDict, total=False):
    """Trade record from swap_across_ticks."""
    ptbl: pd.DataFrame
    new_price: int
    dy_in: float
    dy_fee: float
    dx_out: float
    dx_in: float
    dx_fee: float
    dy_out: float
    fee_tbl: pd.DataFrame


def size_price_change_in_tick(
    l: Union[int, str],
    sqrtpx96: Union[int, str],
    sqrtpx96_target: Union[int, str],
    dx: bool = True,
    decimal_scale: float = 1e18,
    fee: float = 0.003
) -> float:
    """
    Calculate trade size required to move price to target within a tick.

    Given liquidity, a current price, a target price, and the fee tier of a pool,
    calculate how large a trade would be required to get to the target price.

    Args:
        l: Active raw amount of liquidity in the pool, as big integer.
        sqrtpx96: Current price in uint160 format.
        sqrtpx96_target: Target price in uint160 format.
        dx: Whether the amount should be denominated in token 0 (True) or token 1 (False).
        decimal_scale: Decimal of token 0 (if dx=True) or token 1 (if dx=False).
            NOT decimal_adjustment between the two. 1e6 for USDC, 1e8 for WBTC, 1e18 for WETH.
        fee: The pool fee, default 0.3% (0.003). Generally one of: 0.0001, 0.0005, 0.003, 0.01

    Returns:
        Human readable (decimal adjusted) amount the trader needs to trade.
        Positive results are adds to the pool (trader sells);
        negative results are removes from pool (trader buys).

    Examples:
        >>> # Move LINK/MKR 0.3% Pool on Optimism from current price to new price
        >>> size_price_change_in_tick(
        ...     l="343255264548669212",
        ...     sqrtpx96="7625888646051765535543132160",
        ...     sqrtpx96_target='7625888580652810738255925731',
        ...     dx=True,
        ...     decimal_scale=1e18,
        ...     fee=0.003
        ... )
        0.00000003067549  # LINK added to pool (trader sells LINK)
    """
    l = int(l)
    p = int(sqrtpx96)
    p_target = int(sqrtpx96_target)
    c96 = 2 ** 96

    if dx:
        # Use Fraction for precise arithmetic
        ip = Fraction(1, p)
        ip_target = Fraction(1, p_target)
        dxa = (ip_target - ip) * l
        result = float(dxa) / (1 - fee) / decimal_scale * c96
        return result
    else:
        dya = (p_target - p) * l
        dy = dya / (1 - fee) / c96 / decimal_scale
        return float(dy)


def swap_within_tick(
    l: Union[int, str],
    sqrtpx96: Union[int, str],
    dx: Optional[float] = None,
    dy: Optional[float] = None,
    decimal_x: float = 1e18,
    decimal_y: float = 1e18,
    fee: float = 0.003
) -> SwapResult:
    """
    Calculate the output of a swap within a single tick (no liquidity recalculation).

    This function calculates the amount of an asset coming out of a trade from a pool
    given the active liquidity, the current price, the amount of the other asset,
    and the pool fee.

    Args:
        l: Active amount of liquidity in the pool, as big integer.
        sqrtpx96: Current price in uint160 format.
        dx: Human readable amount of token 0 you are trading. None if trading token 1.
        dy: Human readable amount of token 1 you are trading. None if trading token 0.
        decimal_x: The decimals used in token 0, e.g., 1e6 for USDC, 1e8 for WBTC.
        decimal_y: The decimals used in token 1, e.g., 1e18 for WETH.
        fee: The pool fee, default 0.3% (0.003).

    Returns:
        A dict containing:
        - liquidity: Amount of liquidity in the pool after the trade
        - dx: Amount of token 0 added/removed from pool
        - dy: Amount of token 1 added/removed from pool
        - price1: Initial sqrtpx96 price before the swap
        - price2: Final sqrtpx96 price after the swap
        - fee: Fee taken by the pool

    Note:
        This function assumes the amounts traded do not cause a recalculation of
        active liquidity. Use swap_across_ticks for trades that may cross tick boundaries.

    Examples:
        >>> # Sale of 0.03 ETH in ETH/WBTC pool
        >>> swap_within_tick(
        ...     l='1785868753774080000',
        ...     sqrtpx96='28920208462486575390334957222100992',
        ...     dx=None, dy=0.03,
        ...     decimal_x=1e8, decimal_y=1e18, fee=0.003
        ... )
        # Returns ~-0.00224477 BTC from pool
    """
    if dx is None and dy is None:
        raise ValueError("A change in x or y is required to use liquidity")

    if dx is not None and dy is not None:
        raise ValueError("Only 1 swap can be noted")

    l = int(l)
    p = int(sqrtpx96)
    c96 = 2 ** 96

    # Use Fraction for precise arithmetic with inverse price
    ip = Fraction(1, p)

    result: SwapResult = {
        "liquidity": l,
        "dx": 0.0,
        "dy": 0.0,
        "price1": p,
        "price2": 0,
        "fee": 0.0
    }

    if dx is not None:
        # Adjust real dx to 96 int & adjust for fees
        dxa = Fraction(dx) * Fraction(int((1 - fee) * 1e18), int(1e18)) * Fraction(int(decimal_x)) / c96

        # iP_new = dx/L + iP
        ip_new = dxa / l + ip
        p_new = 1 / ip_new

        # dy = (P_new - P) * L
        dya = (p_new - p) * l

        # Convert back to real units
        dyz = float(dya / c96 / decimal_y)

        result["dx"] = dx * (1 - fee)
        result["dy"] = dyz
        result["price2"] = int(p_new)
        result["fee"] = fee * dx

    elif dy is not None:
        # Adjust real dy to 96 int & adjust for fees
        dya = Fraction(dy) * Fraction(int((1 - fee) * 1e18), int(1e18)) * c96 * Fraction(int(decimal_y))

        # P_new = dy/L + P
        p_new = dya / l + p
        ip_new = 1 / p_new

        # dx = (iP_new - iP) * L
        dxa = (ip_new - ip) * l

        # Convert to real units
        dxz = float(dxa * c96 / decimal_x)

        result["dx"] = dxz
        result["dy"] = dy * (1 - fee)
        result["price2"] = int(p_new)
        result["fee"] = fee * dy

    return result


def swap_across_ticks(
    ptbl: pd.DataFrame,
    sqrtpx96: Union[int, str],
    fee_tbl: Optional[pd.DataFrame] = None,
    trade_record: Optional[TradeRecord] = None,
    dx: Optional[float] = None,
    dy: Optional[float] = None,
    decimal_x: float = 1e18,
    decimal_y: float = 1e18,
    fee: float = 0.003
) -> TradeRecord:
    """
    Execute a swap that may cross tick boundaries, recalculating liquidity as needed.

    This function loops through a trade given the swap amount and available liquidity
    (including inactive positions) to calculate the amount received, resulting fees
    paid to each position, and the final price including a history of trades.

    Args:
        ptbl: Liquidity positions table with columns tick_lower, tick_upper, liquidity.
        sqrtpx96: Current price in Uniswap 64.96 square root price format.
        fee_tbl: Table of fees accumulated so far. None for fresh trade.
        trade_record: Trade histories so far. None for fresh trade.
        dx: Human readable amount of token 0 you are trading. None if trading token 1.
        dy: Human readable amount of token 1 you are trading. None if trading token 0.
        decimal_x: The decimals used in token 0, e.g., 1e6 for USDC, 1e8 for WBTC.
        decimal_y: The decimals used in token 1, e.g., 1e18 for WETH.
        fee: The pool fee, default 0.3% (0.003).

    Returns:
        A TradeRecord dict containing:
        - ptbl: Updated liquidity positions table with active flags
        - new_price: The sqrtpx96 after the trade is complete
        - dy_in/dx_in: Amount of token added to pool (fees separated)
        - dy_fee/dx_fee: Amount taken to pay LPs
        - dx_out/dy_out: Amount taken from pool (bought by user)
        - fee_tbl: Fee distribution across positions

    Examples:
        >>> # Trade causing recalculation of liquidity
        >>> swp = swap_across_ticks(
        ...     ptbl=liquidity_table, sqrtpx96=sqrtpx96,
        ...     fee_tbl=None, trade_record=None,
        ...     dx=None, dy=1140.0,
        ...     decimal_x=1e8, decimal_y=1e18, fee=0.003
        ... )
        >>> swp['dx_out']  # BTC removed from pool
        -84.98101962
    """
    # Import here to avoid circular dependency
    from .liquidity import check_positions
    from .utils import find_recalculation_price

    sqrtpx96 = int(sqrtpx96)
    decimal_adjustment = max(decimal_y / decimal_x, decimal_x / decimal_y)

    if dx is None and dy is None:
        raise ValueError("A change in x or y is required to use liquidity")

    if dx is not None and dy is not None:
        raise ValueError("Only 1 swap can be done at a time")

    # Selling dy (price going up: P = Y/X, more Y is more P)
    if dx is None:
        amount = dy
        price = sqrtpx96_to_price(sqrtpx96=sqrtpx96, invert=False, decimal_adjustment=decimal_adjustment)
        update_ptbl = check_positions(ptbl, price, decimal_adjustment=decimal_adjustment, yx=True)

        # Initialize or update fee table
        if fee_tbl is None:
            fee_tbl = update_ptbl[["tick_lower", "tick_upper", "liquidity", "active"]].copy()
            fee_tbl["yfee"] = 0.0
        else:
            yfee = fee_tbl["yfee"].copy()
            fee_tbl = update_ptbl[["tick_lower", "tick_upper", "liquidity", "active"]].copy()
            fee_tbl["yfee"] = yfee

        recalc_price = find_recalculation_price(
            ptbl=update_ptbl, p=price, price_up=True,
            decimal_adjustment=decimal_adjustment, yx=True
        )

        # Sum liquidity in active positions
        current_l = sum(int(liq) for liq, active in zip(update_ptbl["liquidity"], update_ptbl["active"]) if active)

        # Maximum change without recalc
        max_y = size_price_change_in_tick(
            l=current_l,
            sqrtpx96=sqrtpx96,
            sqrtpx96_target=price_to_sqrtpx96(recalc_price, invert=False, decimal_adjustment=decimal_adjustment),
            dx=False,
            decimal_scale=decimal_y,
            fee=fee
        )

        # Can sell without recalculation
        if max_y >= amount:
            swap = swap_within_tick(
                l=current_l,
                sqrtpx96=price_to_sqrtpx96(p=price, invert=False, decimal_adjustment=decimal_adjustment),
                dy=amount,
                decimal_x=decimal_x,
                decimal_y=decimal_y,
                fee=fee
            )

            # Attribute fees to positions
            active_liquidity = sum(int(liq) for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"]) if active)
            new_fees = [
                float(swap["fee"]) * int(active) * int(liq) / active_liquidity if active_liquidity > 0 else 0.0
                for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"])
            ]

            if trade_record is None:
                fee_tbl["yfee"] = fee_tbl["yfee"] + new_fees
                return TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dy_in=swap["dy"],
                    dy_fee=swap["fee"],
                    dx_out=swap["dx"],
                    fee_tbl=fee_tbl
                )
            else:
                tr = trade_record
                fee_tbl["yfee"] = tr["fee_tbl"]["yfee"] + new_fees
                return TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dy_in=tr["dy_in"] + swap["dy"],
                    dy_fee=tr["dy_fee"] + swap["fee"],
                    dx_out=tr["dx_out"] + swap["dx"],
                    fee_tbl=fee_tbl
                )

        # Need to swap as much as possible and recurse
        else:
            leftover = amount - max_y

            swap = swap_within_tick(
                l=current_l,
                sqrtpx96=price_to_sqrtpx96(p=price, invert=False, decimal_adjustment=decimal_adjustment),
                dy=max_y,
                decimal_x=decimal_x,
                decimal_y=decimal_y,
                fee=fee
            )

            # Attribute fees to positions
            active_liquidity = sum(int(liq) for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"]) if active)
            new_fees = [
                float(swap["fee"]) * int(active) * int(liq) / active_liquidity if active_liquidity > 0 else 0.0
                for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"])
            ]

            if trade_record is None:
                fee_tbl["yfee"] = fee_tbl["yfee"] + new_fees
                trade_record = TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dy_in=swap["dy"],
                    dy_fee=swap["fee"],
                    dx_out=swap["dx"],
                    fee_tbl=fee_tbl
                )
            else:
                tr = trade_record
                fee_tbl["yfee"] = tr["fee_tbl"]["yfee"] + new_fees
                trade_record = TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dy_in=tr["dy_in"] + swap["dy"],
                    dy_fee=tr["dy_fee"] + swap["fee"],
                    dx_out=tr["dx_out"] + swap["dx"],
                    fee_tbl=fee_tbl
                )

            # Recurse with remaining amount
            return swap_across_ticks(
                ptbl=trade_record["ptbl"],
                sqrtpx96=trade_record["new_price"],
                fee_tbl=trade_record["fee_tbl"],
                trade_record=trade_record,
                dx=None,
                dy=leftover,
                decimal_x=decimal_x,
                decimal_y=decimal_y,
                fee=fee
            )

    # Selling dx (price going down: P = Y/X, more X is less P)
    elif dy is None:
        amount = dx
        price = sqrtpx96_to_price(sqrtpx96=sqrtpx96, invert=False, decimal_adjustment=decimal_adjustment)
        update_ptbl = check_positions(ptbl, price, decimal_adjustment=decimal_adjustment, yx=True)

        # Initialize or update fee table
        if fee_tbl is None:
            fee_tbl = update_ptbl[["tick_lower", "tick_upper", "liquidity", "active"]].copy()
            fee_tbl["xfee"] = 0.0
        else:
            xfee = fee_tbl["xfee"].copy()
            fee_tbl = update_ptbl[["tick_lower", "tick_upper", "liquidity", "active"]].copy()
            fee_tbl["xfee"] = xfee

        recalc_price = find_recalculation_price(
            ptbl=update_ptbl, p=price, price_up=False,
            decimal_adjustment=decimal_adjustment, yx=True
        )

        # Sum liquidity in active positions
        current_l = sum(int(liq) for liq, active in zip(update_ptbl["liquidity"], update_ptbl["active"]) if active)

        # Maximum change without recalc
        max_x = size_price_change_in_tick(
            l=current_l,
            sqrtpx96=sqrtpx96,
            sqrtpx96_target=price_to_sqrtpx96(recalc_price, invert=False, decimal_adjustment=decimal_adjustment),
            dx=True,
            decimal_scale=decimal_x,
            fee=fee
        )

        # Can sell without recalculation
        if max_x >= amount:
            swap = swap_within_tick(
                l=current_l,
                sqrtpx96=price_to_sqrtpx96(p=price, invert=False, decimal_adjustment=decimal_adjustment),
                dx=amount,
                decimal_x=decimal_x,
                decimal_y=decimal_y,
                fee=fee
            )

            # Attribute fees to positions
            active_liquidity = sum(int(liq) for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"]) if active)
            new_fees = [
                float(swap["fee"]) * int(active) * int(liq) / active_liquidity if active_liquidity > 0 else 0.0
                for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"])
            ]

            if trade_record is None:
                fee_tbl["xfee"] = fee_tbl["xfee"] + new_fees
                return TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dx_in=swap["dx"],
                    dx_fee=swap["fee"],
                    dy_out=swap["dy"],
                    fee_tbl=fee_tbl
                )
            else:
                tr = trade_record
                fee_tbl["xfee"] = tr["fee_tbl"]["xfee"] + new_fees
                return TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dx_in=tr["dx_in"] + swap["dx"],
                    dx_fee=tr["dx_fee"] + swap["fee"],
                    dy_out=tr["dy_out"] + swap["dy"],
                    fee_tbl=fee_tbl
                )

        # Need to swap as much as possible and recurse
        else:
            leftover = amount - max_x

            swap = swap_within_tick(
                l=current_l,
                sqrtpx96=price_to_sqrtpx96(p=price, invert=False, decimal_adjustment=decimal_adjustment),
                dx=max_x,
                decimal_x=decimal_x,
                decimal_y=decimal_y,
                fee=fee
            )

            # Attribute fees to positions
            active_liquidity = sum(int(liq) for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"]) if active)
            new_fees = [
                float(swap["fee"]) * int(active) * int(liq) / active_liquidity if active_liquidity > 0 else 0.0
                for liq, active in zip(fee_tbl["liquidity"], fee_tbl["active"])
            ]

            if trade_record is None:
                fee_tbl["xfee"] = fee_tbl["xfee"] + new_fees
                trade_record = TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dx_in=swap["dx"],
                    dx_fee=swap["fee"],
                    dy_out=swap["dy"],
                    fee_tbl=fee_tbl
                )
            else:
                tr = trade_record
                fee_tbl["xfee"] = tr["fee_tbl"]["xfee"] + new_fees
                trade_record = TradeRecord(
                    ptbl=update_ptbl,
                    new_price=swap["price2"],
                    dx_in=tr["dx_in"] + swap["dx"],
                    dx_fee=tr["dx_fee"] + swap["fee"],
                    dy_out=tr["dy_out"] + swap["dy"],
                    fee_tbl=fee_tbl
                )

            # Recurse with remaining amount
            return swap_across_ticks(
                ptbl=trade_record["ptbl"],
                sqrtpx96=trade_record["new_price"],
                fee_tbl=trade_record["fee_tbl"],
                trade_record=trade_record,
                dx=leftover,
                dy=None,
                decimal_x=decimal_x,
                decimal_y=decimal_y,
                fee=fee
            )

    # Should never reach here
    raise ValueError("Invalid state")
