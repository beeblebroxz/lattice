"""Equity instruments."""

import math
import dag
from .base import Instrument


class Stock(Instrument):
    """
    Equity/Stock instrument with dividend yield.

    Computes forward price and present value of dividends.

    Example:
        stock = Stock()
        stock.Spot.set(100.0)
        stock.DividendYield.set(0.02)  # 2% annual dividend
        stock.Rate.set(0.05)
        stock.TimeToExpiry.set(1.0)

        print(stock.ForwardPrice())  # Forward price for delivery in 1 year
        print(stock.DividendPV())    # PV of dividends over the period
    """

    # ==================== Inputs ====================
    # Identity fields are Persisted (saved to DB)
    # Market data is Input | Overridable (transient, re-fetched on load)

    @dag.computed(dag.Persisted)
    def Symbol(self) -> str:
        """Stock ticker symbol."""
        return ""

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        """Current stock price (market data - not persisted)."""
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)
    def DividendYield(self) -> float:
        """Continuous dividend yield (market data - not persisted)."""
        return 0.0

    @dag.computed(dag.Input | dag.Overridable)
    def Rate(self) -> float:
        """Risk-free interest rate (market data - not persisted)."""
        return 0.05

    @dag.computed(dag.Input)
    def TimeToExpiry(self) -> float:
        """Time horizon in years (for forward calculations)."""
        return 1.0

    # ==================== Computed Values ====================

    @dag.computed
    def ForwardPrice(self) -> float:
        """
        Forward price for delivery at TimeToExpiry.

        F = S * e^((r - q) * T)

        where:
            S = spot price
            r = risk-free rate
            q = dividend yield
            T = time to expiry
        """
        S = self.Spot()
        r = self.Rate()
        q = self.DividendYield()
        T = self.TimeToExpiry()
        return S * math.exp((r - q) * T)

    @dag.computed
    def DividendPV(self) -> float:
        """
        Present value of dividends over the time horizon.

        PV(div) = S * (1 - e^(-q * T))

        This represents the value of dividends foregone by holding
        a forward instead of the stock.
        """
        S = self.Spot()
        q = self.DividendYield()
        T = self.TimeToExpiry()
        if q == 0:
            return 0.0
        return S * (1 - math.exp(-q * T))

    @dag.computed
    def CarryCost(self) -> float:
        """
        Cost of carry (financing cost minus dividend income).

        Carry = S * (e^((r - q) * T) - 1)
        """
        return self.ForwardPrice() - self.Spot()

    @dag.computed
    def DiscountFactor(self) -> float:
        """Discount factor for the time horizon."""
        return math.exp(-self.Rate() * self.TimeToExpiry())

    @dag.computed
    def PresentValue(self) -> float:
        """
        Present value of receiving the stock at expiry.

        PV = F * e^(-r * T) = S * e^(-q * T)
        """
        return self.ForwardPrice() * self.DiscountFactor()
