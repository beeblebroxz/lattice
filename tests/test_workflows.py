"""Tests for Temporal workflow integration.

These tests verify:
1. Serialization/deserialization of instruments
2. Activity logic (without Temporal)
3. Workflow integration (with Temporal testing environment)

To run integration tests, install temporal extras:
    pip install lattice[temporal]
"""

import pytest
from dataclasses import asdict
from datetime import datetime

import dag

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lattice import VanillaOption, Bond
from lattice.workflows.activities import (
    InstrumentRef,
    GreeksResult,
    serialize_instrument,
    deserialize_instrument,
    _load_instrument,
)


class TestInstrumentRef:
    """Tests for InstrumentRef data class."""

    def test_store_path_ref(self):
        """Test creating a reference by store path."""
        ref = InstrumentRef(store_path="/Instruments/AAPL_C_150")
        assert ref.store_path == "/Instruments/AAPL_C_150"
        assert ref.serialized_state is None

    def test_serialized_ref(self):
        """Test creating a reference with serialized state."""
        ref = InstrumentRef(
            serialized_state={"Spot": 100.0, "Strike": 105.0},
            type_name="lattice.VanillaOption",
        )
        assert ref.store_path is None
        assert ref.serialized_state == {"Spot": 100.0, "Strike": 105.0}
        assert ref.type_name == "lattice.VanillaOption"

    def test_ref_to_dict(self):
        """Test converting ref to dict for serialization."""
        ref = InstrumentRef(store_path="/Instruments/AAPL_C_150")
        d = asdict(ref)
        assert d["store_path"] == "/Instruments/AAPL_C_150"


class TestGreeksResult:
    """Tests for GreeksResult data class."""

    def test_basic_result(self):
        """Test creating a basic result."""
        result = GreeksResult(
            instrument_name="AAPL_C_150",
            delta=0.55,
            gamma=0.02,
        )
        assert result.instrument_name == "AAPL_C_150"
        assert result.delta == 0.55
        assert result.gamma == 0.02
        assert result.vega is None

    def test_result_with_error(self):
        """Test creating a result with error."""
        result = GreeksResult(
            instrument_name="BAD_INST",
            error="Calculation failed",
        )
        assert result.instrument_name == "BAD_INST"
        assert result.error == "Calculation failed"
        assert result.delta is None


class TestSerialization:
    """Tests for instrument serialization."""

    def test_serialize_option(self):
        """Test serializing a VanillaOption."""
        opt = VanillaOption()
        opt.Spot.set(105.0)
        opt.Strike.set(100.0)
        opt.Volatility.set(0.25)

        data = serialize_instrument(opt)

        assert data["Spot"] == 105.0
        assert data["Strike"] == 100.0
        assert data["Volatility"] == 0.25

    def test_serialize_bond(self):
        """Test serializing a Bond."""
        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.YieldToMaturity.set(0.05)

        data = serialize_instrument(bond)

        assert data["FaceValue"] == 1000.0
        assert data["YieldToMaturity"] == 0.05

    def test_deserialize_option(self):
        """Test deserializing a VanillaOption."""
        data = {
            "Spot": 110.0,
            "Strike": 105.0,
            "Volatility": 0.30,
            "Rate": 0.05,
            "TimeToExpiry": 0.5,
        }

        opt = deserialize_instrument("lattice.VanillaOption", data)

        assert opt.Spot() == 110.0
        assert opt.Strike() == 105.0
        assert opt.Volatility() == 0.30

    def test_roundtrip_serialization(self):
        """Test serialize then deserialize."""
        original = VanillaOption()
        original.Spot.set(120.0)
        original.Strike.set(115.0)
        original.Volatility.set(0.35)

        data = serialize_instrument(original)
        type_name = f"{original.__class__.__module__}.{original.__class__.__name__}"

        restored = deserialize_instrument(type_name, data)

        assert restored.Spot() == original.Spot()
        assert restored.Strike() == original.Strike()
        assert restored.Volatility() == original.Volatility()


