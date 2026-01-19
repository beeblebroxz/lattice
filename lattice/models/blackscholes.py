"""
Black-Scholes option pricing model.

Provides pricing and Greeks for European vanilla options.
"""

import math
from typing import Literal


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
) -> float:
    """Calculate d1 parameter for Black-Scholes."""
    if time_to_expiry <= 0 or volatility <= 0:
        return 0.0
    return (
        math.log(spot / strike)
        + (rate - dividend + 0.5 * volatility * volatility) * time_to_expiry
    ) / (volatility * math.sqrt(time_to_expiry))


def _d2(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
) -> float:
    """Calculate d2 parameter for Black-Scholes."""
    if time_to_expiry <= 0 or volatility <= 0:
        return 0.0
    return _d1(spot, strike, rate, dividend, volatility, time_to_expiry) - volatility * math.sqrt(time_to_expiry)


def black_scholes_price(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
    is_call: bool,
) -> float:
    """
    Calculate Black-Scholes option price.

    Args:
        spot: Current underlying price
        strike: Option strike price
        rate: Risk-free interest rate (annualized, as decimal)
        dividend: Continuous dividend yield (annualized, as decimal)
        volatility: Implied volatility (annualized, as decimal)
        time_to_expiry: Time to expiration in years
        is_call: True for call, False for put

    Returns:
        Option price
    """
    if time_to_expiry <= 0:
        # At expiry, return intrinsic value
        if is_call:
            return max(0.0, spot - strike)
        else:
            return max(0.0, strike - spot)

    d1 = _d1(spot, strike, rate, dividend, volatility, time_to_expiry)
    d2 = _d2(spot, strike, rate, dividend, volatility, time_to_expiry)

    discount = math.exp(-rate * time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)

    if is_call:
        return spot * dividend_discount * norm_cdf(d1) - strike * discount * norm_cdf(d2)
    else:
        return strike * discount * norm_cdf(-d2) - spot * dividend_discount * norm_cdf(-d1)


def black_scholes_delta(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
    is_call: bool,
) -> float:
    """
    Calculate Black-Scholes delta.

    Delta measures the rate of change of option price with respect to
    changes in the underlying asset's price.

    Returns:
        Delta (between 0 and 1 for calls, -1 and 0 for puts)
    """
    if time_to_expiry <= 0:
        if is_call:
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0

    d1 = _d1(spot, strike, rate, dividend, volatility, time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)

    if is_call:
        return dividend_discount * norm_cdf(d1)
    else:
        return dividend_discount * (norm_cdf(d1) - 1.0)


def black_scholes_gamma(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
) -> float:
    """
    Calculate Black-Scholes gamma.

    Gamma measures the rate of change of delta with respect to
    changes in the underlying price. Same for calls and puts.

    Returns:
        Gamma (always positive)
    """
    if time_to_expiry <= 0 or volatility <= 0:
        return 0.0

    d1 = _d1(spot, strike, rate, dividend, volatility, time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)

    return (
        dividend_discount
        * norm_pdf(d1)
        / (spot * volatility * math.sqrt(time_to_expiry))
    )


def black_scholes_vega(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
) -> float:
    """
    Calculate Black-Scholes vega.

    Vega measures the rate of change of option price with respect to
    changes in volatility. Same for calls and puts.

    Returns:
        Vega (option price change per 1% vol change, i.e., per 0.01 vol)
    """
    if time_to_expiry <= 0:
        return 0.0

    d1 = _d1(spot, strike, rate, dividend, volatility, time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)

    # Return vega per 1% (0.01) change in volatility
    return spot * dividend_discount * norm_pdf(d1) * math.sqrt(time_to_expiry) * 0.01


def black_scholes_theta(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
    is_call: bool,
) -> float:
    """
    Calculate Black-Scholes theta.

    Theta measures the rate of change of option price with respect to
    the passage of time (time decay).

    Returns:
        Theta (option price change per day, negative for long options)
    """
    if time_to_expiry <= 0:
        return 0.0

    d1 = _d1(spot, strike, rate, dividend, volatility, time_to_expiry)
    d2 = _d2(spot, strike, rate, dividend, volatility, time_to_expiry)

    discount = math.exp(-rate * time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)

    sqrt_t = math.sqrt(time_to_expiry)

    # First term: time decay of option value
    term1 = -(spot * dividend_discount * norm_pdf(d1) * volatility) / (2 * sqrt_t)

    if is_call:
        term2 = -rate * strike * discount * norm_cdf(d2)
        term3 = dividend * spot * dividend_discount * norm_cdf(d1)
    else:
        term2 = rate * strike * discount * norm_cdf(-d2)
        term3 = -dividend * spot * dividend_discount * norm_cdf(-d1)

    # Return theta per day (divide annual theta by 365)
    return (term1 + term2 + term3) / 365.0


def black_scholes_rho(
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    volatility: float,
    time_to_expiry: float,
    is_call: bool,
) -> float:
    """
    Calculate Black-Scholes rho.

    Rho measures the rate of change of option price with respect to
    changes in the risk-free interest rate.

    Returns:
        Rho (option price change per 1% rate change, i.e., per 0.01 rate)
    """
    if time_to_expiry <= 0:
        return 0.0

    d2 = _d2(spot, strike, rate, dividend, volatility, time_to_expiry)
    discount = math.exp(-rate * time_to_expiry)

    # Return rho per 1% (0.01) change in rate
    if is_call:
        return strike * time_to_expiry * discount * norm_cdf(d2) * 0.01
    else:
        return -strike * time_to_expiry * discount * norm_cdf(-d2) * 0.01
