"""RiskEngine for batch risk calculations.

This module provides a class-based interface for computing risk metrics
across multiple instruments.

Example:
    from lattice import VanillaOption, Bond
    from lattice.risk import RiskEngine

    engine = RiskEngine()
    engine.add(option, name="AAPL_C_150")
    engine.add(bond, name="UST_10Y")

    greeks = engine.compute_greeks()
    print(greeks["AAPL_C_150"]["delta"])

    stress = engine.stress_test(Spot=-0.10)
    print(stress["AAPL_C_150"])
"""

from typing import Dict, Any, Optional
import dag

from .sensitivities import delta, gamma, vega, theta, rho, dv01


class RiskEngine:
    """Batch risk calculations across multiple instruments.

    RiskEngine provides a convenient way to compute risk metrics
    for a portfolio of instruments in a single call.

    Example:
        engine = RiskEngine()
        engine.add(option1, "AAPL_C_150")
        engine.add(option2, "AAPL_P_145")
        engine.add(bond, "UST_10Y")

        # Compute all greeks
        greeks = engine.compute_greeks()
        for name, metrics in greeks.items():
            print(f"{name}: delta={metrics.get('delta', 'N/A')}")

        # Stress test
        stress = engine.stress_test(Spot=-0.10, Volatility=0.05)
    """

    def __init__(self):
        """Initialize an empty RiskEngine."""
        self._instruments: Dict[str, dag.Model] = {}

    def add(self, instrument: dag.Model, name: Optional[str] = None) -> None:
        """Register an instrument for risk calculation.

        Args:
            instrument: Any dag.Model (option, bond, forward, etc.)
            name: Identifier for this instrument (auto-generated if None)
        """
        if name is None:
            name = f"inst_{len(self._instruments)}"
        self._instruments[name] = instrument

    def remove(self, name: str) -> None:
        """Remove an instrument from the engine.

        Args:
            name: Instrument identifier

        Raises:
            KeyError: If instrument not found
        """
        if name not in self._instruments:
            raise KeyError(f"Instrument '{name}' not found")
        del self._instruments[name]

    def clear(self) -> None:
        """Remove all instruments from the engine."""
        self._instruments.clear()

    @property
    def instruments(self) -> Dict[str, dag.Model]:
        """Return registered instruments."""
        return self._instruments.copy()

    def compute_greeks(self, bump: float = 0.01) -> Dict[str, Dict[str, float]]:
        """Compute all applicable Greeks for registered instruments.

        Automatically detects which Greeks are applicable based on
        the instrument's available inputs.

        Args:
            bump: Bump size for numerical differentiation

        Returns:
            dict mapping instrument name to dict of Greeks
        """
        results = {}

        for name, inst in self._instruments.items():
            results[name] = {}

            # Delta and Gamma (require Spot)
            if hasattr(inst, "Spot") and hasattr(inst, "Price"):
                try:
                    results[name]["delta"] = delta(inst, bump)
                    results[name]["gamma"] = gamma(inst, bump)
                except Exception:
                    pass

            # Vega (requires Volatility)
            if hasattr(inst, "Volatility") and hasattr(inst, "Price"):
                try:
                    results[name]["vega"] = vega(inst, bump)
                except Exception:
                    pass

            # Theta (requires TimeToExpiry)
            if hasattr(inst, "TimeToExpiry") and hasattr(inst, "Price"):
                try:
                    results[name]["theta"] = theta(inst)
                except Exception:
                    pass

            # Rho (requires Rate)
            if hasattr(inst, "Rate") and hasattr(inst, "Price"):
                try:
                    results[name]["rho"] = rho(inst, bump)
                except Exception:
                    pass

            # DV01 (requires YieldToMaturity)
            if hasattr(inst, "YieldToMaturity") and hasattr(inst, "Price"):
                try:
                    results[name]["dv01"] = dv01(inst)
                except Exception:
                    pass

        return results

    def stress_test(self, **shocks) -> Dict[str, Dict[str, Any]]:
        """Apply stress scenario to all instruments.

        Shocks are specified as keyword arguments where the key is the
        input name and the value is the relative shock (e.g., -0.10 for -10%).

        Args:
            **shocks: Relative shocks by input name
                      e.g., Spot=-0.10, Volatility=0.05

        Returns:
            dict mapping instrument name to result dict with:
                - base_price: Price before shock
                - stressed_price: Price after shock
                - price_impact: Change in price

        Example:
            # -10% spot, +5% vol
            results = engine.stress_test(Spot=-0.10, Volatility=0.05)
        """
        results = {}

        for name, inst in self._instruments.items():
            # Get base price
            if hasattr(inst, "Price"):
                base_price = inst.Price()
            else:
                results[name] = {"error": "No Price attribute"}
                continue

            # Apply shocks
            with dag.scenario():
                for input_name, shock in shocks.items():
                    if hasattr(inst, input_name):
                        accessor = getattr(inst, input_name)
                        current_value = accessor()
                        accessor.override(current_value * (1 + shock))

                stressed_price = inst.Price()

            results[name] = {
                "base_price": base_price,
                "stressed_price": stressed_price,
                "price_impact": stressed_price - base_price,
                "price_impact_pct": (stressed_price - base_price) / base_price if base_price else 0,
            }

        return results

    def summary(self) -> Dict[str, Any]:
        """Get summary of registered instruments.

        Returns:
            dict with counts and instrument names
        """
        return {
            "count": len(self._instruments),
            "instruments": list(self._instruments.keys()),
        }