class TestLoadInstrument:
    """Tests for _load_instrument helper."""

    def test_load_from_serialized(self):
        """Test loading from serialized state."""
        ref = InstrumentRef(
            serialized_state={"Spot": 100.0, "Strike": 100.0},
            type_name="lattice.VanillaOption",
        )

        inst = _load_instrument(ref)

        assert inst.Spot() == 100.0
        assert inst.Strike() == 100.0

    def test_load_invalid_ref_raises(self):
        """Test that invalid ref raises ValueError."""
        ref = InstrumentRef()

        with pytest.raises(ValueError, match="must have either"):
            _load_instrument(ref)

    def test_load_store_path_without_uri_raises(self):
        """Test that store path without URI raises."""
        ref = InstrumentRef(store_path="/Instruments/AAPL")

        with pytest.raises(ValueError, match="must have either"):
            _load_instrument(ref, store_uri=None)


class TestActivityLogic:
    """Tests for activity computation logic (without Temporal)."""

    def test_compute_greeks_option(self):
        """Test computing Greeks for an option."""
        import asyncio

        pytest.importorskip("temporalio")
        from lattice.workflows.activities import compute_instrument_greeks

        opt = VanillaOption()
        opt.Spot.set(100.0)
        opt.Strike.set(100.0)
        opt.Volatility.set(0.20)
        opt.Rate.set(0.05)
        opt.TimeToExpiry.set(1.0)

        ref = InstrumentRef(
            serialized_state=serialize_instrument(opt),
            type_name="lattice.VanillaOption",
        )

        result = asyncio.run(
            compute_instrument_greeks(
                instrument_name="TEST_OPT",
                instrument_ref=ref,
                bump=0.01,
            )
        )

        assert result.instrument_name == "TEST_OPT"
        assert result.delta is not None
        assert 0.4 < result.delta < 0.7
        assert result.gamma is not None
        assert result.gamma > 0
        assert result.vega is not None
        assert result.theta is not None
        assert result.rho is not None
        assert result.error is None

    def test_compute_greeks_bond(self):
        """Test computing Greeks for a bond (only DV01)."""
        import asyncio

        pytest.importorskip("temporalio")
        from lattice.workflows.activities import compute_instrument_greeks

        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.YieldToMaturity.set(0.05)
        bond.Maturity.set(10.0)

        ref = InstrumentRef(
            serialized_state=serialize_instrument(bond),
            type_name="lattice.Bond",
        )

        result = asyncio.run(
            compute_instrument_greeks(
                instrument_name="TEST_BOND",
                instrument_ref=ref,
            )
        )

        assert result.instrument_name == "TEST_BOND"
        assert result.delta is None
        assert result.gamma is None
        assert result.vega is None
        assert result.dv01 is not None
        assert result.dv01 > 0

    def test_compute_stress_test(self):
        """Test stress testing an option."""
        import asyncio

        pytest.importorskip("temporalio")
        from lattice.workflows.activities import compute_stress_test

        opt = VanillaOption()
        opt.Spot.set(100.0)
        opt.Strike.set(100.0)
        opt.Volatility.set(0.20)

        ref = InstrumentRef(
            serialized_state=serialize_instrument(opt),
            type_name="lattice.VanillaOption",
        )

        result = asyncio.run(
            compute_stress_test(
                instrument_name="TEST_OPT",
                instrument_ref=ref,
                shocks={"Spot": -0.10},
            )
        )

        assert result["instrument_name"] == "TEST_OPT"
        assert "base_price" in result
        assert "stressed_price" in result
        assert "price_impact" in result
        assert result["price_impact"] < 0


