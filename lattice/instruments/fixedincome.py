"""Fixed income instruments."""

import math
import dag
from .base import Instrument


class Bond(Instrument):
    """
    Fixed coupon bond with duration, convexity, and yield calculations.

    Example:
        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.CouponRate.set(0.05)      # 5% annual coupon
        bond.Maturity.set(10.0)        # 10 years to maturity
        bond.YieldToMaturity.set(0.04) # 4% YTM
        bond.Frequency.set(2)          # Semi-annual payments

        print(bond.Price())            # Bond price
        print(bond.Duration())         # Macaulay duration
        print(bond.ModifiedDuration()) # Modified duration
        print(bond.Convexity())        # Convexity
    """

    # ==================== Inputs ====================
    # Contract terms are Persisted (saved to DB)
    # Market data (YieldToMaturity) is Input | Overridable (transient)

    @dag.computed(dag.Persisted)
    def Issuer(self) -> str:
        """Bond issuer identifier."""
        return ""

    @dag.computed(dag.Persisted)
    def FaceValue(self) -> float:
        """Face (par) value of the bond."""
        return 1000.0

    @dag.computed(dag.Persisted)
    def CouponRate(self) -> float:
        """Annual coupon rate (as decimal, e.g., 0.05 = 5%)."""
        return 0.05

    @dag.computed(dag.Persisted)
    def Maturity(self) -> float:
        """Time to maturity in years."""
        return 10.0

    @dag.computed(dag.Input | dag.Overridable)
    def YieldToMaturity(self) -> float:
        """Yield to maturity (market data - not persisted)."""
        return 0.05

    @dag.computed(dag.Persisted)
    def Frequency(self) -> int:
        """Coupon payment frequency per year (1=annual, 2=semi-annual, 4=quarterly)."""
        return 2

    # ==================== Computed Values ====================

    @dag.computed
    def CouponPayment(self) -> float:
        """Coupon payment per period."""
        return (self.CouponRate() * self.FaceValue()) / self.Frequency()

    @dag.computed
    def NumPeriods(self) -> int:
        """Total number of coupon periods."""
        return int(self.Maturity() * self.Frequency())

    @dag.computed
    def PeriodicYield(self) -> float:
        """Yield per coupon period."""
        return self.YieldToMaturity() / self.Frequency()

    @dag.computed
    def Price(self) -> float:
        """
        Bond price (present value of all cash flows).

        P = sum(C / (1 + y)^t) + FV / (1 + y)^n

        where:
            C = coupon payment per period
            y = periodic yield
            n = number of periods
            FV = face value
        """
        C = self.CouponPayment()
        y = self.PeriodicYield()
        n = self.NumPeriods()
        FV = self.FaceValue()

        if y == 0:
            # Special case: zero yield
            return C * n + FV

        # PV of coupon annuity + PV of face value
        pv_coupons = C * (1 - (1 + y) ** (-n)) / y
        pv_face = FV / ((1 + y) ** n)

        return pv_coupons + pv_face

    @dag.computed
    def CleanPrice(self) -> float:
        """Clean price (dirty price minus accrued interest)."""
        # For simplicity, assuming we're at a coupon date (no accrued interest)
        return self.Price()

    @dag.computed
    def CurrentYield(self) -> float:
        """Current yield (annual coupon / price)."""
        annual_coupon = self.CouponRate() * self.FaceValue()
        return annual_coupon / self.Price()

    @dag.computed
    def Duration(self) -> float:
        """
        Macaulay duration - weighted average time to receive cash flows.

        D = sum(t * PV(CF_t)) / Price

        Returns duration in years.
        """
        C = self.CouponPayment()
        y = self.PeriodicYield()
        n = self.NumPeriods()
        FV = self.FaceValue()
        freq = self.Frequency()

        if y == 0:
            # Special case: approximate
            total_cf = C * n + FV
            weighted = sum((t / freq) * C for t in range(1, n + 1))
            weighted += (n / freq) * FV
            return weighted / total_cf

        weighted_pv = 0.0
        for t in range(1, n + 1):
            pv = C / ((1 + y) ** t)
            weighted_pv += (t / freq) * pv

        # Add face value at maturity
        pv_face = FV / ((1 + y) ** n)
        weighted_pv += (n / freq) * pv_face

        return weighted_pv / self.Price()

    @dag.computed
    def ModifiedDuration(self) -> float:
        """
        Modified duration - price sensitivity to yield changes.

        MD = D / (1 + y/freq)

        Interpretation: For a 1% increase in yield, price decreases by MD%.
        """
        return self.Duration() / (1 + self.PeriodicYield())

    @dag.computed
    def Convexity(self) -> float:
        """
        Convexity - second derivative of price with respect to yield.

        Convexity = sum(t * (t+1) * PV(CF_t)) / (Price * (1+y)^2 * freq^2)

        Used to improve duration-based price change estimates.
        """
        C = self.CouponPayment()
        y = self.PeriodicYield()
        n = self.NumPeriods()
        FV = self.FaceValue()
        freq = self.Frequency()

        if y == 0:
            # Approximate for zero yield
            return self.Maturity() ** 2

        weighted_pv = 0.0
        for t in range(1, n + 1):
            pv = C / ((1 + y) ** t)
            weighted_pv += t * (t + 1) * pv

        # Add face value contribution
        pv_face = FV / ((1 + y) ** n)
        weighted_pv += n * (n + 1) * pv_face

        return weighted_pv / (self.Price() * ((1 + y) ** 2) * (freq ** 2))

    @dag.computed
    def DV01(self) -> float:
        """
        Dollar value of a basis point (DV01).

        The change in bond price for a 1 basis point (0.01%) change in yield.
        """
        return self.ModifiedDuration() * self.Price() * 0.0001

    @dag.computed
    def PriceChange(self) -> float:
        """
        Estimated price change for a 1% yield increase using duration and convexity.

        dP/P = -MD * dy + 0.5 * Convexity * dy^2
        """
        dy = 0.01  # 1% yield change
        md = self.ModifiedDuration()
        conv = self.Convexity()

        # Percentage change
        pct_change = -md * dy + 0.5 * conv * (dy ** 2)
        return pct_change * self.Price()

    # ==================== Instrument Interface ====================

    @dag.computed
    def Summary(self) -> str:
        """Summary of key bond parameters: {coupon}% {maturity}Y."""
        return f"{self.CouponRate()*100:.0f}% {self.Maturity():.0f}Y"

    @dag.computed
    def MarketValue(self) -> float:
        """Market value of the bond (same as Price)."""
        return self.Price()
