"""High-level client API for Lattice Temporal workflows.

This module provides convenient functions for executing Lattice workflows
without needing to interact with the Temporal client directly.

Example:
    from lattice import VanillaOption
    from lattice.workflows import compute_greeks_async
    import asyncio

    # Create some instruments
    options = {}
    for i in range(10):
        opt = VanillaOption()
        opt.Spot.set(100 + i)
        options[f"OPT_{i}"] = opt

    # Compute Greeks via Temporal (parallel, durable)
    results = asyncio.run(compute_greeks_async(options))
"""

from dataclasses import asdict
from typing import Any, Dict, Optional
from uuid import uuid4

try:
    from temporalio.client import Client

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    Client = None

import dag

from .activities import InstrumentRef, GreeksResult, serialize_instrument
from .workflows import ComputeGreeksWorkflow, StressTestWorkflow, BatchRiskWorkflow
from .worker import DEFAULT_TASK_QUEUE, DEFAULT_TEMPORAL_HOST


def _check_temporalio():
    """Check if temporalio is available and raise if not."""
    if not TEMPORALIO_AVAILABLE:
        raise RuntimeError(
            "temporalio is not installed. Install with: pip install lattice[temporal]"
        )


def _instrument_to_ref(inst: dag.Model) -> InstrumentRef:
    """Convert a dag.Model instrument to an InstrumentRef.

    Prefers store path if available, falls back to inline serialization.

    Args:
        inst: The instrument

    Returns:
        InstrumentRef that can be passed to activities
    """
    if hasattr(inst, "path") and inst.path():
        return InstrumentRef(store_path=inst.path())
    else:
        type_name = f"{inst.__class__.__module__}.{inst.__class__.__name__}"
        return InstrumentRef(
            serialized_state=serialize_instrument(inst),
            type_name=type_name,
        )


