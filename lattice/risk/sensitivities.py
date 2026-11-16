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

from typing import Optional
import dag

# Size of the move that vega and rho are quoted against (1% = 0.01).
ONE_PERCENT = 0.01
ONE_BASIS_POINT = 0.0001
ONE_DAY = 1 / 365

# Inputs that carry an instrument's interest-rate level for DV01, in order of
# preference: bonds are driven by yield, swaps by their discount rate.
_DV01_INPUTS = ("YieldToMaturity", "DiscountRate")


def value_output(instrument: dag.Model) -> Optional[str]:
    """Name of the output that risk measures are taken on, or None.

    ``Price`` when the instrument has one, otherwise ``MarketValue`` (forwards
    and FX instruments are valued, not priced).
    """
    for name in ("Price", "MarketValue"):
        if hasattr(instrument, name):
            return name
    return None


def dv01_input(instrument: dag.Model) -> Optional[str]:
    """Name of the rate input DV01 bumps on this instrument, or None."""
    for name in _DV01_INPUTS:
        if hasattr(instrument, name):
            return name
    return None


def _output(instrument: dag.Model, output_name: Optional[str]) -> str:
    if output_name is not None:
        return output_name
    name = value_output(instrument)
    if name is None:
        raise AttributeError(
            f"{type(instrument).__name__} has neither Price nor MarketValue"
        )
    return name


def sensitivity(
    instrument: dag.Model,
    input_name: str,
    output_name: Optional[str] = None,
    bump: float = 0.01,
    bump_type: str = "absolute",
) -> float:
    """Compute sensitivity of output to input via bump-and-reval.

    Uses forward difference: (f(x+h) - f(x)) / h

    Args:
        instrument: Any dag.Model with overridable inputs
        input_name: Name of input to bump (e.g., "Spot", "Rate")
        output_name: Name of output to measure (e.g., "Price", "TotalPnL").
            Defaults to Price, or MarketValue for instruments without a Price.
        bump: Size of bump
        bump_type: "absolute" (add bump) or "relative" (multiply by 1+bump)

    Returns:
        Sensitivity = (bumped_output - base_output) / bump

    Raises:
        AttributeError: If input or output doesn't exist on instrument
    """
    # Get accessors
    input_accessor = getattr(instrument, input_name)
    output_accessor = getattr(instrument, _output(instrument, output_name))

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


def delta(
    instrument: dag.Model, bump: float = 0.01, output_name: Optional[str] = None
) -> float:
    """Compute delta: dPrice/dSpot.

    Delta measures how much the price changes for a $1 move in the underlying.

    Args:
        instrument: Any dag.Model with Spot and Price (or MarketValue)
        bump: Spot bump size (default $0.01)
        output_name: Output to measure (default Price, else MarketValue)

    Returns:
        Delta value
    """
    return sensitivity(instrument, "Spot", output_name, bump=bump)


def gamma(
    instrument: dag.Model, bump: float = 0.01, output_name: Optional[str] = None
) -> float:
    """Compute gamma: d²Price/dSpot² using central difference.

    Gamma measures the rate of change of delta. Uses central difference
    for better accuracy: (f(x+h) - 2*f(x) + f(x-h)) / h²

    Args:
        instrument: Any dag.Model with Spot and Price (or MarketValue)
        bump: Spot bump size (default $0.01)
        output_name: Output to measure (default Price, else MarketValue)

    Returns:
        Gamma value
    """
    spot_accessor = getattr(instrument, "Spot")
    price_accessor = getattr(instrument, _output(instrument, output_name))

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


def vega(
    instrument: dag.Model, bump: float = 0.01, output_name: Optional[str] = None
) -> float:
    """Compute vega: price change per 1% vol move.

    Vega measures price sensitivity to implied volatility.
    Returns the price change for a 0.01 (1%) move in volatility,
    matching the convention used by closed-form Black-Scholes.

    Args:
        instrument: Any dag.Model with Volatility and Price (or MarketValue)
        bump: Volatility bump used to estimate the slope (default 0.01). The
            result is always quoted per 1%, whatever the bump.
        output_name: Output to measure (default Price, else MarketValue)

    Returns:
        Vega value (price change for a 1% vol move)
    """
    raw_sens = sensitivity(instrument, "Volatility", output_name, bump=bump)
    return raw_sens * ONE_PERCENT


def theta(instrument: dag.Model, bump: float = 1 / 365) -> float:
    """Compute theta: price change per day (time decay).

    Theta measures how much value the instrument loses per day.
    Negative theta means the instrument loses value as time passes.

    Time is rolled forward (TimeToExpiry is bumped down), so near expiry this
    is the decay the instrument actually has left, and at expiry it is zero.

    Args:
        instrument: Any dag.Model with TimeToExpiry and Price (or MarketValue)
        bump: Time step used to estimate the slope (default 1 day = 1/365
            years). The result is always quoted per day.

    Returns:
        Theta value (price change per day, typically negative)
    """
    time_accessor = getattr(instrument, "TimeToExpiry")
    price_accessor = getattr(instrument, _output(instrument, None))

    time_left = time_accessor()
    if time_left <= 0:
        return 0.0
    step = min(bump, time_left)
    base_price = price_accessor()

    with dag.scenario():
        time_accessor.override(time_left - step)
        later_price = price_accessor()

    return (later_price - base_price) / step * ONE_DAY


def rho(instrument: dag.Model, bump: float = 0.01) -> float:
    """Compute rho: price change per 1% rate move.

    Rho measures price sensitivity to interest rates.
    Returns the price change for a 0.01 (1%) move in rates,
    matching the convention used by closed-form Black-Scholes.

    Args:
        instrument: Any dag.Model with Rate and Price (or MarketValue)
        bump: Rate bump used to estimate the slope (default 0.01). The result
            is always quoted per 1%, whatever the bump.

    Returns:
        Rho value (price change for a 1% rate move)
    """
    raw_sens = sensitivity(instrument, "Rate", bump=bump)
    return raw_sens * ONE_PERCENT


def dv01(instrument: dag.Model, bump: float = 0.0001) -> float:
    """Compute DV01: Dollar value of 1 basis point yield change.

    DV01 measures how much a bond's price changes for a 1bp yield move.
    Also known as "dollar duration" or "price value of a basis point".

    The rate bumped is YieldToMaturity (bonds) or, failing that, DiscountRate
    (swaps).

    Args:
        instrument: Any dag.Model with YieldToMaturity or DiscountRate, and
            Price (or MarketValue)
        bump: Rate bump used to estimate the slope (default 0.0001 = 1bp). The
            result is always quoted per 1bp.

    Returns:
        DV01 value (absolute price change per 1bp)

    Raises:
        AttributeError: If the instrument has no rate input to bump
    """
    rate_input = dv01_input(instrument)
    if rate_input is None:
        raise AttributeError(
            f"{type(instrument).__name__} has no YieldToMaturity or DiscountRate"
        )
    # DV01 is typically reported as absolute value
    sens = sensitivity(instrument, rate_input, bump=bump)
    return abs(sens * ONE_BASIS_POINT)
