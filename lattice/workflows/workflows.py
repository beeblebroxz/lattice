"""Temporal workflows for Lattice risk calculations.

Workflows orchestrate activities into durable, reliable computations.
They provide automatic retries, progress tracking, and can survive
worker restarts.

Example:
    from temporalio.client import Client

    client = await Client.connect("localhost:7233")

    # Start the workflow
    result = await client.execute_workflow(
        ComputeGreeksWorkflow.run,
        args=[instruments, 0.01, "sqlite:///trading.db"],
        id="greeks-batch-001",
        task_queue="lattice-risk",
    )
"""

import asyncio
from dataclasses import asdict
from datetime import timedelta
from typing import Any, Dict, List, Optional

try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    workflow = None
    RetryPolicy = None

from .activities import (
    InstrumentRef,
    GreeksResult,
    compute_instrument_greeks,
    compute_stress_test,
)


def _workflow_defn(cls):
    """Decorator that applies @workflow.defn if available."""
    if TEMPORALIO_AVAILABLE:
        return workflow.defn(cls)
    return cls


def _workflow_run(fn):
    """Decorator that applies @workflow.run if available."""
    if TEMPORALIO_AVAILABLE:
        return workflow.run(fn)
    return fn


@_workflow_defn
class ComputeGreeksWorkflow:
    """Workflow to compute Greeks for multiple instruments in parallel.

    This workflow fans out to compute Greeks for each instrument concurrently,
    then aggregates the results. Each instrument calculation is an independent
    activity that can be retried on failure.

    Benefits over sequential computation:
    - Parallel execution across instruments
    - Automatic retries on numerical errors
    - Progress tracking via Temporal UI
    - Durability - can resume after worker restart

    Example:
        instruments = {
            "AAPL_C_150": InstrumentRef(store_path="/Instruments/AAPL_C_150"),
            "AAPL_P_145": InstrumentRef(store_path="/Instruments/AAPL_P_145"),
        }

        result = await client.execute_workflow(
            ComputeGreeksWorkflow.run,
            args=[instruments, 0.01, "sqlite:///trading.db"],
            id="greeks-batch-001",
            task_queue="lattice-risk",
        )
    """

    @_workflow_run
    async def run(
        self,
        instruments: Dict[str, Dict[str, Any]],
        bump: float = 0.01,
        store_uri: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Execute the Greeks calculation workflow.

        Args:
            instruments: Map of instrument name to InstrumentRef as dict
                         (Temporal serializes dataclasses as dicts)
            bump: Bump size for numerical differentiation
            store_uri: Store connection string if using persistence

        Returns:
            Dict mapping instrument name to GreeksResult as dict
        """
        if not TEMPORALIO_AVAILABLE:
            raise RuntimeError(
                "temporalio is not installed. Install with: pip install lattice[temporal]"
            )

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
            non_retryable_error_types=["ValueError"],
        )

        tasks = []
        names = []

        for name, ref_dict in instruments.items():
            ref = InstrumentRef(**ref_dict) if isinstance(ref_dict, dict) else ref_dict
            names.append(name)
            task = workflow.execute_activity(
                compute_instrument_greeks,
                args=[name, ref, bump, store_uri],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                output[name] = {"instrument_name": name, "error": str(result)}
            elif isinstance(result, GreeksResult):
                output[name] = asdict(result)
            elif isinstance(result, dict):
                output[name] = result
            else:
                output[name] = {"instrument_name": name, "error": "Unknown result type"}

        return output


@_workflow_defn
class StressTestWorkflow:
    """Workflow to run stress tests across multiple instruments.

    Similar to ComputeGreeksWorkflow but applies stress scenarios
    instead of computing Greeks.

    Example:
        instruments = {
            "AAPL_C_150": InstrumentRef(store_path="/Instruments/AAPL_C_150"),
        }
        shocks = {"Spot": -0.10, "Volatility": 0.05}

        result = await client.execute_workflow(
            StressTestWorkflow.run,
            args=[instruments, shocks, "sqlite:///trading.db"],
            id="stress-test-001",
            task_queue="lattice-risk",
        )
    """

    @_workflow_run
    async def run(
        self,
        instruments: Dict[str, Dict[str, Any]],
        shocks: Dict[str, float],
        store_uri: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Execute the stress test workflow.

        Args:
            instruments: Map of instrument name to InstrumentRef as dict
            shocks: Dict of input_name -> relative shock
            store_uri: Store connection string if using persistence

        Returns:
            Dict mapping instrument name to stress test results
        """
        if not TEMPORALIO_AVAILABLE:
            raise RuntimeError(
                "temporalio is not installed. Install with: pip install lattice[temporal]"
            )

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        tasks = []
        names = []

        for name, ref_dict in instruments.items():
            ref = InstrumentRef(**ref_dict) if isinstance(ref_dict, dict) else ref_dict
            names.append(name)
            task = workflow.execute_activity(
                compute_stress_test,
                args=[name, ref, shocks, store_uri],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                output[name] = {"instrument_name": name, "error": str(result)}
            elif isinstance(result, dict):
                output[name] = result
            else:
                output[name] = {"instrument_name": name, "error": "Unknown result type"}

        return output


@_workflow_defn
class BatchRiskWorkflow:
    """Combined workflow for Greeks and stress testing.

    Runs both Greeks calculation and stress testing in sequence,
    providing a comprehensive risk report.

    Example:
        result = await client.execute_workflow(
            BatchRiskWorkflow.run,
            args=[instruments, 0.01, {"Spot": -0.10}, "sqlite:///trading.db"],
            id="batch-risk-001",
            task_queue="lattice-risk",
        )
    """

    @_workflow_run
    async def run(
        self,
        instruments: Dict[str, Dict[str, Any]],
        bump: float = 0.01,
        shocks: Optional[Dict[str, float]] = None,
        store_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute combined risk calculations.

        Args:
            instruments: Map of instrument name to InstrumentRef as dict
            bump: Bump size for Greeks calculation
            shocks: Dict of shocks for stress testing (optional)
            store_uri: Store connection string

        Returns:
            Dict with "greeks" and "stress" (if shocks provided) results
        """
        if not TEMPORALIO_AVAILABLE:
            raise RuntimeError(
                "temporalio is not installed. Install with: pip install lattice[temporal]"
            )

        greeks_workflow = ComputeGreeksWorkflow()
        greeks_result = await greeks_workflow.run(instruments, bump, store_uri)

        result = {"greeks": greeks_result}

        if shocks:
            stress_workflow = StressTestWorkflow()
            stress_result = await stress_workflow.run(instruments, shocks, store_uri)
            result["stress"] = stress_result

        return result
