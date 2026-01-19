"""Temporal workflows for distributed Lattice computations.

This module provides Temporal workflow integration for Lattice, enabling
durable, parallel execution of risk calculations across workers.

Quick Start:
    # 1. Start Temporal server
    temporal server start-dev

    # 2. Start worker
    python -m lattice.workflows.worker

    # 3. Run workflows from your code
    from lattice import VanillaOption
    from lattice.workflows import compute_greeks_async
    import asyncio

    opt = VanillaOption()
    opt.Spot.set(100)

    results = asyncio.run(compute_greeks_async({"OPT_1": opt}))

Key Functions:
    compute_greeks_async: Compute Greeks for multiple instruments in parallel
    stress_test_async: Run stress tests in parallel
    batch_risk_async: Combined Greeks + stress testing

Workflows:
    ComputeGreeksWorkflow: Fan-out/fan-in Greeks calculation
    StressTestWorkflow: Fan-out/fan-in stress testing
    BatchRiskWorkflow: Combined risk workflow

Activities:
    compute_instrument_greeks: Calculate Greeks for one instrument
    compute_stress_test: Calculate stress impact for one instrument

Data Classes:
    InstrumentRef: Reference to an instrument (by path or serialized state)
    GreeksResult: Result of Greeks calculation

Worker:
    run_worker: Start a worker process
    create_worker: Create a configured worker instance
"""

from .activities import (
    InstrumentRef,
    GreeksResult,
    serialize_instrument,
    deserialize_instrument,
    compute_instrument_greeks,
    compute_stress_test,
)

from .workflows import (
    ComputeGreeksWorkflow,
    StressTestWorkflow,
    BatchRiskWorkflow,
)

from .worker import (
    run_worker,
    create_worker,
    DEFAULT_TASK_QUEUE,
    DEFAULT_TEMPORAL_HOST,
)

from .client import (
    compute_greeks_async,
    stress_test_async,
    batch_risk_async,
    LatticeTemporalClient,
)

__all__ = [
    # Data classes
    "InstrumentRef",
    "GreeksResult",
    # Serialization helpers
    "serialize_instrument",
    "deserialize_instrument",
    # Activities
    "compute_instrument_greeks",
    "compute_stress_test",
    # Workflows
    "ComputeGreeksWorkflow",
    "StressTestWorkflow",
    "BatchRiskWorkflow",
    # Worker
    "run_worker",
    "create_worker",
    "DEFAULT_TASK_QUEUE",
    "DEFAULT_TEMPORAL_HOST",
    # Client helpers
    "compute_greeks_async",
    "stress_test_async",
    "batch_risk_async",
    "LatticeTemporalClient",
]
