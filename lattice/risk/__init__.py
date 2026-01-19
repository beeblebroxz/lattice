"""Risk analysis and sensitivity calculations.

This module provides numerical risk calculations using bump-and-reval
techniques that work for any dag.Model instrument.

Key Functions:
    - sensitivity(): General-purpose sensitivity calculation
    - delta(), gamma(), vega(), theta(), rho(): Standard Greeks
    - dv01(): Bond duration risk
    - portfolio_delta(), stress(): Portfolio-level risk
    - parametric_var(): Value at Risk

Classes:
    - RiskEngine: Batch risk calculations across instruments

Example:
    from lattice import VanillaOption, risk

    option = VanillaOption()
    option.Spot.set(100.0)
    option.Strike.set(100.0)

    # Numerical Greeks (work for any instrument)
    print(f"Delta: {risk.delta(option):.4f}")
    print(f"Gamma: {risk.gamma(option):.6f}")
    print(f"Vega:  {risk.vega(option):.4f}")

    # Compare with closed-form
    print(f"Closed-form delta: {option.Delta():.4f}")
"""

# Core sensitivity functions
from .sensitivities import (
    sensitivity,
    delta,
    gamma,
    vega,
    theta,
    rho,
    dv01,
)

# Portfolio-level risk
from .portfolio import (
    portfolio_delta,
    stress,
    portfolio_exposure,
)

# Predefined scenarios
from .scenarios import (
    run_scenario,
    run_all_scenarios,
    list_scenarios,
    add_scenario,
    remove_scenario,
    SCENARIOS,
)

# Value at Risk
from .var import (
    parametric_var,
    var_contribution,
    var_report,
)

# RiskEngine class
from .engine import RiskEngine

__all__ = [
    # Core sensitivities
    "sensitivity",
    "delta",
    "gamma",
    "vega",
    "theta",
    "rho",
    "dv01",
    # Portfolio risk
    "portfolio_delta",
    "stress",
    "portfolio_exposure",
    # Scenarios
    "run_scenario",
    "run_all_scenarios",
    "list_scenarios",
    "add_scenario",
    "remove_scenario",
    "SCENARIOS",
    # VaR
    "parametric_var",
    "var_contribution",
    "var_report",
    # Engine
    "RiskEngine",
]
