"""
Basic tests for Uniswap V3 calculation utilities.

Tests are based on examples from the original R documentation.
"""

import pandas as pd
import pytest

from uniswap import (
    tick_to_price,
    get_closest_tick,
    sqrtpx96_to_price,
    price_to_sqrtpx96,
    get_liquidity,
    get_position_balance,
    check_positions,
    swap_within_tick,
    size_price_change_in_tick,
    calc_fees_from_trades,
    find_recalculation_price,
    match_tokens_to_range,
    price_all_tokens,
)


class TestTickToPrice:
    """Tests for tick_to_price function."""

    def test_usdc_eth_price(self):
        """1,351.327 USDC per ETH from tick 204232."""
        result = tick_to_price(204232, decimal_adjustment=1e12, yx=False)
        assert abs(result - 1351.327) / 1351.327 < 0.001  # Within 0.1%

    def test_eth_wbtc_price(self):
        """19.98232 ETH per WBTC from tick 260220."""
        result = tick_to_price(260220, decimal_adjustment=1e10, yx=True)
        assert abs(result - 19.98232) / 19.98232 < 0.001  # Within 0.1%

    def test_invert_equivalence(self):
        """Inverted prices should be equivalent."""
        result_yx_false = tick_to_price(260220, decimal_adjustment=1e10, yx=False) ** -1
        result_yx_true = tick_to_price(260220, decimal_adjustment=1e10, yx=True)
        assert abs(result_yx_false / result_yx_true - 1) < 0.000001


class TestGetClosestTick:
    """Tests for get_closest_tick function."""

    def test_btc_eth_tick(self):
        """0.05 BTC/ETH should give tick 260220."""
        result = get_closest_tick(0.05, tick_spacing=60, decimal_adjustment=1e10, yx=False)
        assert result["tick"] == 260220

    def test_eth_btc_inverted(self):
        """20 ETH/BTC should also give tick 260220."""
        result = get_closest_tick(20, tick_spacing=60, decimal_adjustment=1e10, yx=True)
        assert result["tick"] == 260220

    def test_tick_spacing_1(self):
        """tick_spacing=1 should inverse tick_to_price."""
        result = get_closest_tick(
            desired_price=0.05004423, tick_spacing=1, decimal_adjustment=1e10, yx=False
        )
        assert result["tick"] == 260220


class TestPriceConversions:
    """Tests for sqrtpx96_to_price and price_to_sqrtpx96."""

    def test_sqrtpx96_to_price_usdc_eth(self):
        """Convert sqrtPriceX96 to USDC/ETH price."""
        result = sqrtpx96_to_price(
            "1854219362252931989533640458424264", invert=True, decimal_adjustment=1e12
        )
        assert abs(result - 1825.732) / 1825.732 < 0.0001  # Within 0.01%

    def test_price_to_sqrtpx96_usdc_eth(self):
        """Convert USDC/ETH price to sqrtPriceX96."""
        result = price_to_sqrtpx96(1825.732, invert=True, decimal_adjustment=1e12)
        expected = 1854219362252931989533640458424264
        # Should be within 0.001%
        assert abs(result / expected - 1) < 0.00001

    def test_roundtrip(self):
        """Converting price to sqrtpx96 and back should be close to original."""
        original_price = 1825.732
        sqrtpx96 = price_to_sqrtpx96(original_price, invert=True, decimal_adjustment=1e12)
        recovered = sqrtpx96_to_price(sqrtpx96, invert=True, decimal_adjustment=1e12)
        assert abs(recovered / original_price - 1) < 0.0001


class TestGetLiquidity:
    """Tests for get_liquidity function."""

    def test_eth_wbtc_liquidity(self):
        """
        From block 12,376,757: 1 BTC and 16.117809469 ETH added to pool
        with range 257760 to 258900, should result in liquidity ~1429022393248418.
        """
        result = get_liquidity(
            x=1,
            y=16.117809469,
            sqrtpx96="32211102662183904786754519772954624",
            decimal_x=1e8,
            decimal_y=1e18,
            tick_lower=257760,
            tick_upper=258900,
        )
        expected = 1429022393248418
        # Within 0.01%
        assert abs(result / expected - 1) < 0.0001


