"""Value at Risk (VaR) calculations.

This module provides parametric VaR and Expected Shortfall calculations
using the variance-covariance method.

Example:
    from lattice.trading import TradingSystem
    from lattice import risk

    system = TradingSystem()
    desk = system.book("OPTIONS_DESK")
    # ... add trades ...

    # 1-day 95% VaR
    result = risk.parametric_var(desk, confidence=0.95, holding_period=1)
    print(f"VaR: ${result['var']:,.2f}")
    print(f"Expected Shortfall: ${result['expected_shortfall']:,.2f}")
"""

import math
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from lattice.trading import Book


# Standard normal distribution z-scores for common confidence levels
Z_SCORES: Dict[float, float] = {
    0.90: 1.282,
    0.95: 1.645,
    0.99: 2.326,
}

# Trading days per year
TRADING_DAYS = 252


def parametric_var(
    book: "Book",
    confidence: float = 0.95,
    holding_period: int = 1,
    volatility: Optional[float] = None,
) -> Dict:
    """Compute parametric VaR using variance-covariance method.

    Uses the normal distribution assumption for returns.

    Args:
        book: Book with positions to analyze
        confidence: Confidence level (0.90, 0.95, or 0.99)
        holding_period: Number of trading days
        volatility: Annual volatility (if None, uses 20% default)

    Returns:
        dict with:
            - var: Value at Risk
            - expected_shortfall: Expected Shortfall (CVaR)
            - confidence: Confidence level used
            - holding_period: Holding period used
            - portfolio_value: Gross exposure
            - volatility: Volatility used

    Example:
        # 1-day 95% VaR
        result = parametric_var(book, confidence=0.95, holding_period=1)

        # 10-day 99% VaR (regulatory)
        result = parametric_var(book, confidence=0.99, holding_period=10)
    """
    # Get z-score for confidence level
    if confidence in Z_SCORES:
        z = Z_SCORES[confidence]
    else:
        # Approximate z-score using inverse normal CDF
        # For confidence c, z = Phi^{-1}(c)
        # Using simple approximation for common values
        z = 1.645  # Default to 95%

    # Portfolio value (use gross exposure as proxy for position size)
    portfolio_value = book.GrossExposure()

    # Use provided volatility or default
    if volatility is None:
        volatility = 0.20  # 20% annual vol is a reasonable default

    # Scale volatility to holding period
    daily_vol = volatility / math.sqrt(TRADING_DAYS)
    period_vol = daily_vol * math.sqrt(holding_period)

    # VaR = Portfolio Value × Volatility × Z-score
    var = portfolio_value * period_vol * z

    # Expected Shortfall (CVaR) for normal distribution
    # ES = σ × φ(z) / (1-c) where φ is the standard normal PDF
    pdf_z = math.exp(-z**2 / 2) / math.sqrt(2 * math.pi)
    es = portfolio_value * period_vol * pdf_z / (1 - confidence)

    return {
        "var": var,
        "expected_shortfall": es,
        "confidence": confidence,
        "holding_period": holding_period,
        "portfolio_value": portfolio_value,
        "volatility": volatility,
        "daily_volatility": daily_vol,
        "period_volatility": period_vol,
        "z_score": z,
    }


def var_contribution(
    book: "Book",
    confidence: float = 0.95,
    holding_period: int = 1,
    volatility: Optional[float] = None,
) -> Dict[str, float]:
    """Compute VaR contribution by position.

    Shows how much each position contributes to total portfolio VaR.
    Useful for identifying risk concentrations.

    Args:
        book: Book with positions to analyze
        confidence: Confidence level
        holding_period: Number of trading days
        volatility: Annual volatility

    Returns:
        dict mapping symbol to VaR contribution
    """
    total_var = parametric_var(book, confidence, holding_period, volatility)["var"]

    contributions = {}
    for pos in book.Positions():
        # Simple approximation: weight by position value
        pos_value = abs(pos.MarketValue())
        total_value = book.GrossExposure()

        if total_value > 0:
            weight = pos_value / total_value
            contributions[pos.Symbol()] = total_var * weight
        else:
            contributions[pos.Symbol()] = 0.0

    return contributions


def var_report(
    book: "Book",
    confidence_levels: Optional[list] = None,
    holding_periods: Optional[list] = None,
    volatility: Optional[float] = None,
) -> Dict:
    """Generate comprehensive VaR report.

    Args:
        book: Book with positions to analyze
        confidence_levels: List of confidence levels (default: [0.90, 0.95, 0.99])
        holding_periods: List of holding periods (default: [1, 5, 10])
        volatility: Annual volatility

    Returns:
        dict with VaR matrix and contributions
    """
    if confidence_levels is None:
        confidence_levels = [0.90, 0.95, 0.99]
    if holding_periods is None:
        holding_periods = [1, 5, 10]

    var_matrix = {}
    for conf in confidence_levels:
        var_matrix[conf] = {}
        for period in holding_periods:
            result = parametric_var(book, conf, period, volatility)
            var_matrix[conf][period] = {
                "var": result["var"],
                "expected_shortfall": result["expected_shortfall"],
            }

    # Position contributions at 95% 1-day
    contributions = var_contribution(book, 0.95, 1, volatility)

    return {
        "var_matrix": var_matrix,
        "contributions": contributions,
        "portfolio_value": book.GrossExposure(),
        "volatility": volatility or 0.20,
    }
