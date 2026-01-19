"""Trade as dag.Model class.

A Trade represents a transaction between two books (buyer and seller).
"""

from datetime import datetime
import dag


class Trade(dag.Model):
    """A single trade - transaction between two books.

    A trade represents a transfer of an instrument from seller to buyer
    at a specified price. Both parties get mirror-image positions.

    Example:
        trade = Trade()
        trade.Symbol.set("AAPL_C_150")
        trade.Quantity.set(10)
        trade.Price.set(5.25)
        trade.BuyerBookId.set("DESK_A")
        trade.SellerBookId.set("CUST_123")

        print(trade.Notional())    # 52.50
        trade.MarketPrice.set(6.00)
        print(trade.BuyerPnL())    # 7.50 (profit for buyer)
        print(trade.SellerPnL())   # -7.50 (loss for seller)
    """

    # ==================== Inputs ====================

    @dag.computed(dag.Input)
    def TradeId(self) -> int:
        """Unique trade identifier."""
        return 0

    @dag.computed(dag.Input)
    def Symbol(self) -> str:
        """Instrument symbol."""
        return ""

    @dag.computed(dag.Input)
    def Quantity(self) -> int:
        """Number of units traded (always positive)."""
        return 0

    @dag.computed(dag.Input)
    def Price(self) -> float:
        """Execution price."""
        return 0.0

    @dag.computed(dag.Input)
    def BuyerBookId(self) -> str:
        """Book ID of the buyer."""
        return ""

    @dag.computed(dag.Input)
    def SellerBookId(self) -> str:
        """Book ID of the seller."""
        return ""

    @dag.computed(dag.Input)
    def Timestamp(self) -> datetime:
        """Trade execution timestamp."""
        return datetime.now()

    @dag.computed(dag.Input | dag.Overridable)
    def MarketPrice(self) -> float:
        """Current market price for P&L calculation.

        Defaults to trade price. Override for mark-to-market.
        """
        return self.Price()

    # ==================== Computed ====================

    @dag.computed
    def Notional(self) -> float:
        """Total notional value at trade price."""
        return self.Quantity() * self.Price()

    @dag.computed
    def MarketValue(self) -> float:
        """Current market value."""
        return self.Quantity() * self.MarketPrice()

    @dag.computed
    def BuyerPnL(self) -> float:
        """P&L for the buyer (long position).

        Positive when market price > trade price.
        """
        return (self.MarketPrice() - self.Price()) * self.Quantity()

    @dag.computed
    def SellerPnL(self) -> float:
        """P&L for the seller (short position).

        Positive when market price < trade price.
        """
        return (self.Price() - self.MarketPrice()) * self.Quantity()
