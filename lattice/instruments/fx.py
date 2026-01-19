"""Foreign exchange instruments."""

import math
import dag
from .base import Instrument


class FXPair(Instrument):
    """
    Foreign exchange currency pair.

    Follows the convention BASE/QUOTE where the spot rate is
    the number of QUOTE currency units per BASE currency unit.

    Example (EUR/USD):
        fx = FXPair()
        fx.BaseCurrency.set("EUR")
        fx.QuoteCurrency.set("USD")
        fx.Spot.set(1.10)           # 1 EUR = 1.10 USD
        fx.BaseRate.set(0.04)       # EUR interest rate
        fx.QuoteRate.set(0.05)      # USD interest rate
        fx.TimeToExpiry.set(1.0)    # 1 year

        print(fx.ForwardRate())     # Forward rate for 1Y
        print(fx.ForwardPoints())   # Forward points (pips)
        print(fx.SwapPoints())      # Swap points
    """

    # ==================== Inputs ====================

    @dag.computed(dag.Input)
    def BaseCurrency(self) -> str:
        """Base currency (the currency being bought/sold)."""
        return "EUR"

    @dag.computed(dag.Input)
    def QuoteCurrency(self) -> str:
        """Quote currency (the currency used to express the price)."""
        return "USD"

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        """Spot exchange rate (quote per base)."""
        return 1.0

    @dag.computed(dag.Input | dag.Overridable)
    def BaseRate(self) -> float:
        """Interest rate in the base currency (annualized, as decimal)."""
        return 0.05

    @dag.computed(dag.Input | dag.Overridable)
    def QuoteRate(self) -> float:
        """Interest rate in the quote currency (annualized, as decimal)."""
        return 0.05

    @dag.computed(dag.Input)
    def TimeToExpiry(self) -> float:
        """Time to delivery in years."""
        return 1.0

    @dag.computed(dag.Input)
    def BaseNotional(self) -> float:
        """Notional amount in base currency."""
        return 1000000.0  # 1 million

    # ==================== Computed Values ====================

    @dag.computed
    def PairName(self) -> str:
        """Currency pair name (e.g., 'EUR/USD')."""
        return f"{self.BaseCurrency()}/{self.QuoteCurrency()}"

    @dag.computed
    def ForwardRate(self) -> float:
        """
        Forward exchange rate using covered interest rate parity.

        F = S * e^((r_quote - r_base) * T)

        where:
            S = spot rate
            r_quote = quote currency interest rate
            r_base = base currency interest rate
            T = time to expiry
        """
        S = self.Spot()
        r_base = self.BaseRate()
        r_quote = self.QuoteRate()
        T = self.TimeToExpiry()
        return S * math.exp((r_quote - r_base) * T)

    @dag.computed
    def ForwardPoints(self) -> float:
        """
        Forward points (forward - spot).

        Expressed in quote currency units.
        Positive when quote rate > base rate (forward premium).
        Negative when quote rate < base rate (forward discount).
        """
        return self.ForwardRate() - self.Spot()

    @dag.computed
    def ForwardPointsPips(self) -> float:
        """
        Forward points in pips (1 pip = 0.0001 for most pairs).

        Note: For JPY pairs, 1 pip = 0.01
        """
        points = self.ForwardPoints()
        # Assume standard 4 decimal places (not JPY pairs)
        return points * 10000

    @dag.computed
    def SwapPoints(self) -> float:
        """
        Swap points (same as forward points, common FX terminology).
        """
        return self.ForwardPoints()

    @dag.computed
    def QuoteNotional(self) -> float:
        """Notional amount in quote currency (at spot)."""
        return self.BaseNotional() * self.Spot()

    @dag.computed
    def ForwardValue(self) -> float:
        """Value of base notional at the forward rate."""
        return self.BaseNotional() * self.ForwardRate()

    @dag.computed
    def CarryReturn(self) -> float:
        """
        Carry return - interest differential earned over the period.

        For a long base / short quote position:
        Carry = (r_base - r_quote) * T
        """
        return (self.BaseRate() - self.QuoteRate()) * self.TimeToExpiry()

    @dag.computed
    def RollCost(self) -> float:
        """
        Roll cost/income for holding the position.

        Positive = you pay to roll (quote rate > base rate)
        Negative = you earn to roll (base rate > quote rate)
        """
        return -self.CarryReturn() * self.QuoteNotional()

    @dag.computed
    def ImpliedBaseRate(self) -> float:
        """
        Implied base rate from spot, forward, and quote rate.

        Useful when you know the forward and want to back out rates.

        r_base = r_quote - ln(F/S) / T
        """
        S = self.Spot()
        F = self.ForwardRate()
        r_quote = self.QuoteRate()
        T = self.TimeToExpiry()

        if T == 0 or F == 0 or S == 0:
            return 0.0

        return r_quote - math.log(F / S) / T

    @dag.computed
    def InverseSpot(self) -> float:
        """Inverse spot rate (for QUOTE/BASE)."""
        if self.Spot() == 0:
            return 0.0
        return 1.0 / self.Spot()

    @dag.computed
    def InverseForward(self) -> float:
        """Inverse forward rate (for QUOTE/BASE)."""
        if self.ForwardRate() == 0:
            return 0.0
        return 1.0 / self.ForwardRate()


class FXForward(FXPair):
    """
    FX Forward contract - agreement to exchange currencies at a future date.

    Example:
        fwd = FXForward()
        fwd.Spot.set(1.10)
        fwd.BaseRate.set(0.04)
        fwd.QuoteRate.set(0.05)
        fwd.TimeToExpiry.set(0.5)
        fwd.ContractRate.set(1.105)  # Agreed forward rate
        fwd.BaseNotional.set(1000000)
        fwd.IsLongBase.set(True)     # Buying EUR, selling USD

        print(fwd.Value())           # Current value of the forward
    """

    @dag.computed(dag.Input)
    def ContractRate(self) -> float:
        """Contracted forward rate."""
        return 0.0

    @dag.computed(dag.Input)
    def IsLongBase(self) -> bool:
        """True if long base currency (buying base, selling quote)."""
        return True

    @dag.computed
    def Value(self) -> float:
        """
        Current value of the FX forward contract.

        V = (F - K) * Notional * DF_quote * sign

        where:
            F = current forward rate
            K = contract rate
            DF_quote = discount factor in quote currency
        """
        F = self.ForwardRate()
        K = self.ContractRate()
        notional = self.BaseNotional()
        r_quote = self.QuoteRate()
        T = self.TimeToExpiry()
        sign = 1 if self.IsLongBase() else -1

        df = math.exp(-r_quote * T)
        return (F - K) * notional * df * sign

    @dag.computed
    def MarkToMarket(self) -> float:
        """Mark-to-market value (same as Value)."""
        return self.Value()

    @dag.computed
    def Delta(self) -> float:
        """
        Delta - sensitivity to spot rate changes.

        For FX forward: Delta = Notional * DF_base * sign
        """
        notional = self.BaseNotional()
        r_base = self.BaseRate()
        T = self.TimeToExpiry()
        sign = 1 if self.IsLongBase() else -1

        df = math.exp(-r_base * T)
        return notional * df * sign
