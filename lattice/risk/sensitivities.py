"""Core sensitivity calculations using bump-and-reval.

This module provides numerical sensitivity calculations that work for any
dag.Model instrument. It complements closed-form Greeks (like those on
VanillaOption) with a general-purpose approach.

Example:
    from lattice import VanillaOption, risk

    option = VanillaOption()
    option.Spot.set(100.0)
    option.Strike.set(100.0)

    # Closed-form (exact)
    print(option.Delta())

    # Numerical (general, works for anything)
    print(risk.delta(option))
"""

from typing import Any
import dag


def sensitivity(
    instrument: dag.Model,
    input_name: str,
    output_name: str = "Price",
    bump: float = 0.01,
    bump_type: str = "absolute",
) -> float:
    """Compute sensitivity of output to input via bump-and-reval.

    Uses forward difference: (f(x+h) - f(x)) / h

    Args:
        instrument: Any dag.Model with overridable inputs
        input_name: Name of input to bump (e.g., "Spot", "Rate")
        output_name: Name of output to measure (e.g., "Price", "TotalPnL")
        bump: Size of bump
        bump_type: "absolute" (add bump) or "relative" (multiply by 1+bump)

    Returns:
        Sensitivity = (bumped_output - base_output) / bump

    Raises:
        AttributeError: If input or output doesn't exist on instrument
    """
    # Get accessors
    input_accessor = getattr(instrument, input_name)
    output_accessor = getattr(instrument, output_name)

    # Get base values
    base_input = input_accessor()
    base_output = output_accessor()

    # Compute bumped input value
    if bump_type == "relative":
        bumped_input = base_input * (1 + bump)
        effective_bump = base_input * bump
    else:  # absolute
        bumped_input = base_input + bump
        effective_bump = bump

    # Bump and reval
    with dag.scenario():
        input_accessor.override(bumped_input)
        bumped_output = output_accessor()

    return (bumped_output - base_output) / effective_bump


def delta(instrument: dag.Model, bump: float = 0.01) -> float:
    """Compute delta: dPrice/dSpot.

    Delta measures how much the price changes for a $1 move in the underlying.

    Args:
        instrument: Any dag.Model with Spot and Price
        bump: Spot bump size (default $0.01)

    Returns:
        Delta value
    """
    return sensitivity(instrument, "Spot", "Price", bump=bump)


def gamma(instrument: dag.Model, bump: float = 0.01) -> float:
    """Compute gamma: d²Price/dSpot² using central difference.

    Gamma measures the rate of change of delta. Uses central difference
    for better accuracy: (f(x+h) - 2*f(x) + f(x-h)) / h²

    Args:
        instrument: Any dag.Model with Spot and Price
        bump: Spot bump size (default $0.01)

    Returns:
        Gamma value
    """
    spot_accessor = getattr(instrument, "Spot")
    price_accessor = getattr(instrument, "Price")

    base_spot = spot_accessor()
    base_price = price_accessor()

    # Bump up
    with dag.scenario():
        spot_accessor.override(base_spot + bump)
        price_up = price_accessor()

    # Bump down
    with dag.scenario():
        spot_accessor.override(base_spot - bump)
        price_down = price_accessor()

    # Central difference formula for second derivative
    return (price_up - 2 * base_price + price_down) / (bump * bump)


def vega(instrument: dag.Model, bump: float = 0.01) -> float:
    """Compute vega: price change per 1% vol move.

    Vega measures price sensitivity to implied volatility.
    Returns the price change for a 0.01 (1%) move in volatility,
    matching the convention used by closed-form Black-Scholes.

    Args:
        instrument: Any dag.Model with Volatility and Price
        bump: Volatility bump size (default 0.01 = 1%)

    Returns:
        Vega value (price change for a 1% vol move)
    """
    # sensitivity() returns dP/dvol, multiply by bump to get price change
    raw_sens = sensitivity(instrument, "Volatility", "Price", bump=bump)
    return raw_sens * bump


def theta(instrument: dag.Model, bump: float = 1 / 365) -> float:
    """Compute theta: price change per day (time decay).

    Theta measures how much value the instrument loses per day.
    Negative theta means the instrument loses value as time passes.

    Args:
        instrument: Any dag.Model with TimeToExpiry and Price
        bump: Time bump size (default 1 day = 1/365 years)

    Returns:
        Theta value (price change per day, typically negative)
    """
    # As time passes, TimeToExpiry decreases, so we negate and scale
    # sensitivity() returns dP/dT, we want price change per day
    raw_sens = sensitivity(instrument, "TimeToExpiry", "Price", bump=bump)
    return -raw_sens * bump


def rho(instrument: dag.Model, bump: float = 0.01) -> float:
    """Compute rho: price change per 1% rate move.

    Rho measures price sensitivity to interest rates.
    Returns the price change for a 0.01 (1%) move in rates,
    matching the convention used by closed-form Black-Scholes.

    Args:
        instrument: Any dag.Model with Rate and Price
        bump: Rate bump size (default 0.01 = 1%)

    Returns:
        Rho value (price change for a 1% rate move)
    """
    # sensitivity() returns dP/dr, multiply by bump to get price change
    raw_sens = sensitivity(instrument, "Rate", "Price", bump=bump)
    return raw_sens * bump


def dv01(instrument: dag.Model, bump: float = 0.0001) -> float:
    """Compute DV01: Dollar value of 1 basis point yield change.

    DV01 measures how much a bond's price changes for a 1bp yield move.
    Also known as "dollar duration" or "price value of a basis point".

    Args:
        instrument: Any dag.Model with YieldToMaturity and Price
        bump: Yield bump size (default 0.0001 = 1bp)

    Returns:
        DV01 value (absolute price change per 1bp)
    """
    # DV01 is typically reported as absolute value
    sens = sensitivity(instrument, "YieldToMaturity", "Price", bump=bump)
    return abs(sens * bump)
