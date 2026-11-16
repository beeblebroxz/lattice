"""Book as dag.Model class.

A Book represents an entity that holds positions - it could be a
trading desk, customer account, or internal book.
"""

from typing import Optional, List, TYPE_CHECKING
import dag

from lattice.store.storable import Storable

from .position import Position

if TYPE_CHECKING:
    from .system import TradingSystem

# Instrument input each Greek requires; positions whose instrument lacks it skip.
_GREEK_REQUIRES = {"delta": "Spot", "vega": "Volatility", "gamma": "Spot"}


class Book(Storable, dag.Model):
    """A book holding positions with aggregated P&L.

    A Book represents an entity that holds positions - it could be a
    trading desk, customer account, or internal book. Books are
    populated from trades executed in a TradingSystem.

    Example:
        book = Book()
        book.BookId.set("DESK_OPTIONS")
        book.Name.set("Options Trading Desk")
        book.BookType.set("trading")

        # Positions are managed by TradingSystem
        # Access via book.Positions() after system.trade()

        print(book.TotalPnL())        # Realized + unrealized P&L
        print(book.GrossExposure())   # Sum of absolute values
        print(book.NetExposure())     # Net market value
    """

    # ==================== Inputs ====================

    @dag.computed(dag.Persisted)
    def BookId(self) -> str:
        """Unique book identifier."""
        return ""

    @dag.computed(dag.Persisted)
    def Name(self) -> str:
        """Human-readable book name."""
        return ""

    @dag.computed(dag.Persisted)
    def BookType(self) -> str:
        """Book type: 'trading', 'customer', 'house', or 'hedge'."""
        return "trading"

    @dag.computed(dag.Persisted)
    def ParentBookId(self) -> str:
        """Parent book ID for hierarchy roll-up (optional)."""
        return ""

    @dag.computed(dag.Input)
    def AllPositions(self) -> List[Position]:
        """Every position this book has held, including ones now flat.

        Maintained by TradingSystem. Flat positions stay here because they
        still carry realized P&L. It is a dag input, so everything computed
        from it updates when the system adds a position.
        """
        return []

    # Internal: reference to the trading system (set by TradingSystem)
    _system: Optional["TradingSystem"] = None

    def _set_system(self, system: "TradingSystem") -> None:
        """Set the trading system reference (called by TradingSystem)."""
        self._system = system

    def _set_positions(self, positions: List[Position]) -> None:
        """Replace the position list (called by TradingSystem)."""
        self.AllPositions.set(list(positions))

    # ==================== Computed from positions ====================

    @dag.computed
    def DisplayName(self) -> str:
        """Display name (Name if set, otherwise BookId)."""
        name = self.Name()
        return name if name else self.BookId()

    @dag.computed
    def Positions(self) -> List[Position]:
        """Open (non-flat) positions for this book.

        Positions are aggregated from trades by the TradingSystem.
        """
        return [pos for pos in self.AllPositions() if not pos.IsFlat()]

    @dag.computed
    def UnrealizedPnL(self) -> float:
        """Sum of unrealized P&L across open positions."""
        return sum(pos.UnrealizedPnL() for pos in self.Positions())

    @dag.computed
    def RealizedPnL(self) -> float:
        """Sum of realized P&L across all positions, including closed ones."""
        return sum(pos.RealizedPnL() for pos in self.AllPositions())

    @dag.computed
    def TotalPnL(self) -> float:
        """Realized plus unrealized P&L."""
        return self.RealizedPnL() + self.UnrealizedPnL()

    @dag.computed
    def GrossExposure(self) -> float:
        """Sum of absolute market values (total exposure)."""
        return sum(abs(pos.MarketValue()) for pos in self.Positions())

    @dag.computed
    def NetExposure(self) -> float:
        """Net market value (longs - shorts)."""
        return sum(pos.MarketValue() for pos in self.Positions())

    @dag.computed
    def NumPositions(self) -> int:
        """Number of non-flat positions."""
        return len([p for p in self.Positions() if not p.IsFlat()])

    @dag.computed
    def NumLongPositions(self) -> int:
        """Number of long positions."""
        return len([p for p in self.Positions() if p.IsLong()])

    @dag.computed
    def NumShortPositions(self) -> int:
        """Number of short positions."""
        return len([p for p in self.Positions() if p.IsShort()])

    @dag.computed
    def LongExposure(self) -> float:
        """Total market value of long positions."""
        return sum(pos.MarketValue() for pos in self.Positions() if pos.IsLong())

    @dag.computed
    def ShortExposure(self) -> float:
        """Total market value of short positions (as positive number)."""
        return abs(sum(pos.MarketValue() for pos in self.Positions() if pos.IsShort()))

    @dag.computed
    def Delta(self) -> float:
        """Aggregate delta: sum of quantity * instrument delta over linked positions."""
        return self._book_greek("delta", self.Positions())

    @dag.computed
    def Vega(self) -> float:
        """Aggregate vega across linked positions."""
        return self._book_greek("vega", self.Positions())

    @dag.computed
    def Gamma(self) -> float:
        """Aggregate gamma across linked positions."""
        return self._book_greek("gamma", self.Positions())

    def _book_greek(self, name: str, positions: List[Position]) -> float:
        """Quantity-weighted sum of a numerical Greek over linked positions.

        Positions with no linked instrument, or whose instrument lacks the
        required input (e.g. a bond has no Spot), contribute nothing.

        The sensitivity is taken on the instrument's MarketValue, which is
        what the position is marked at, so the aggregate is the sensitivity
        of the book's own value.
        """
        from lattice.risk import sensitivities

        required = _GREEK_REQUIRES.get(name)
        if required is None:
            raise ValueError(f"Unknown greek: {name!r}")
        fn = getattr(sensitivities, name)
        total = 0.0
        for pos in positions:
            inst = pos.LinkedInstrument()
            if inst is None or not hasattr(inst, required):
                continue
            total += pos.Quantity() * fn(inst, output_name="MarketValue")
        return total