class TestCheckPositions:
    """Tests for check_positions function."""

    def test_active_flag(self):
        """Positions should be flagged as active or inactive based on price."""
        ptbl = pd.DataFrame({
            "tick_lower": [256400, 256000, 260000],
            "tick_upper": [256520, 256100, 260100],
            "liquidity": [1000000, 2000000, 3000000],
        })
        result = check_positions(ptbl, p=0.05, decimal_adjustment=1e10, yx=False)

        # Check that active column was added
        assert "active" in result.columns
        # At least one position should be active and one inactive
        assert result["active"].sum() < len(result)


class TestSwapWithinTick:
    """Tests for swap_within_tick function."""

    def test_sell_eth_for_btc(self):
        """
        Sale of 0.03 ETH should return ~-0.00224477 BTC from pool.
        """
        result = swap_within_tick(
            l="1785868753774080000",
            sqrtpx96="28920208462486575390334957222100992",
            dx=None,
            dy=0.03,
            decimal_x=1e8,
            decimal_y=1e18,
            fee=0.003,
        )
        # dx should be negative (BTC taken from pool)
        assert result["dx"] < 0
        # Should be close to -0.00224477
        assert abs(result["dx"] - (-0.00224477)) / 0.00224477 < 0.01  # Within 1%


class TestSizePriceChangeInTick:
    """Tests for size_price_change_in_tick function."""

    def test_link_added_to_pool(self):
        """Calculate LINK needed to move price."""
        result = size_price_change_in_tick(
            l="343255264548669212",
            sqrtpx96="7625888646051765535543132160",
            sqrtpx96_target="7625888580652810738255925731",
            dx=True,
            decimal_scale=1e18,
            fee=0.003,
        )
        # Should be a very small positive number (LINK added to pool)
        assert result > 0
        assert result < 0.001  # Very small amount


class TestCalcFeesFromTrades:
    """Tests for calc_fees_from_trades function."""

    def test_basic_fee_calculation(self):
        """Basic fee calculation from trades."""
        trades = pd.DataFrame({
            "tick": [256450, 256460, 256470],
            "amount0_adjusted": [0.1, -0.05, 0.2],
            "amount1_adjusted": [-1.5, 0.8, -2.0],
            "liquidity": [1000000000000000, 1000000000000000, 1000000000000000],
        })
        result = calc_fees_from_trades(
            position_l="1000000000000000",
            tick_lower=256400,
            tick_upper=256520,
            trades=trades,
            fee=0.003,
        )
        # Should have fee values
        assert "amount0_fees" in result
        assert "amount1_fees" in result
        # Fees should be positive (from positive amounts in trades)
        assert result["amount0_fees"] >= 0
        assert result["amount1_fees"] >= 0


class TestMatchTokensToRange:
    """Tests for match_tokens_to_range function."""

    def test_match_btc_to_eth(self):
        """
        Match 1 BTC to ETH in range 257760-258900 at price 16.52921 ETH/BTC.
        Should return ~16.117809469 ETH.
        """
        result = match_tokens_to_range(
            x=1,
            y=None,
            sqrtpx96="32211102662183904786754519772954624",
            decimal_x=1e8,
            decimal_y=1e18,
            tick_lower=257760,
            tick_upper=258900,
        )
        assert result["amount_x"] == 1
        assert result["amount_y"] is not None
        # Should be close to 16.117809469
        assert abs(result["amount_y"] - 16.117809469) / 16.117809469 < 0.01


class TestPriceAllTokens:
    """Tests for price_all_tokens function."""

    def test_find_tick_lower(self):
        """
        Given x=1, y=16.11781, and tick_upper=258900, find tick_lower.
        Should return tick_lower=257760.
        """
        result = price_all_tokens(
            x=1,
            y=16.11781,
            sqrtpx96="32211102662183904786754519772954624",
            decimal_x=1e8,
            decimal_y=1e18,
            tick_lower=None,
            tick_upper=258900,
        )
        assert result["tick_upper"] == 258900
        # tick_lower should be close to 257760
        assert abs(result["tick_lower"] - 257760) < 10  # Within 10 ticks


class TestFindRecalculationPrice:
    """Tests for find_recalculation_price function."""

    def test_find_next_price_up(self):
        """Find next price where liquidity recalculates when price goes up."""
        ptbl = pd.DataFrame({
            "tick_lower": [92100, 256000],
            "tick_upper": [267180, 267500],
            "liquidity": [1000000, 2000000],
        })
        # At current price, find next higher recalculation price
        result = find_recalculation_price(
            ptbl=ptbl,
            p=39.36252,
            price_up=True,
            decimal_adjustment=1e10,
            yx=True,
        )
        # Should return a price higher than current
        assert result > 39.36252


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
