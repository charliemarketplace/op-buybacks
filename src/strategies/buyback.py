"""
Buyback strategies for OP token accumulation.

Strategies:
1. Naive: Swap ETH → OP at random/fixed times
2. Timing: Swap when OP is "cheap" based on signals
3. POL: Deploy as V3 liquidity, accumulate both tokens + fees
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from abc import ABC, abstractmethod

from ..uniswap_v3.liquidity import (
    Position,
    create_position,
    match_tokens_to_range,
    match_range_to_tokens,
    simulate_swap_in_position,
)


@dataclass
class BuybackResult:
    """Result of running a buyback strategy over a period."""
    strategy_name: str
    total_eth_spent: float
    total_op_acquired: float
    total_fees_earned_eth: float
    total_fees_earned_op: float
    avg_execution_price: float  # OP per ETH
    positions: List[Position] = field(default_factory=list)
    daily_log: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def net_op(self) -> float:
        """Total OP including fees."""
        return self.total_op_acquired + self.total_fees_earned_op

    @property
    def net_eth(self) -> float:
        """Remaining ETH including fees."""
        return self.total_fees_earned_eth

    def summary(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "eth_spent": self.total_eth_spent,
            "op_acquired": self.total_op_acquired,
            "fees_eth": self.total_fees_earned_eth,
            "fees_op": self.total_fees_earned_op,
            "avg_price": self.avg_execution_price,
            "num_positions": len(self.positions),
        }


class Strategy(ABC):
    """Base class for buyback strategies."""

    @abstractmethod
    def execute(
        self,
        daily_fees: pd.DataFrame,
        ohlc: pd.DataFrame,
        swaps: pd.DataFrame,
    ) -> BuybackResult:
        """
        Execute the strategy over the given data.

        Args:
            daily_fees: DataFrame with columns [date, total_fees_eth, tx_count]
            ohlc: DataFrame with OHLC price data
            swaps: DataFrame with individual swap data

        Returns:
            BuybackResult with execution details
        """
        pass


class NaiveBuybackStrategy(Strategy):
    """
    Simple strategy: convert all ETH fees to OP daily at market price.
    """

    def __init__(self, execution_time: str = "close"):
        """
        Args:
            execution_time: Which price to use - 'open', 'close', 'vwap', 'random'
        """
        self.execution_time = execution_time

    def execute(
        self,
        daily_fees: pd.DataFrame,
        ohlc: pd.DataFrame,
        swaps: pd.DataFrame,
    ) -> BuybackResult:
        # Merge fees with prices
        df = daily_fees.merge(ohlc, left_on="date", right_on="timestamp", how="inner")

        if self.execution_time == "close":
            df["exec_price"] = df["close"]
        elif self.execution_time == "open":
            df["exec_price"] = df["open"]
        elif self.execution_time == "vwap":
            df["exec_price"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
        elif self.execution_time == "random":
            # Random price within day's range
            df["exec_price"] = df.apply(
                lambda r: np.random.uniform(r["low"], r["high"]), axis=1
            )
        else:
            raise ValueError(f"Unknown execution_time: {self.execution_time}")

        # Calculate OP acquired each day (price is OP per ETH)
        df["op_acquired"] = df["total_fees_eth"] * df["exec_price"]

        total_eth = df["total_fees_eth"].sum()
        total_op = df["op_acquired"].sum()

        return BuybackResult(
            strategy_name=f"naive_{self.execution_time}",
            total_eth_spent=total_eth,
            total_op_acquired=total_op,
            total_fees_earned_eth=0.0,
            total_fees_earned_op=0.0,
            avg_execution_price=total_op / total_eth if total_eth > 0 else 0,
            daily_log=df[["date", "total_fees_eth", "exec_price", "op_acquired"]],
        )


class TimingBuybackStrategy(Strategy):
    """
    Strategy: Buy OP only when price is below a threshold (e.g., previous day's low).
    Accumulate ETH when price is high, deploy when price dips.
    """

    def __init__(
        self,
        buy_signal: Callable[[pd.Series, pd.DataFrame], bool] = None,
        lookback_days: int = 7,
    ):
        """
        Args:
            buy_signal: Function(today_row, historical_df) -> bool
            lookback_days: Days of history for signal calculation
        """
        self.buy_signal = buy_signal or self._default_signal
        self.lookback_days = lookback_days

    def _default_signal(self, today: pd.Series, history: pd.DataFrame) -> bool:
        """Buy if today's open is below the lookback period's average low."""
        if len(history) < self.lookback_days:
            return True  # Not enough history, just buy
        recent = history.tail(self.lookback_days)
        avg_low = recent["low"].mean()
        return today["open"] < avg_low

    def execute(
        self,
        daily_fees: pd.DataFrame,
        ohlc: pd.DataFrame,
        swaps: pd.DataFrame,
    ) -> BuybackResult:
        df = daily_fees.merge(ohlc, left_on="date", right_on="timestamp", how="inner")
        df = df.sort_values("date").reset_index(drop=True)

        eth_reserve = 0.0
        total_op = 0.0
        total_eth_spent = 0.0
        log_rows = []

        for i, row in df.iterrows():
            eth_reserve += row["total_fees_eth"]
            history = df.iloc[:i] if i > 0 else pd.DataFrame()

            if self.buy_signal(row, history):
                # Execute buy at close price
                op_acquired = eth_reserve * row["close"]
                total_op += op_acquired
                total_eth_spent += eth_reserve
                log_rows.append({
                    "date": row["date"],
                    "action": "buy",
                    "eth_spent": eth_reserve,
                    "price": row["close"],
                    "op_acquired": op_acquired,
                    "eth_reserve": 0.0,
                })
                eth_reserve = 0.0
            else:
                log_rows.append({
                    "date": row["date"],
                    "action": "hold",
                    "eth_spent": 0.0,
                    "price": row["close"],
                    "op_acquired": 0.0,
                    "eth_reserve": eth_reserve,
                })

        return BuybackResult(
            strategy_name="timing",
            total_eth_spent=total_eth_spent,
            total_op_acquired=total_op,
            total_fees_earned_eth=eth_reserve,  # Leftover
            total_fees_earned_op=0.0,
            avg_execution_price=total_op / total_eth_spent if total_eth_spent > 0 else 0,
            daily_log=pd.DataFrame(log_rows),
        )


class POLStrategy(Strategy):
    """
    Protocol Owned Liquidity strategy:
    Deploy tx fees as V3 liquidity, accumulating both tokens and earning trading fees.

    Two modes:
    1. Single wide position: Add to one position continuously
    2. Multiple positions: Create new positions daily
    """

    def __init__(
        self,
        mode: str = "single_wide",
        range_width_pct: float = 0.5,  # +/- 50% from current price
        fee_rate: float = 0.003,  # 0.3% fee tier
        initial_op_ratio: float = 0.5,  # What fraction of ETH to swap to OP initially
    ):
        """
        Args:
            mode: 'single_wide' or 'multiple'
            range_width_pct: Position width as fraction of current price
            fee_rate: Pool fee rate (0.003 = 0.3%)
            initial_op_ratio: Fraction of incoming ETH to swap to OP for LP
        """
        self.mode = mode
        self.range_width_pct = range_width_pct
        self.fee_rate = fee_rate
        self.initial_op_ratio = initial_op_ratio

    def execute(
        self,
        daily_fees: pd.DataFrame,
        ohlc: pd.DataFrame,
        swaps: pd.DataFrame,
    ) -> BuybackResult:
        df = daily_fees.merge(ohlc, left_on="date", right_on="timestamp", how="inner")
        df = df.sort_values("date").reset_index(drop=True)

        positions: List[Position] = []
        total_eth_used = 0.0
        total_op_acquired = 0.0
        fees_eth = 0.0
        fees_op = 0.0
        log_rows = []

        for i, row in df.iterrows():
            eth_in = row["total_fees_eth"]
            current_price = row["close"]

            # Swap portion to OP for balanced LP
            eth_for_op = eth_in * self.initial_op_ratio
            eth_for_lp = eth_in - eth_for_op
            op_acquired = eth_for_op * current_price

            # Define position range
            price_low = current_price * (1 - self.range_width_pct)
            price_high = current_price * (1 + self.range_width_pct)

            # Calculate matched amounts for the range
            matched_eth, matched_op = match_tokens_to_range(
                current_price=current_price,
                price_low=price_low,
                price_high=price_high,
                amount_eth=eth_for_lp,
            )

            # May need to adjust if we don't have enough OP
            if matched_op > op_acquired:
                # Use all OP, recalc ETH
                matched_eth, matched_op = match_tokens_to_range(
                    current_price=current_price,
                    price_low=price_low,
                    price_high=price_high,
                    amount_op=op_acquired,
                )

            # Create position
            position = create_position(
                current_price=current_price,
                price_low=price_low,
                price_high=price_high,
                amount_eth=min(matched_eth, eth_for_lp),
                amount_op=min(matched_op, op_acquired),
            )

            positions.append(position)
            total_eth_used += position.amount_eth + eth_for_op
            total_op_acquired += position.amount_op

            # Estimate fees earned (simplified: based on daily volume through position)
            day_volume = row.get("volume_eth", 0)
            if day_volume > 0 and position.liquidity > 0:
                # Simplified fee model: assume position captures proportional volume
                # In reality, depends on where trades happen relative to position range
                estimated_fee_eth = day_volume * self.fee_rate * 0.1  # Conservative 10% capture
                estimated_fee_op = estimated_fee_eth * current_price
                fees_eth += estimated_fee_eth
                fees_op += estimated_fee_op

            log_rows.append({
                "date": row["date"],
                "price": current_price,
                "eth_in": eth_in,
                "position_eth": position.amount_eth,
                "position_op": position.amount_op,
                "position_liquidity": position.liquidity,
                "range_low": price_low,
                "range_high": price_high,
            })

        avg_price = total_op_acquired / total_eth_used if total_eth_used > 0 else 0

        return BuybackResult(
            strategy_name=f"pol_{self.mode}",
            total_eth_spent=total_eth_used,
            total_op_acquired=total_op_acquired,
            total_fees_earned_eth=fees_eth,
            total_fees_earned_op=fees_op,
            avg_execution_price=avg_price,
            positions=positions,
            daily_log=pd.DataFrame(log_rows),
        )


def compare_strategies(
    strategies: List[Strategy],
    daily_fees: pd.DataFrame,
    ohlc: pd.DataFrame,
    swaps: pd.DataFrame,
) -> pd.DataFrame:
    """
    Run multiple strategies and compare results.
    """
    results = []
    for strategy in strategies:
        result = strategy.execute(daily_fees, ohlc, swaps)
        results.append(result.summary())

    return pd.DataFrame(results)
