"""Position as dag.Model class.

A Position represents a holding in a single instrument for a book.
"""

from typing import Dict

import dag

from lattice.store.storable import Storable


def _position_greeks(inst, quantity: int) -> Dict[str, float]:
    """Quantity-weighted numerical Greeks of a linked instrument.

    A Greek is zero when there is no linked instrument or it lacks the input
    the Greek is taken against (a bond has no Spot, a stock no Volatility).

    The instrument and quantity are passed in, read by the calling node, so
    that dag sees the node's dependencies.
    """
    from lattice.risk import sensitivities

    greeks = {"delta": 0.0, "gamma": 0.0, "vega": 0.0}
    if inst is None:
        return greeks
    if hasattr(inst, "Spot"):
        delta, gamma = sensitivities.delta_gamma(inst, output_name="MarketValue")
        greeks["delta"] = quantity * delta
        greeks["gamma"] = quantity * gamma
    if hasattr(inst, "Volatility"):
        greeks["vega"] = quantity * sensitivities.vega(inst, output_name="MarketValue")
    return greeks

class Position(Storable, dag.Model):
    """A position in a single instrument for a book.

    Positions are aggregated from trades. The quantity is signed:
    positive for long positions, negative for short.

    Example:
        pos = Position()
        pos.Symbol.set("AAPL_C_150")
        pos.BookId.set("DESK_A")
        pos.Quantity.set(10)      # Long 10
        pos.AvgPrice.set(5.25)

        pos.MarketPrice.set(6.00)
        print(pos.UnrealizedPnL())  # 7.50
        print(pos.MarketValue())    # 60.00
    """

    # ==================== Inputs ====================

    @dag.computed(dag.Persisted)
    def Symbol(self) -> str:
        """Instrument symbol."""
        return ""

    @dag.computed(dag.Persisted)
    def BookId(self) -> str:
        """Book ID this position belongs to."""
        return ""

    @dag.computed(dag.Persisted)
    def Quantity(self) -> int:
        """Position quantity. Positive = long, negative = short."""
        return 0

    @dag.computed(dag.Persisted)
    def AvgPrice(self) -> float:
        """Average entry price."""
        return 0.0

    @dag.computed(dag.Persisted)
    def RealizedPnL(self) -> float:
        """P&L locked in by trades that reduced, closed or flipped the position."""
        return 0.0

    @dag.computed(dag.Input | dag.Overridable)
    def MarketPrice(self) -> float:
        """Current market price for valuation.

        Defaults to average price. Override for mark-to-market.
        """
        return self.AvgPrice()

    # ==================== Computed ====================

    @dag.computed
    def CostBasis(self) -> float:
        """Total cost basis (absolute value)."""
        return abs(self.Quantity()) * self.AvgPrice()

    @dag.computed(dag.Input | dag.Optional)
    def LinkedInstrument(self):
        """Optional live instrument backing this position (None = price-only)."""
        return None

    @dag.computed
    def EffectivePrice(self) -> float:
        """Per-unit price: the instrument's market value if linked, else MarketPrice."""
        inst = self.LinkedInstrument()
        return inst.MarketValue() if inst is not None else self.MarketPrice()

    @dag.computed
    def MarketValue(self) -> float:
        """Current market value (signed). Uses the linked instrument when present."""
        return self.Quantity() * self.EffectivePrice()

    @dag.computed
    def UnrealizedPnL(self) -> float:
        """Unrealized P&L.

        = MarketValue - (Quantity * AvgPrice)
        """
        return self.MarketValue() - (self.Quantity() * self.AvgPrice())

    @dag.computed
    def TotalPnL(self) -> float:
        """Realized plus unrealized P&L."""
        return self.RealizedPnL() + self.UnrealizedPnL()

    # ==================== Greeks ====================
    # Position-level: quantity x the linked instrument's sensitivity, taken
    # on MarketValue (what the position is marked at).
    #
    # All three are computed together in one cached node. Each Greek is a
    # bump-and-reval inside a dag scenario, and a scenario on an instrument
    # invalidates everything that depends on it; as separate nodes, computing
    # gamma would throw away the cached delta, and so on. Together they are
    # computed once and then reused until the instrument or quantity changes,
    # so a tick on one instrument revalues only its own positions.

    @dag.computed
    def Greeks(self) -> Dict[str, float]:
        """Position delta, gamma and vega as a dict (zeros where not applicable)."""
        return _position_greeks(self.LinkedInstrument(), self.Quantity())

    @dag.computed
    def Delta(self) -> float:
        """Position delta: quantity x instrument delta (0 if not applicable)."""
        return self.Greeks()["delta"]

    @dag.computed
    def Gamma(self) -> float:
        """Position gamma: quantity x instrument gamma (0 if not applicable)."""
        return self.Greeks()["gamma"]

    @dag.computed
    def Vega(self) -> float:
        """Position vega per 1% vol: quantity x instrument vega (0 if not applicable)."""
        return self.Greeks()["vega"]

    @dag.computed
    def IsLong(self) -> bool:
        """True if this is a long position."""
        return self.Quantity() > 0

    @dag.computed
    def IsShort(self) -> bool:
        """True if this is a short position."""
        return self.Quantity() < 0

    @dag.computed
    def IsFlat(self) -> bool:
        """True if position is flat (zero quantity)."""
        return self.Quantity() == 0

    @dag.computed
    def AbsQuantity(self) -> int:
        """Absolute quantity (unsigned)."""
        return abs(self.Quantity())

    @dag.computed
    def Side(self) -> str:
        """Position side: 'LONG', 'SHORT', or 'FLAT'."""
        if self.Quantity() > 0:
            return "LONG"
        elif self.Quantity() < 0:
            return "SHORT"
        else:
            return "FLAT"