def _has_temporalio():
    """Check if temporalio is available."""
    try:
        import temporalio
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_temporalio(), reason="temporalio not installed")
class TestWorkflowIntegration:
    """Integration tests with Temporal testing environment.

    These tests use Temporal's built-in test environment which doesn't
    require a real Temporal server.
    """

    def test_compute_greeks_workflow(self):
        """Test the full Greeks workflow with Temporal test environment."""
        import asyncio
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporalio.worker.workflow_sandbox import (
            SandboxedWorkflowRunner,
            SandboxRestrictions,
        )
        from lattice.workflows import (
            ComputeGreeksWorkflow,
            StressTestWorkflow,
            InstrumentRef,
            compute_instrument_greeks,
            compute_stress_test,
        )

        opt = VanillaOption()
        opt.Spot.set(100.0)
        opt.Strike.set(100.0)

        instruments = {
            "OPT_1": asdict(
                InstrumentRef(
                    serialized_state=serialize_instrument(opt),
                    type_name="lattice.VanillaOption",
                )
            ),
        }

        async def run_test():
            async with await WorkflowEnvironment.start_local() as env:
                worker = Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[ComputeGreeksWorkflow, StressTestWorkflow],
                    activities=[compute_instrument_greeks, compute_stress_test],
                    workflow_runner=SandboxedWorkflowRunner(
                        restrictions=SandboxRestrictions.default.with_passthrough_modules(
                            "numpy", "dag", "lattice"
                        )
                    ),
                )
                async with worker:
                    result = await env.client.execute_workflow(
                        ComputeGreeksWorkflow.run,
                        args=[instruments, 0.01, None],
                        id="test-greeks-1",
                        task_queue="test-queue",
                    )
                    return result

        result = asyncio.run(run_test())

        assert "OPT_1" in result
        assert result["OPT_1"]["delta"] is not None

    def test_stress_test_workflow(self):
        """Test the full stress test workflow with Temporal test environment."""
        import asyncio
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from temporalio.worker.workflow_sandbox import (
            SandboxedWorkflowRunner,
            SandboxRestrictions,
        )
        from lattice.workflows import (
            ComputeGreeksWorkflow,
            StressTestWorkflow,
            InstrumentRef,
            compute_instrument_greeks,
            compute_stress_test,
        )

        opt = VanillaOption()
        opt.Spot.set(100.0)
        opt.Strike.set(100.0)

        instruments = {
            "OPT_1": asdict(
                InstrumentRef(
                    serialized_state=serialize_instrument(opt),
                    type_name="lattice.VanillaOption",
                )
            ),
        }

        async def run_test():
            async with await WorkflowEnvironment.start_local() as env:
                worker = Worker(
                    env.client,
                    task_queue="test-queue",
                    workflows=[ComputeGreeksWorkflow, StressTestWorkflow],
                    activities=[compute_instrument_greeks, compute_stress_test],
                    workflow_runner=SandboxedWorkflowRunner(
                        restrictions=SandboxRestrictions.default.with_passthrough_modules(
                            "numpy", "dag", "lattice"
                        )
                    ),
                )
                async with worker:
                    result = await env.client.execute_workflow(
                        StressTestWorkflow.run,
                        args=[instruments, {"Spot": -0.10}, None],
                        id="test-stress-1",
                        task_queue="test-queue",
                    )
                    return result

        result = asyncio.run(run_test())

        assert "OPT_1" in result
        assert result["OPT_1"]["price_impact"] < 0


class _Dated(dag.Model):
    """Instrument-like model with inputs the wire format must not drop."""

    @dag.computed(dag.Input)
    def Expiry(self):
        return datetime(2030, 1, 1)

    @dag.computed(dag.Input)
    def Lots(self):
        return 1

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        return 100.0

    @dag.computed
    def Price(self) -> float:
        return self.Spot() * self.Lots()


