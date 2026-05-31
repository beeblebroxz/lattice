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

from .shocks import shocked_value

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
    vol_shock: float = 0.0,
    rate_shock: float = 0.0,
) -> dict:
    """Apply spot/vol/rate shocks to a book and return the P&L impact.

    For positions linked to a live instrument, the instrument's Spot/Volatility/
    Rate are overridden (each unique instrument once) and the book reprices
    reactively. For price-only positions, spot_shock moves MarketPrice; vol/rate
    have nothing to act on. Shocks that found nothing to act on are reported
    under ``skipped_shocks`` rather than silently dropped.

    Shock convention (see lattice.risk.shocks): spot/vol relative, rate absolute.

    The rate leg covers both ``Rate`` (option rate input) and ``YieldToMaturity``
    (bond rate input), so bond-linked books reprice correctly on rate_shock.
    Swap-specific rate inputs (FloatingRate, DiscountRate) are a follow-up.
    """
    base_pnl = book.TotalPnL()
    legs = {
        "spot_shock": (("Spot",), spot_shock),
        "vol_shock": (("Volatility",), vol_shock),
        "rate_shock": (("Rate", "YieldToMaturity"), rate_shock),
    }
    applied: dict = {}
    skipped: dict = {}

    with dag.scenario():
        # Unique linked instruments + the price-only positions.
        instruments = []
        seen = set()
        unlinked = []
        for pos in book.Positions():
            inst = pos.LinkedInstrument()
            if inst is not None:
                if id(inst) not in seen:
                    seen.add(id(inst))
                    instruments.append(inst)
            else:
                unlinked.append(pos)

        for leg, (factors, shock) in legs.items():
            # A zero-magnitude leg is a no-op; report it in neither applied nor skipped.
            if shock == 0.0:
                continue
            acted = False
            for inst in instruments:
                for factor in factors:
                    if hasattr(inst, factor):
                        acc = getattr(inst, factor)
                        acc.override(shocked_value(factor, acc(), shock))
                        acted = True
            # The spot leg also moves price-only positions' MarketPrice.
            if "Spot" in factors:
                for pos in unlinked:
                    pos.MarketPrice.override(
                        shocked_value("Spot", pos.MarketPrice(), shock)
                    )
                    acted = True
            (applied if acted else skipped)[leg] = shock

        stressed_pnl = book.TotalPnL()

    return {
        "base_pnl": base_pnl,
        "stressed_pnl": stressed_pnl,
        "pnl_impact": stressed_pnl - base_pnl,
        "spot_shock": spot_shock,
        "vol_shock": vol_shock,
        "rate_shock": rate_shock,
        "applied_shocks": applied,
        "skipped_shocks": skipped,
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
