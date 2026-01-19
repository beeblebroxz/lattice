"""Predefined stress scenarios for risk analysis.

This module provides common stress scenarios used in risk management,
such as market crashes, rate hikes, and volatility spikes.

Example:
    from lattice import risk

    # Run a specific scenario
    result = risk.run_scenario(book, "market_crash")
    print(f"P&L under crash: ${result['pnl_impact']:,.2f}")

    # Run all scenarios
    results = risk.run_all_scenarios(book)
    for name, result in results.items():
        print(f"{name}: ${result['pnl_impact']:+,.2f}")
"""

from typing import TYPE_CHECKING, Dict, Any

from .portfolio import stress

if TYPE_CHECKING:
    from lattice.trading import Book


# Predefined stress scenarios
# Format: {name: {shock_param: value}}
SCENARIOS: Dict[str, Dict[str, float]] = {
    # Equity market scenarios
    "market_crash": {
        "spot_shock": -0.20,  # -20% spot
        "vol_shock": 0.50,    # +50% vol (from 20% to 30%)
    },
    "market_correction": {
        "spot_shock": -0.10,  # -10% spot
        "vol_shock": 0.25,    # +25% vol
    },
    "market_rally": {
        "spot_shock": 0.10,   # +10% spot
        "vol_shock": -0.10,   # -10% vol (volatility compression)
    },

    # Rate scenarios
    "rate_hike": {
        "rate_shock": 0.01,   # +100bp
    },
    "rate_cut": {
        "rate_shock": -0.01,  # -100bp
    },
    "rate_shock_severe": {
        "rate_shock": 0.02,   # +200bp
    },

    # Volatility scenarios
    "vol_spike": {
        "vol_shock": 0.10,    # +10% vol (absolute)
    },
    "vol_crush": {
        "vol_shock": -0.05,   # -5% vol (absolute)
    },

    # Combined scenarios
    "flight_to_quality": {
        "spot_shock": -0.10,  # -10% equity
        "rate_shock": -0.005, # -50bp rates (safe haven buying)
    },
    "stagflation": {
        "spot_shock": -0.15,  # -15% equity
        "rate_shock": 0.015,  # +150bp rates
        "vol_shock": 0.30,    # +30% vol
    },
    "black_swan": {
        "spot_shock": -0.40,  # -40% spot
        "vol_shock": 1.00,    # +100% vol (vol doubles)
    },
}


def run_scenario(book: "Book", scenario_name: str) -> Dict[str, Any]:
    """Run a predefined stress scenario on a book.

    Args:
        book: Book with positions to analyze
        scenario_name: Name of scenario from SCENARIOS dict

    Returns:
        dict with base_pnl, stressed_pnl, pnl_impact, and scenario name

    Raises:
        KeyError: If scenario_name not found
    """
    if scenario_name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise KeyError(f"Unknown scenario '{scenario_name}'. Available: {available}")

    params = SCENARIOS[scenario_name]
    result = stress(book, **params)
    result["scenario"] = scenario_name
    return result


def run_all_scenarios(book: "Book") -> Dict[str, Dict[str, Any]]:
    """Run all predefined scenarios on a book.

    Args:
        book: Book with positions to analyze

    Returns:
        dict mapping scenario name to result dict
    """
    return {name: run_scenario(book, name) for name in SCENARIOS}


def list_scenarios() -> Dict[str, Dict[str, float]]:
    """Return all available scenarios with their parameters.

    Returns:
        dict mapping scenario name to parameter dict
    """
    return SCENARIOS.copy()


def add_scenario(name: str, **params) -> None:
    """Add a custom scenario to the available scenarios.

    Args:
        name: Scenario name
        **params: Shock parameters (spot_shock, rate_shock, vol_shock)

    Example:
        risk.add_scenario("my_scenario", spot_shock=-0.15, vol_shock=0.20)
    """
    SCENARIOS[name] = params


def remove_scenario(name: str) -> None:
    """Remove a scenario from the available scenarios.

    Args:
        name: Scenario name to remove

    Raises:
        KeyError: If scenario not found
    """
    if name not in SCENARIOS:
        raise KeyError(f"Scenario '{name}' not found")
    del SCENARIOS[name]
