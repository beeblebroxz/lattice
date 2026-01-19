"""Derivative instruments (forwards, futures)."""

import math
import dag
from .base import Instrument


class Forward(Instrument):
    """
    Forward contract on an underlying asset.

    A forward is an agreement to buy/sell an asset at a future date
    for a price agreed today.

    Example:
        forward = Forward()
        forward.Spot.set(100.0)
        forward.Rate.set(0.05)
        forward.DividendYield.set(0.02)
        forward.TimeToExpiry.set(0.5)

        print(forward.ForwardPrice())  # Fair forward price

        # Value an existing forward with a contract price
        forward.ContractPrice.set(102.0)
        print(forward.Value())         # Current value of the forward
    """

    # ==================== Inputs ====================
    # Contract terms are Persisted (saved to DB)
    # Market data is Input | Overridable (transient, re-fetched on load)

    @dag.computed(dag.Persisted)
    def Underlying(self) -> str:
        """Underlying asset identifier."""
        return ""

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        """Current spot price of the underlying (market data - not persisted)."""
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)
    def Rate(self) -> float:
        """Risk-free interest rate (market data - not persisted)."""
        return 0.05

    @dag.computed(dag.Input | dag.Overridable)
    def DividendYield(self) -> float:
        """Dividend yield or convenience yield (market data - not persisted)."""
        return 0.0

    @dag.computed(dag.Input | dag.Overridable)
    def StorageCost(self) -> float:
        """Storage cost rate for commodities (market data - not persisted)."""
        return 0.0

    @dag.computed(dag.Persisted)
    def TimeToExpiry(self) -> float:
        """Time to delivery/expiry in years."""
        return 1.0

    @dag.computed(dag.Persisted)
    def ContractPrice(self) -> float:
        """Contracted forward price (for valuing existing forwards)."""
        return 0.0

    @dag.computed(dag.Persisted)
    def IsLong(self) -> bool:
        """True if long the forward (agree to buy), False if short (agree to sell)."""
        return True

    @dag.computed(dag.Persisted)
    def ContractSize(self) -> float:
        """Number of units in the contract."""
        return 1.0

    # ==================== Computed Values ====================

    @dag.computed
    def CostOfCarry(self) -> float:
        """
        Net cost of carry rate.

        b = r - q + s

        where:
            r = risk-free rate
            q = dividend/convenience yield
            s = storage cost
        """
        return self.Rate() - self.DividendYield() + self.StorageCost()

    @dag.computed
    def ForwardPrice(self) -> float:
        """
        Fair forward price (no-arbitrage price).

        F = S * e^(b * T)

        where:
            S = spot price
            b = cost of carry
            T = time to expiry
        """
        S = self.Spot()
        b = self.CostOfCarry()
        T = self.TimeToExpiry()
        return S * math.exp(b * T)

    @dag.computed
    def DiscountFactor(self) -> float:
        """Discount factor for time to expiry."""
        return math.exp(-self.Rate() * self.TimeToExpiry())

    @dag.computed
    def Value(self) -> float:
        """
        Current value of an existing forward contract.

        V = (F - K) * e^(-r * T) * size * sign

        where:
            F = current forward price
            K = contracted price
            r = risk-free rate
            T = time to expiry
            sign = +1 for long, -1 for short
        """
        F = self.ForwardPrice()
        K = self.ContractPrice()
        df = self.DiscountFactor()
        size = self.ContractSize()
        sign = 1 if self.IsLong() else -1

        return (F - K) * df * size * sign

    @dag.computed
    def Delta(self) -> float:
        """
        Delta - sensitivity of forward value to spot price.

        For a forward: Delta = e^(-q * T) * sign
        """
        q = self.DividendYield()
        T = self.TimeToExpiry()
        sign = 1 if self.IsLong() else -1
        return math.exp(-q * T) * sign * self.ContractSize()

    @dag.computed
    def Gamma(self) -> float:
        """
        Gamma - rate of change of delta.

        For a forward: Gamma = 0 (linear payoff)
        """
        return 0.0

    @dag.computed
    def Theta(self) -> float:
        """
        Theta - time decay per day.

        For a forward contract with no optionality.
        """
        # dV/dT = S * b * e^((b-r)*T) for forward price
        # Simplified: negative of daily carry cost
        S = self.Spot()
        b = self.CostOfCarry()
        r = self.Rate()
        T = self.TimeToExpiry()
        sign = 1 if self.IsLong() else -1

        # Value decay per year
        annual_theta = -S * (b - r) * math.exp((b - r) * T)
        # Convert to per day
        return annual_theta / 365.0 * sign * self.ContractSize()

    @dag.computed
    def Rho(self) -> float:
        """
        Rho - sensitivity to interest rate (per 1% change).

        For a forward: affects both forward price and discounting.
        """
        # Approximate via finite difference
        r = self.Rate()
        T = self.TimeToExpiry()
        S = self.Spot()
        b = self.CostOfCarry()
        K = self.ContractPrice()
        sign = 1 if self.IsLong() else -1
        size = self.ContractSize()

        # Sensitivity: T * V + S * T * e^((b-r)*T)
        F = S * math.exp(b * T)
        df = math.exp(-r * T)
        value = (F - K) * df * size * sign

        # dV/dr per 1% = T * (K - F) * e^(-r*T) + T * S * e^(b*T) * e^(-r*T)
        # Simplified approximation:
        return -T * value * 0.01


class Future(Forward):
    """
    Futures contract (exchange-traded forward with daily settlement).

    Inherits from Forward but adds margin-related calculations.
    For most purposes, futures prices are approximately equal to forward
    prices (exact under constant interest rates).

    Example:
        future = Future()
        future.Spot.set(100.0)
        future.Rate.set(0.05)
        future.TimeToExpiry.set(0.25)
        future.ContractSize.set(100)  # 100 units per contract

        print(future.ForwardPrice())   # Theoretical futures price
        print(future.NotionalValue())  # Total notional value
    """

    @dag.computed(dag.Input | dag.Overridable)
    def InitialMargin(self) -> float:
        """Initial margin requirement per contract (market data - not persisted)."""
        return 0.0

    @dag.computed(dag.Input | dag.Overridable)
    def MaintenanceMargin(self) -> float:
        """Maintenance margin requirement per contract (market data - not persisted)."""
        return 0.0

    @dag.computed
    def NotionalValue(self) -> float:
        """Total notional value of the position."""
        return self.ForwardPrice() * self.ContractSize()

    @dag.computed
    def Leverage(self) -> float:
        """Leverage ratio (notional / margin)."""
        margin = self.InitialMargin()
        if margin == 0:
            return float('inf')
        return self.NotionalValue() / margin
