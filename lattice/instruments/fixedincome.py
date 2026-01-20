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


class InterestRateSwap(Instrument):
    """
    Interest Rate Swap instrument.

    A vanilla IRS exchanges fixed rate payments for floating rate payments.
    The notional principal is not exchanged.

    Example:
        swap = InterestRateSwap()
        swap.Notional.set(10_000_000.0)   # $10M notional
        swap.FixedRate.set(0.03)           # 3% fixed rate
        swap.Maturity.set(5.0)             # 5 years to maturity
        swap.Frequency.set(4)              # Quarterly payments
        swap.IsPayer.set(True)             # Pay fixed, receive floating

        swap.DiscountRate.set(0.035)       # Discount rate
        swap.FloatingRate.set(0.025)       # Current floating rate

        print(swap.NPV())                   # Net present value
        print(swap.DV01())                  # Dollar value of 1bp
        print(swap.ParSwapRate())           # Fair fixed rate
    """

    # ==================== Contract Terms (Persisted) ====================

    @dag.computed(dag.Persisted)
    def Notional(self) -> float:
        """Notional principal amount (not exchanged)."""
        return 1_000_000.0

    @dag.computed(dag.Persisted)
    def FixedRate(self) -> float:
        """Fixed leg rate (annual, as decimal)."""
        return 0.03

    @dag.computed(dag.Persisted)
    def Maturity(self) -> float:
        """Time to maturity in years."""
        return 5.0

    @dag.computed(dag.Persisted)
    def Frequency(self) -> int:
        """Payment frequency per year (1=annual, 2=semi, 4=quarterly)."""
        return 4

    @dag.computed(dag.Persisted)
    def IsPayer(self) -> bool:
        """True = pay fixed (receive floating), False = receive fixed."""
        return True

    # ==================== Market Data (Input | Overridable) ====================

    @dag.computed(dag.Input | dag.Overridable)
    def FloatingRate(self) -> float:
        """Current floating rate (e.g., SOFR)."""
        return 0.025

    @dag.computed(dag.Input | dag.Overridable)
    def DiscountRate(self) -> float:
        """Discount rate for PV calculations."""
        return 0.03

    @dag.computed(dag.Input | dag.Overridable)
    def FloatingSpread(self) -> float:
        """Spread over the floating index."""
        return 0.0

    # Alias for risk module compatibility (DV01 detection)
    @dag.computed(dag.Input | dag.Overridable)
    def YieldToMaturity(self) -> float:
        """Alias for DiscountRate (risk module compatibility)."""
        return self.DiscountRate()

    # ==================== Intermediate Calculations ====================

    @dag.computed
    def NumPeriods(self) -> int:
        """Total number of payment periods."""
        return int(self.Maturity() * self.Frequency())

    @dag.computed
    def PeriodicDiscountRate(self) -> float:
        """Discount rate per period."""
        return self.DiscountRate() / self.Frequency()

    @dag.computed
    def PeriodicFixedRate(self) -> float:
        """Fixed rate per period."""
        return self.FixedRate() / self.Frequency()

    @dag.computed
    def PeriodicFloatingRate(self) -> float:
        """Floating rate per period (including spread)."""
        return (self.FloatingRate() + self.FloatingSpread()) / self.Frequency()

    @dag.computed
    def FixedPayment(self) -> float:
        """Fixed leg payment per period."""
        return self.Notional() * self.PeriodicFixedRate()

    @dag.computed
    def FloatingPayment(self) -> float:
        """Estimated floating payment per period."""
        return self.Notional() * self.PeriodicFloatingRate()

    # ==================== Valuation ====================

    @dag.computed
    def Annuity(self) -> float:
        """
        Annuity factor (sum of discount factors).

        Annuity = sum_{t=1}^{n} [1 / (1 + r)^t]
        """
        r = self.PeriodicDiscountRate()
        n = self.NumPeriods()

        if r == 0:
            return float(n)

        return (1 - (1 + r) ** (-n)) / r

    @dag.computed
    def FixedLegPV(self) -> float:
        """
        Present value of the fixed leg.

        PV_fixed = FixedPayment * Annuity
        """
        return self.FixedPayment() * self.Annuity()

    @dag.computed
    def FloatingLegPV(self) -> float:
        """
        Present value of the floating leg.

        The floating leg (coupons only, no principal exchange) is valued as:
        FloatingLegPV = Notional * (1 - DF_n)

        This is derived from replication:
        - Long a floating rate note (prices at par = Notional at reset)
        - Short a zero-coupon bond (prices at Notional * DF_n)

        For off-reset dates, this is a simplification. A full implementation
        would account for accrued interest to the next reset.
        """
        r = self.PeriodicDiscountRate()
        n = self.NumPeriods()
        df_n = 1 / ((1 + r) ** n)
        return self.Notional() * (1 - df_n)

    @dag.computed
    def NPV(self) -> float:
        """
        Net Present Value of the swap.

        Payer swap: NPV = FloatingLegPV - FixedLegPV
        Receiver swap: NPV = FixedLegPV - FloatingLegPV
        """
        fixed_pv = self.FixedLegPV()
        float_pv = self.FloatingLegPV()

        if self.IsPayer():
            return float_pv - fixed_pv
        else:
            return fixed_pv - float_pv

    @dag.computed
    def Price(self) -> float:
        """Alias for NPV (risk module compatibility)."""
        return self.NPV()

    @dag.computed
    def ParSwapRate(self) -> float:
        """
        The fixed rate that makes the swap value zero (fair rate).

        ParRate = (1 - DF_n) / Annuity * Frequency

        where DF_n = final discount factor
        """
        r = self.PeriodicDiscountRate()
        n = self.NumPeriods()
        freq = self.Frequency()

        df_n = 1 / ((1 + r) ** n)
        annuity = self.Annuity()

        if annuity == 0:
            return 0.0

        return (1 - df_n) / annuity * freq

    # ==================== Risk Metrics ====================

    @dag.computed
    def DV01(self) -> float:
        """
        Dollar Value of a Basis Point.

        The change in NPV for a 1bp parallel shift in rates.
        DV01 ≈ Notional * Annuity * 0.0001 / Frequency
        """
        return abs(self.Notional() * self.Annuity() * 0.0001 / self.Frequency())

    @dag.computed
    def PV01(self) -> float:
        """
        Present Value of 01: NPV change for 1bp fixed rate change.

        PV01 = Notional * Annuity / Frequency * 0.0001
        """
        return self.Notional() * self.Annuity() / self.Frequency() * 0.0001

    @dag.computed
    def Duration(self) -> float:
        """
        Modified duration of the swap.

        Approximate weighted average life of the swap.
        """
        if abs(self.NPV()) < 0.01:  # Near-par swap
            # Duration is roughly half the maturity for an ATM swap
            return self.Maturity() / 2

        # For non-par swaps, use DV01-based calculation
        npv = self.NPV()
        if npv == 0:
            return self.Maturity() / 2
        return self.DV01() / (abs(npv) * 0.0001)

    # ==================== Instrument Interface ====================

    @dag.computed
    def Summary(self) -> str:
        """Summary: {rate}% {maturity}Y {Payer/Receiver}."""
        direction = "Payer" if self.IsPayer() else "Receiver"
        return f"{self.FixedRate()*100:.2f}% {self.Maturity():.0f}Y {direction}"

    @dag.computed
    def MarketValue(self) -> float:
        """Market value of the swap."""
        return self.NPV()
