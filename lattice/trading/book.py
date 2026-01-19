"""Book as dag.Model class.

A Book represents an entity that holds positions - it could be a
trading desk, customer account, or internal book.
"""

from typing import Optional, List, TYPE_CHECKING
import dag

from .position import Position

if TYPE_CHECKING:
    from .system import TradingSystem


class Book(dag.Model):
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

        print(book.TotalPnL())        # Sum of position P&Ls
        print(book.GrossExposure())   # Sum of absolute values
        print(book.NetExposure())     # Net market value
    """

    # ==================== Inputs ====================

    @dag.computed(dag.Input)
    def BookId(self) -> str:
        """Unique book identifier."""
        return ""

    @dag.computed(dag.Input)
    def Name(self) -> str:
        """Human-readable book name."""
        return ""

    @dag.computed(dag.Input)
    def BookType(self) -> str:
        """Book type: 'trading', 'customer', 'house', or 'hedge'."""
        return "trading"

    @dag.computed(dag.Input)
    def ParentBookId(self) -> str:
        """Parent book ID for hierarchy roll-up (optional)."""
        return ""

    # Internal: reference to the trading system (set by TradingSystem)
    _system: Optional["TradingSystem"] = None
    _positions: List[Position] = []

    def _set_system(self, system: "TradingSystem") -> None:
        """Set the trading system reference (called by TradingSystem)."""
        self._system = system

    def _set_positions(self, positions: List[Position]) -> None:
        """Update positions list (called by TradingSystem)."""
        self._positions = positions

    # ==================== Computed from positions ====================

    @dag.computed
    def DisplayName(self) -> str:
        """Display name (Name if set, otherwise BookId)."""
        name = self.Name()
        return name if name else self.BookId()

    @dag.computed
    def Positions(self) -> List[Position]:
        """All positions for this book.

        Positions are aggregated from trades by the TradingSystem.
        """
        return self._positions

    @dag.computed
    def TotalPnL(self) -> float:
        """Sum of unrealized P&L across all positions."""
        return sum(pos.UnrealizedPnL() for pos in self.Positions())

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
