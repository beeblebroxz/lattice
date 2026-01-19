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

    @dag.computed(dag.Input)
    def Underlying(self) -> str:
        """Underlying asset identifier."""
        return ""

    @dag.computed(dag.Input)
    def Strike(self) -> float:
        """Option strike price."""
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        """Current underlying price."""
        return 100.0

    @dag.computed(dag.Input)
    def Volatility(self) -> float:
        """Implied volatility (annualized, as decimal e.g., 0.20 = 20%)."""
        return 0.20

    @dag.computed(dag.Input)
    def Rate(self) -> float:
        """Risk-free interest rate (annualized, as decimal)."""
        return 0.05

    @dag.computed(dag.Input)
    def Dividend(self) -> float:
        """Continuous dividend yield (annualized, as decimal)."""
        return 0.0

    @dag.computed(dag.Input)
    def TimeToExpiry(self) -> float:
        """Time to expiration in years."""
        return 1.0

    @dag.computed(dag.Input)
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
