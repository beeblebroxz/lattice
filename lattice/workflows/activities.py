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

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

import dag
from dag.flags import Flags
from lattice.risk.shocks import shocked_value
from lattice.store.exceptions import SerializationError
from lattice.store.serialization import Serializer

logger = logging.getLogger(__name__)

# Instrument state crosses the wire in the Store's JSON-compatible encoding.
_SERIALIZER = Serializer()

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
    1. Serialized state (preferred): the instrument's full input state,
       market data included, is passed inline with its type name. This is
       what the client sends, so a worker prices exactly what the caller has.
    2. Store path: the instrument is loaded from a Store. This needs the
       type name too, and restores only persisted fields (contract terms):
       market data such as Spot or Volatility comes back at its defaults.

    When both are present the serialized state is used.

    Attributes:
        store_path: Path in a Store (e.g., "/Instruments/AAPL_C_150")
        serialized_state: Dict of field values for inline deserialization
        type_name: Fully qualified class name
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

    Extracts every Input field that has been explicitly set, for
    reconstruction. This enables passing instrument state to activities
    without a Store. Unlike the Store, which keeps only persisted contract
    terms, this includes market data, so the worker prices the instrument as
    it is now.

    Inputs still at their default are left out: the worker's copy computes
    the same default. Sending a default as a set value would pin it, which
    matters when it is derived from another input (a swap's FloatingRate
    follows DiscountRate until it is set) and that input is then bumped.

    Values are encoded the same way the Store encodes them (datetimes
    included); numpy scalars are converted to plain Python numbers.

    Args:
        inst: The instrument to serialize

    Returns:
        Dict of field names to JSON-compatible values

    Raises:
        SerializationError: If an input holds a value that cannot be sent
            (for example another dag.Model). Dropping it silently would make
            the worker price a different instrument.
    """
    data = {}
    for name, descriptor in inst._computed_functions_.items():
        if not descriptor.flags & Flags.Input:
            continue
        accessor = getattr(inst, name)
        if not _is_set(accessor):
            continue
        try:
            value = accessor()
        except Exception as e:
            logger.warning("Skipping field %s during serialization: %s", name, e)
            continue
        try:
            data[name] = _SERIALIZER._to_json_compatible(_plain(value))
        except SerializationError as e:
            raise SerializationError(
                f"Cannot send {type(inst).__name__}.{name} to a worker: {e}"
            ) from e
    return data


def _is_set(accessor: Any) -> bool:
    """Whether an input has been explicitly set (as opposed to defaulted)."""
    if not hasattr(accessor, "_node"):
        # Unknown dag version: be conservative and send the value.
        return True
    node = accessor._node
    return node is not None and node.has_set_value


def _plain(value: Any) -> Any:
    """Convert numpy scalars (np.int64, np.bool_, ...) to Python values."""
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return value.item()
    return value


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
                accessor.set(_SERIALIZER._from_json_compatible(value))

    return inst


def _import_type(type_name: str) -> type:
    """Import a class from its fully qualified name."""
    module_name, _, class_name = type_name.rpartition(".")
    if not module_name:
        raise ImportError(f"Cannot import type: {type_name}")
    import importlib

    return getattr(importlib.import_module(module_name), class_name)


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
    if ref.serialized_state is not None and ref.type_name:
        return deserialize_instrument(ref.type_name, ref.serialized_state)
    elif ref.store_path and store_uri:
        if not ref.type_name:
            raise ValueError(
                f"InstrumentRef for store path {ref.store_path!r} needs a "
                f"type_name: a worker's store has no registered types."
            )
        from lattice.store import connect

        store = connect(store_uri)
        try:
            # A fresh connection knows no types; register this one path.
            store.register_type(ref.store_path, _import_type(ref.type_name))
            return store[ref.store_path]
        finally:
            store.close()
    else:
        raise ValueError(
            "InstrumentRef must have either serialized_state (with type_name) "
            "or store_path (with type_name and store_uri)"
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
    - Delta/Gamma: If instrument has Spot
    - Vega: If instrument has Volatility
    - Theta: If instrument has TimeToExpiry
    - Rho: If instrument has Rate
    - DV01: If instrument has YieldToMaturity (or DiscountRate, for swaps)

    All are measured on Price, or on MarketValue for instruments without a
    Price, matching RiskEngine.compute_greeks().

    Args:
        instrument_name: Identifier for results tracking
        instrument_ref: Reference to the instrument
        bump: Bump size for numerical differentiation
        store_uri: Store connection string (if using store paths)

    Returns:
        GreeksResult with all computed values
    """
    from lattice.risk.sensitivities import (
        delta, gamma, vega, theta, rho, dv01, dv01_input, value_output,
    )

    result = GreeksResult(instrument_name=instrument_name)

    try:
        inst = _load_instrument(instrument_ref, store_uri)
    except Exception as e:
        result.error = f"Failed to load instrument: {e}"
        return result

    priced = value_output(inst) is not None

    if priced and hasattr(inst, "Spot"):
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

    if priced and hasattr(inst, "Volatility"):
        try:
            result.vega = vega(inst, bump)
        except Exception as e:
            if result.error is None:
                result.error = f"Vega failed: {e}"

    if priced and hasattr(inst, "TimeToExpiry"):
        try:
            result.theta = theta(inst)
        except Exception as e:
            if result.error is None:
                result.error = f"Theta failed: {e}"

    if priced and hasattr(inst, "Rate"):
        try:
            result.rho = rho(inst, bump)
        except Exception as e:
            if result.error is None:
                result.error = f"Rho failed: {e}"

    if priced and dv01_input(inst) is not None:
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
        shocks: Dict of input_name -> shock magnitude. Rate-like inputs
            (Rate, YieldToMaturity, swap rates/spreads) are shocked additively
            (bp); all other inputs are shocked relatively (e.g., {"Spot": -0.10}).
        store_uri: Store connection string (if using store paths)

    Returns:
        Dict with base_price, stressed_price, price_impact, price_impact_pct
    """
    try:
        inst = _load_instrument(instrument_ref, store_uri)
    except Exception as e:
        return {"instrument_name": instrument_name, "error": str(e)}

    from lattice.risk.sensitivities import value_output

    output = value_output(inst)
    if output is None:
        return {
            "instrument_name": instrument_name,
            "error": "No Price or MarketValue attribute",
        }
    value = getattr(inst, output)

    base_price = value()

    with dag.scenario():
        for input_name, shock in shocks.items():
            if hasattr(inst, input_name):
                accessor = getattr(inst, input_name)
                current_value = accessor()
                accessor.override(shocked_value(input_name, current_value, shock))

        stressed_price = value()

    return {
        "instrument_name": instrument_name,
        "base_price": base_price,
        "stressed_price": stressed_price,
        "price_impact": stressed_price - base_price,
        "price_impact_pct": (stressed_price - base_price) / base_price
        if base_price
        else 0,
    }
