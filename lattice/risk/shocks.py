"""Shock-application convention shared by all stress paths.

Rate-like factors are quoted in absolute terms (basis points), so a +100bp
shock is ``Rate + 0.01``. Price- and vol-like factors are quoted in relative
terms, so a shock ``s`` means ``value * (1 + s)``.
"""

# Instrument inputs shocked additively (rates / yields / spreads, quoted in bp).
# This is a by-name allowlist: keep it in sync when new rate-like inputs are added.
ABSOLUTE_FACTORS = frozenset({
    "Rate",
    "YieldToMaturity",
    "FloatingRate",
    "DiscountRate",
    "FloatingSpread",
})


def shocked_value(factor: str, current: float, shock: float) -> float:
    """Return the post-shock value of an instrument input under the convention.

    Args:
        factor: Instrument input name (e.g. "Spot", "Volatility", "Rate").
        current: Current value of that input.
        shock: Shock magnitude (relative fraction, or absolute for rate-like).
    """
    if factor in ABSOLUTE_FACTORS:
        return current + shock
    return current * (1 + shock)
