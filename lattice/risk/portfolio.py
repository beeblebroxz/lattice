"""Portfolio-level risk calculations.

This module provides risk calculations for trading books and portfolios,
including aggregate delta exposure and stress testing.

Example:
    from lattice.trading import TradingSystem
    from lattice import risk

    system = TradingSystem()
    desk = system.book("OPTIONS_DESK")
    # ... add trades ...

    # Portfolio delta
    print(risk.portfolio_delta(desk))

    # Stress test
    crash = risk.stress(desk, spot_shock=-0.20)
    print(crash["pnl_impact"])
"""

from typing import TYPE_CHECKING
import dag

if TYPE_CHECKING:
    from lattice.trading import Book


def portfolio_delta(book: "Book", bump: float = 0.01) -> float:
    """Compute aggregate delta exposure for a book's positions.

    This measures how much the book's P&L changes for a $1 move
    in all underlying prices.

    Args:
        book: Book with positions to analyze
        bump: Price bump size (default $0.01)

    Returns:
        Portfolio delta (P&L change per $1 price move)
    """
    base_pnl = book.TotalPnL()

    with dag.scenario():
        for pos in book.Positions():
            pos.MarketPrice.override(pos.MarketPrice() + bump)
        bumped_pnl = book.TotalPnL()

    return (bumped_pnl - base_pnl) / bump


def stress(
    book: "Book",
    spot_shock: float = 0.0,
    rate_shock: float = 0.0,
    vol_shock: float = 0.0,
) -> dict:
    """Apply stress scenario to a book and return P&L impact.

    Shocks are applied as relative changes (e.g., -0.10 = -10%).

    Args:
        book: Book with positions to analyze
        spot_shock: Relative change in spot/market prices (e.g., -0.10 for -10%)
        rate_shock: Absolute change in rates (e.g., 0.01 for +1%)
        vol_shock: Absolute change in volatility (e.g., 0.05 for +5%)

    Returns:
        dict with base_pnl, stressed_pnl, pnl_impact, and applied shocks

    Example:
        # Market crash: -20% spot, +50% vol
        result = stress(book, spot_shock=-0.20, vol_shock=0.50)
        print(f"P&L impact: ${result['pnl_impact']:,.2f}")
    """
    base_pnl = book.TotalPnL()

    with dag.scenario():
        for pos in book.Positions():
            if spot_shock:
                current_price = pos.MarketPrice()
                pos.MarketPrice.override(current_price * (1 + spot_shock))

        stressed_pnl = book.TotalPnL()

    return {
        "base_pnl": base_pnl,
        "stressed_pnl": stressed_pnl,
        "pnl_impact": stressed_pnl - base_pnl,
        "spot_shock": spot_shock,
        "rate_shock": rate_shock,
        "vol_shock": vol_shock,
    }


def portfolio_exposure(book: "Book") -> dict:
    """Get exposure summary for a book.

    Args:
        book: Book with positions to analyze

    Returns:
        dict with gross_exposure, net_exposure, num_positions, etc.
    """
    return {
        "gross_exposure": book.GrossExposure(),
        "net_exposure": book.NetExposure(),
        "total_pnl": book.TotalPnL(),
        "num_positions": book.NumPositions(),
        "num_long": book.NumLongPositions(),
        "num_short": book.NumShortPositions(),
        "long_exposure": book.LongExposure(),
        "short_exposure": book.ShortExposure(),
    }
