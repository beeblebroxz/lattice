"""Position as dag.Model class.

A Position represents a holding in a single instrument for a book.
"""

import dag


class Position(dag.Model):
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

    @dag.computed(dag.Input)
    def Symbol(self) -> str:
        """Instrument symbol."""
        return ""

    @dag.computed(dag.Input)
    def BookId(self) -> str:
        """Book ID this position belongs to."""
        return ""

    @dag.computed(dag.Input)
    def Quantity(self) -> int:
        """Position quantity. Positive = long, negative = short."""
        return 0

    @dag.computed(dag.Input)
    def AvgPrice(self) -> float:
        """Average entry price."""
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

    @dag.computed
    def MarketValue(self) -> float:
        """Current market value (signed)."""
        return self.Quantity() * self.MarketPrice()

    @dag.computed
    def UnrealizedPnL(self) -> float:
        """Unrealized P&L.

        = MarketValue - (Quantity * AvgPrice)
        """
        return self.MarketValue() - (self.Quantity() * self.AvgPrice())

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
