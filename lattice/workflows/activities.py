"""Temporal activities for Lattice risk calculations.

Activities are the building blocks of Temporal workflows. Each activity
represents a single unit of work that can be executed, retried, and
distributed across workers.

Example:
    from lattice.workflows.activities import compute_instrument_greeks, InstrumentRef

    # Activity can be called directly for testing
    result = await compute_instrument_greeks(
        instrument_name="AAPL_C_150",
        instrument_ref=InstrumentRef(store_path="/Instruments/AAPL_C_150"),
        bump=0.01,
        store_uri="sqlite:///trading.db",
    )
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

import dag
from dag.flags import Flags

try:
    from temporalio import activity

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False

    class _MockActivity:
        """Mock activity decorator when temporalio not installed."""

        @staticmethod
        def defn(fn):
            return fn

    activity = _MockActivity()


@dataclass
class InstrumentRef:
    """Reference to an instrument for passing to activities.

    Activities cannot receive dag.Model objects directly (not serializable).
    Instead, we pass a reference that can be resolved to the actual object.

    Two modes are supported:
    1. Store path: Instrument is loaded from a Store
    2. Serialized state: Instrument state is passed inline

    Attributes:
        store_path: Path in a Store (e.g., "/Instruments/AAPL_C_150")
        serialized_state: Dict of field values for inline deserialization
        type_name: Fully qualified class name (for inline deserialization)
    """

    store_path: Optional[str] = None
    serialized_state: Optional[Dict[str, Any]] = None
    type_name: Optional[str] = None


@dataclass
class GreeksResult:
    """Result of Greeks calculation for a single instrument.

    Contains all computed Greeks plus any error information.
    Greeks that don't apply to the instrument are left as None.

    Attributes:
        instrument_name: Identifier for the instrument
        delta: Price sensitivity to underlying (dPrice/dSpot)
        gamma: Rate of change of delta (d²Price/dSpot²)
        vega: Price sensitivity to volatility
        theta: Time decay (price change per day)
        rho: Price sensitivity to interest rates
        dv01: Dollar value of 1 basis point yield change
        error: Error message if calculation failed
    """

    instrument_name: str
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    rho: Optional[float] = None
    dv01: Optional[float] = None
    error: Optional[str] = None


def serialize_instrument(inst: dag.Model) -> Dict[str, Any]:
    """Serialize a dag.Model instrument to a dictionary.

    Extracts all Input fields (those that can be set) for reconstruction.
    This enables passing instrument state to activities without a Store.

    Args:
        inst: The instrument to serialize

    Returns:
        Dict with type name and field values
    """
    data = {}
    for name, descriptor in inst._computed_functions_.items():
        if descriptor.flags & Flags.Input:
            accessor = getattr(inst, name)
            try:
                value = accessor()
                if isinstance(value, (str, int, float, bool, type(None))):
                    data[name] = value
                elif isinstance(value, (list, tuple)):
                    data[name] = list(value)
                elif isinstance(value, dict):
                    data[name] = dict(value)
            except Exception:
                pass
    return data


def deserialize_instrument(
    type_name: str,
    data: Dict[str, Any],
) -> dag.Model:
    """Deserialize an instrument from type name and field values.

    Reconstructs a dag.Model from its serialized state by:
    1. Importing the class from its fully qualified name
    2. Creating a new instance
    3. Setting all Input fields

    Args:
        type_name: Fully qualified class name (e.g., "lattice.VanillaOption")
        data: Dict of field names to values

    Returns:
        Reconstructed dag.Model instance

    Raises:
        ImportError: If the class cannot be imported
        AttributeError: If a field doesn't exist
    """
    parts = type_name.rsplit(".", 1)
    if len(parts) == 2:
        module_name, class_name = parts
        import importlib

        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    else:
        raise ImportError(f"Cannot import type: {type_name}")

    inst = cls()
    for name, value in data.items():
        if hasattr(inst, name):
            accessor = getattr(inst, name)
            if hasattr(accessor, "set"):
                accessor.set(value)

    return inst


def _load_instrument(
    ref: InstrumentRef,
    store_uri: Optional[str] = None,
) -> dag.Model:
    """Load an instrument from a reference.

    Args:
        ref: InstrumentRef with store path or serialized state
        store_uri: Store connection string (required if using store_path)

    Returns:
        The loaded dag.Model instance

    Raises:
        ValueError: If reference is invalid
    """
    if ref.store_path and store_uri:
        from lattice.store import connect

        store = connect(store_uri)
        return store[ref.store_path]
    elif ref.serialized_state and ref.type_name:
        return deserialize_instrument(ref.type_name, ref.serialized_state)
    else:
        raise ValueError(
            "InstrumentRef must have either store_path (with store_uri) "
            "or serialized_state (with type_name)"
        )


@activity.defn
async def compute_instrument_greeks(
    instrument_name: str,
    instrument_ref: InstrumentRef,
    bump: float = 0.01,
    store_uri: Optional[str] = None,
) -> GreeksResult:
    """Compute all applicable Greeks for a single instrument.

    This activity loads an instrument from a reference and computes
    all Greeks that apply based on the instrument's available inputs.

    Supported Greeks:
    - Delta/Gamma: If instrument has Spot and Price
    - Vega: If instrument has Volatility and Price
    - Theta: If instrument has TimeToExpiry and Price
    - Rho: If instrument has Rate and Price
    - DV01: If instrument has YieldToMaturity and Price

    Args:
        instrument_name: Identifier for results tracking
        instrument_ref: Reference to the instrument
        bump: Bump size for numerical differentiation
        store_uri: Store connection string (if using store paths)

    Returns:
        GreeksResult with all computed values
    """
    from lattice.risk.sensitivities import delta, gamma, vega, theta, rho, dv01

    result = GreeksResult(instrument_name=instrument_name)

    try:
        inst = _load_instrument(instrument_ref, store_uri)
    except Exception as e:
        result.error = f"Failed to load instrument: {e}"
        return result

    if hasattr(inst, "Spot") and hasattr(inst, "Price"):
        try:
            result.delta = delta(inst, bump)
        except Exception as e:
            if result.error is None:
                result.error = f"Delta failed: {e}"

        try:
            result.gamma = gamma(inst, bump)
        except Exception as e:
            if result.error is None:
                result.error = f"Gamma failed: {e}"

    if hasattr(inst, "Volatility") and hasattr(inst, "Price"):
        try:
            result.vega = vega(inst, bump)
        except Exception as e:
            if result.error is None:
                result.error = f"Vega failed: {e}"

    if hasattr(inst, "TimeToExpiry") and hasattr(inst, "Price"):
        try:
            result.theta = theta(inst)
        except Exception as e:
            if result.error is None:
                result.error = f"Theta failed: {e}"

    if hasattr(inst, "Rate") and hasattr(inst, "Price"):
        try:
            result.rho = rho(inst, bump)
        except Exception as e:
            if result.error is None:
                result.error = f"Rho failed: {e}"

    if hasattr(inst, "YieldToMaturity") and hasattr(inst, "Price"):
        try:
            result.dv01 = dv01(inst)
        except Exception as e:
            if result.error is None:
                result.error = f"DV01 failed: {e}"

    return result


@activity.defn
async def compute_stress_test(
    instrument_name: str,
    instrument_ref: InstrumentRef,
    shocks: Dict[str, float],
    store_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply stress scenario to a single instrument.

    Computes the price impact of specified shocks to inputs.

    Args:
        instrument_name: Identifier for results tracking
        instrument_ref: Reference to the instrument
        shocks: Dict of input_name -> relative shock (e.g., {"Spot": -0.10})
        store_uri: Store connection string (if using store paths)

    Returns:
        Dict with base_price, stressed_price, price_impact, price_impact_pct
    """
    try:
        inst = _load_instrument(instrument_ref, store_uri)
    except Exception as e:
        return {"instrument_name": instrument_name, "error": str(e)}

    if not hasattr(inst, "Price"):
        return {"instrument_name": instrument_name, "error": "No Price attribute"}

    base_price = inst.Price()

    with dag.scenario():
        for input_name, shock in shocks.items():
            if hasattr(inst, input_name):
                accessor = getattr(inst, input_name)
                current_value = accessor()
                accessor.override(current_value * (1 + shock))

        stressed_price = inst.Price()

    return {
        "instrument_name": instrument_name,
        "base_price": base_price,
        "stressed_price": stressed_price,
        "price_impact": stressed_price - base_price,
        "price_impact_pct": (stressed_price - base_price) / base_price
        if base_price
        else 0,
    }
