"""Option instruments."""

import dag
from .base import Instrument
from ..models.blackscholes import (
    black_scholes_price,
    black_scholes_delta,
    black_scholes_gamma,
    black_scholes_vega,
    black_scholes_theta,
    black_scholes_rho,
)


class VanillaOption(Instrument):
    """
    European vanilla option with Black-Scholes pricing.

    Example:
        option = VanillaOption()
        option.Strike.set(100.0)
        option.Spot.set(105.0)
        option.Volatility.set(0.20)
        option.Rate.set(0.05)
        option.TimeToExpiry.set(0.5)
        option.IsCall.set(True)

        print(option.Price())   # Black-Scholes price
        print(option.Delta())   # Delta
    """

    # ==================== Inputs ====================
    # Contract terms are Persisted (saved to DB)
    # Market data is Input | Overridable (transient, re-fetched on load)

    @dag.computed(dag.Persisted)
    def Underlying(self) -> str:
        """Underlying asset identifier."""
        return ""

    @dag.computed(dag.Persisted)
    def Strike(self) -> float:
        """Option strike price."""
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        """Current underlying price (market data - not persisted)."""
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)
    def Volatility(self) -> float:
        """Implied volatility (market data - not persisted)."""
        return 0.20

    @dag.computed(dag.Input | dag.Overridable)
    def Rate(self) -> float:
        """Risk-free interest rate (market data - not persisted)."""
        return 0.05

    @dag.computed(dag.Input | dag.Overridable)
    def Dividend(self) -> float:
        """Continuous dividend yield (market data - not persisted)."""
        return 0.0

    @dag.computed(dag.Persisted | dag.Overridable)
    def TimeToExpiry(self) -> float:
        """Time to expiration in years (persisted and overridable for scenarios)."""
        return 1.0

    @dag.computed(dag.Persisted)
    def IsCall(self) -> bool:
        """True for call option, False for put option."""
        return True

    # ==================== Pricing ====================

    @dag.computed
    def Price(self) -> float:
        """Option price using Black-Scholes model."""
        return black_scholes_price(
            spot=self.Spot(),
            strike=self.Strike(),
            rate=self.Rate(),
            dividend=self.Dividend(),
            volatility=self.Volatility(),
            time_to_expiry=self.TimeToExpiry(),
            is_call=self.IsCall(),
        )

    @dag.computed
    def IntrinsicValue(self) -> float:
        """Intrinsic value of the option."""
        if self.IsCall():
            return max(0.0, self.Spot() - self.Strike())
        else:
            return max(0.0, self.Strike() - self.Spot())

    @dag.computed
    def TimeValue(self) -> float:
        """Time value (extrinsic value) of the option."""
        return self.Price() - self.IntrinsicValue()

    # ==================== Greeks ====================

    @dag.computed
    def Delta(self) -> float:
        """
        Delta - rate of change of option price with respect to underlying price.

        Range: 0 to 1 for calls, -1 to 0 for puts.
        """
        return black_scholes_delta(
            spot=self.Spot(),
            strike=self.Strike(),
            rate=self.Rate(),
            dividend=self.Dividend(),
            volatility=self.Volatility(),
            time_to_expiry=self.TimeToExpiry(),
            is_call=self.IsCall(),
        )

    @dag.computed
    def Gamma(self) -> float:
        """
        Gamma - rate of change of delta with respect to underlying price.

        Always positive for both calls and puts.
        """
        return black_scholes_gamma(
            spot=self.Spot(),
            strike=self.Strike(),
            rate=self.Rate(),
            dividend=self.Dividend(),
            volatility=self.Volatility(),
            time_to_expiry=self.TimeToExpiry(),
        )

    @dag.computed
    def Vega(self) -> float:
        """
        Vega - rate of change of option price with respect to volatility.

        Expressed per 1% (0.01) change in volatility.
        """
        return black_scholes_vega(
            spot=self.Spot(),
            strike=self.Strike(),
            rate=self.Rate(),
            dividend=self.Dividend(),
            volatility=self.Volatility(),
            time_to_expiry=self.TimeToExpiry(),
        )

    @dag.computed
    def Theta(self) -> float:
        """
        Theta - rate of change of option price with respect to time.

        Expressed per day. Usually negative for long options (time decay).
        """
        return black_scholes_theta(
            spot=self.Spot(),
            strike=self.Strike(),
            rate=self.Rate(),
            dividend=self.Dividend(),
            volatility=self.Volatility(),
            time_to_expiry=self.TimeToExpiry(),
            is_call=self.IsCall(),
        )

    @dag.computed
    def Rho(self) -> float:
        """
        Rho - rate of change of option price with respect to interest rate.

        Expressed per 1% (0.01) change in rate.
        """
        return black_scholes_rho(
            spot=self.Spot(),
            strike=self.Strike(),
            rate=self.Rate(),
            dividend=self.Dividend(),
            volatility=self.Volatility(),
            time_to_expiry=self.TimeToExpiry(),
            is_call=self.IsCall(),
        )

    # ==================== Instrument Interface ====================

    @dag.computed
    def Summary(self) -> str:
        """Summary of key option parameters: K={strike} S={spot} {C/P}."""
        option_type = "C" if self.IsCall() else "P"
        return f"K={self.Strike():.0f} S={self.Spot():.0f} {option_type}"

    @dag.computed
    def MarketValue(self) -> float:
        """Market value of the option (same as Price)."""
        return self.Price()