async def compute_greeks_async(
    instruments: Dict[str, dag.Model],
    bump: float = 0.01,
    store_uri: Optional[str] = None,
    temporal_host: str = DEFAULT_TEMPORAL_HOST,
    task_queue: str = DEFAULT_TASK_QUEUE,
    namespace: str = "default",
    workflow_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute Greeks for multiple instruments via Temporal workflow.

    This is the main entry point for distributed Greeks calculation.
    Each instrument is processed in parallel with automatic retries.

    Args:
        instruments: Dict mapping name to dag.Model instrument
        bump: Bump size for numerical differentiation
        store_uri: Store connection string (if instruments are in a Store)
        temporal_host: Temporal server address
        task_queue: Task queue name
        namespace: Temporal namespace
        workflow_id: Custom workflow ID (auto-generated if None)

    Returns:
        Dict mapping instrument name to Greeks result dict

    Raises:
        RuntimeError: If temporalio is not installed

    Example:
        from lattice import VanillaOption
        from lattice.workflows import compute_greeks_async
        import asyncio

        opt1 = VanillaOption()
        opt1.Spot.set(100)
        opt2 = VanillaOption()
        opt2.Spot.set(110)

        results = asyncio.run(compute_greeks_async({
            "OPT_1": opt1,
            "OPT_2": opt2,
        }))

        print(results["OPT_1"]["delta"])
    """
    _check_temporalio()
    client = await Client.connect(temporal_host, namespace=namespace)

    refs = {name: asdict(_instrument_to_ref(inst)) for name, inst in instruments.items()}

    if workflow_id is None:
        workflow_id = f"compute-greeks-{uuid4()}"

    result = await client.execute_workflow(
        ComputeGreeksWorkflow.run,
        args=[refs, bump, store_uri],
        id=workflow_id,
        task_queue=task_queue,
    )

    return result


async def stress_test_async(
    instruments: Dict[str, dag.Model],
    shocks: Dict[str, float],
    store_uri: Optional[str] = None,
    temporal_host: str = DEFAULT_TEMPORAL_HOST,
    task_queue: str = DEFAULT_TASK_QUEUE,
    namespace: str = "default",
    workflow_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Run stress test on multiple instruments via Temporal workflow.

    Args:
        instruments: Dict mapping name to dag.Model instrument
        shocks: Dict of input_name -> relative shock
        store_uri: Store connection string
        temporal_host: Temporal server address
        task_queue: Task queue name
        namespace: Temporal namespace
        workflow_id: Custom workflow ID

    Returns:
        Dict mapping instrument name to stress test results

    Raises:
        RuntimeError: If temporalio is not installed

    Example:
        results = await stress_test_async(
            instruments={"OPT_1": opt1},
            shocks={"Spot": -0.10, "Volatility": 0.05},
        )
        print(results["OPT_1"]["price_impact"])
    """
    _check_temporalio()
    client = await Client.connect(temporal_host, namespace=namespace)

    refs = {name: asdict(_instrument_to_ref(inst)) for name, inst in instruments.items()}

    if workflow_id is None:
        workflow_id = f"stress-test-{uuid4()}"

    result = await client.execute_workflow(
        StressTestWorkflow.run,
        args=[refs, shocks, store_uri],
        id=workflow_id,
        task_queue=task_queue,
    )

    return result


async def batch_risk_async(
    instruments: Dict[str, dag.Model],
    bump: float = 0.01,
    shocks: Optional[Dict[str, float]] = None,
    store_uri: Optional[str] = None,
    temporal_host: str = DEFAULT_TEMPORAL_HOST,
    task_queue: str = DEFAULT_TASK_QUEUE,
    namespace: str = "default",
    workflow_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run combined Greeks and stress test via Temporal workflow.

    Args:
        instruments: Dict mapping name to dag.Model instrument
        bump: Bump size for Greeks calculation
        shocks: Dict of shocks for stress testing (optional)
        store_uri: Store connection string
        temporal_host: Temporal server address
        task_queue: Task queue name
        namespace: Temporal namespace
        workflow_id: Custom workflow ID

    Returns:
        Dict with "greeks" and optionally "stress" results

    Raises:
        RuntimeError: If temporalio is not installed
    """
    _check_temporalio()
    client = await Client.connect(temporal_host, namespace=namespace)

    refs = {name: asdict(_instrument_to_ref(inst)) for name, inst in instruments.items()}

    if workflow_id is None:
        workflow_id = f"batch-risk-{uuid4()}"

    result = await client.execute_workflow(
        BatchRiskWorkflow.run,
        args=[refs, bump, shocks, store_uri],
        id=workflow_id,
        task_queue=task_queue,
    )

    return result


class LatticeTemporalClient:
    """Reusable client for Lattice Temporal workflows.

    Use this when making multiple workflow calls to avoid reconnecting
    to Temporal for each request.

    Example:
        async with LatticeTemporalClient() as client:
            greeks1 = await client.compute_greeks(instruments1)
            greeks2 = await client.compute_greeks(instruments2)
            stress = await client.stress_test(instruments1, shocks)
    """

    def __init__(
        self,
        temporal_host: str = DEFAULT_TEMPORAL_HOST,
        task_queue: str = DEFAULT_TASK_QUEUE,
        namespace: str = "default",
    ):
        self.temporal_host = temporal_host
        self.task_queue = task_queue
        self.namespace = namespace
        self._client: Optional[Client] = None

    async def __aenter__(self) -> "LatticeTemporalClient":
        self._client = await Client.connect(self.temporal_host, namespace=self.namespace)
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def connect(self) -> None:
        """Explicitly connect to Temporal (alternative to async context manager)."""
        _check_temporalio()
        if self._client is None:
            self._client = await Client.connect(
                self.temporal_host, namespace=self.namespace
            )

    async def compute_greeks(
        self,
        instruments: Dict[str, dag.Model],
        bump: float = 0.01,
        store_uri: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute Greeks via workflow."""
        if self._client is None:
            await self.connect()

        refs = {
            name: asdict(_instrument_to_ref(inst)) for name, inst in instruments.items()
        }

        if workflow_id is None:
            workflow_id = f"compute-greeks-{uuid4()}"

        return await self._client.execute_workflow(
            ComputeGreeksWorkflow.run,
            args=[refs, bump, store_uri],
            id=workflow_id,
            task_queue=self.task_queue,
        )

    async def stress_test(
        self,
        instruments: Dict[str, dag.Model],
        shocks: Dict[str, float],
        store_uri: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Run stress test via workflow."""
        if self._client is None:
            await self.connect()

        refs = {
            name: asdict(_instrument_to_ref(inst)) for name, inst in instruments.items()
        }

        if workflow_id is None:
            workflow_id = f"stress-test-{uuid4()}"

        return await self._client.execute_workflow(
            StressTestWorkflow.run,
            args=[refs, shocks, store_uri],
            id=workflow_id,
            task_queue=self.task_queue,
        )