class TestWorkerSeesCallerState:
    """A worker prices the instrument the caller has, market data included."""

    def test_stored_instrument_is_sent_inline(self):
        from lattice.store import connect
        from lattice.workflows.client import _instrument_to_ref

        store = connect("memory://")
        store.register_type("/Instruments/*", VanillaOption)
        opt = store.new(VanillaOption, "/Instruments/OPT")
        opt.Spot.set(123.0)
        opt.Volatility.set(0.35)

        ref = _instrument_to_ref(opt)
        assert ref.type_name.endswith("VanillaOption")
        assert ref.serialized_state["Spot"] == 123.0

        restored = _load_instrument(ref)
        assert restored.Spot() == 123.0
        assert restored.Price() == pytest.approx(opt.Price())

    def test_activity_computes_greeks_for_stored_instrument(self):
        import asyncio
        from lattice.store import connect
        from lattice.workflows.activities import compute_instrument_greeks
        from lattice.workflows.client import _instrument_to_ref

        store = connect("memory://")
        store.register_type("/Instruments/*", VanillaOption)
        opt = store.new(VanillaOption, "/Instruments/OPT")
        opt.Spot.set(110.0)

        result = asyncio.run(
            compute_instrument_greeks("OPT", _instrument_to_ref(opt))
        )
        assert result.error is None
        assert result.delta == pytest.approx(opt.Delta(), rel=1e-2)

    def test_datetime_and_numpy_inputs_survive(self):
        import numpy as np

        inst = _Dated()
        inst.Expiry.set(datetime(2027, 6, 30, 16, 0))
        inst.Lots.set(np.int64(5))

        data = serialize_instrument(inst)
        restored = deserialize_instrument(f"{__name__}._Dated", data)
        assert restored.Expiry() == datetime(2027, 6, 30, 16, 0)
        assert restored.Lots() == 5
        assert restored.Price() == 500.0

    def test_only_explicitly_set_inputs_are_sent(self):
        from lattice import InterestRateSwap

        swap = InterestRateSwap()
        swap.DiscountRate.set(0.04)
        data = serialize_instrument(swap)
        assert data == {"DiscountRate": 0.04}

        # The worker's FloatingRate still follows its DiscountRate.
        restored = deserialize_instrument("lattice.InterestRateSwap", data)
        assert restored.FloatingRate() == 0.04

        swap.FloatingRate.set(0.02)
        assert serialize_instrument(swap)["FloatingRate"] == 0.02

    def test_unsendable_input_raises(self):
        from lattice import Position
        from lattice.store import SerializationError

        pos = Position()
        pos.LinkedInstrument.set(VanillaOption())
        with pytest.raises(SerializationError, match="LinkedInstrument"):
            serialize_instrument(pos)

    def test_store_path_ref_needs_type_name(self):
        ref = InstrumentRef(store_path="/Instruments/OPT")
        with pytest.raises(ValueError, match="type_name"):
            _load_instrument(ref, store_uri="memory://")

    def test_store_path_ref_loads_with_type_name(self, tmp_path):
        from lattice.store import connect

        uri = f"sqlite:///{tmp_path / 'store.db'}"
        store = connect(uri)
        store.register_type("/Instruments/*", VanillaOption)
        opt = store.new(VanillaOption, "/Instruments/OPT")
        opt.Strike.set(150.0)
        opt.save()
        store.close()

        ref = InstrumentRef(
            store_path="/Instruments/OPT", type_name="lattice.VanillaOption"
        )
        assert _load_instrument(ref, store_uri=uri).Strike() == 150.0

    def test_forward_and_swap_get_greeks(self):
        import asyncio
        from lattice import Forward, InterestRateSwap
        from lattice.workflows.activities import compute_instrument_greeks
        from lattice.workflows.client import _instrument_to_ref

        fwd = asyncio.run(
            compute_instrument_greeks("FWD", _instrument_to_ref(Forward()))
        )
        assert fwd.delta == pytest.approx(1.0, rel=1e-6)

        swap = InterestRateSwap()
        res = asyncio.run(
            compute_instrument_greeks("SWAP", _instrument_to_ref(swap))
        )
        assert res.dv01 == pytest.approx(swap.DV01(), rel=1e-2)


class TestDistributedErrorsSurface:
    """RiskEngine does not hide a worker-side failure."""

    def test_error_is_returned_and_logged(self, monkeypatch, caplog):
        import asyncio
        import lattice.workflows as workflows
        from lattice.risk import RiskEngine

        async def fake_compute_greeks_async(instruments, **kwargs):
            return {
                "GOOD": {"instrument_name": "GOOD", "delta": 0.5, "error": None},
                "BAD": {
                    "instrument_name": "BAD",
                    "delta": None,
                    "error": "Failed to load instrument: boom",
                },
            }

        monkeypatch.setattr(workflows, "compute_greeks_async", fake_compute_greeks_async)

        engine = RiskEngine()
        engine.add(VanillaOption(), "GOOD")
        engine.add(VanillaOption(), "BAD")
        with caplog.at_level("WARNING"):
            results = asyncio.run(engine.compute_greeks_distributed())

        assert results["GOOD"] == {"delta": 0.5}
        assert results["BAD"] == {"error": "Failed to load instrument: boom"}
        assert "BAD" in caplog.text
