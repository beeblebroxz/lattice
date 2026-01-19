"""Temporal worker for Lattice risk calculations.

This module provides the worker that executes Lattice workflows and activities.
Run this as a standalone process to handle workflow tasks.

Usage:
    # Start worker with default settings
    python -m lattice.workflows.worker

    # Start worker with custom settings
    python -m lattice.workflows.worker --host localhost:7233 --queue lattice-risk

    # Or programmatically
    import asyncio
    from lattice.workflows.worker import run_worker
    asyncio.run(run_worker())
"""

import argparse
import asyncio
import logging
from typing import Optional

try:
    from temporalio.client import Client
    from temporalio.worker import Worker
    from temporalio.worker.workflow_sandbox import (
        SandboxedWorkflowRunner,
        SandboxRestrictions,
    )

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    Client = None
    Worker = None
    SandboxedWorkflowRunner = None
    SandboxRestrictions = None

from .activities import compute_instrument_greeks, compute_stress_test
from .workflows import ComputeGreeksWorkflow, StressTestWorkflow, BatchRiskWorkflow


DEFAULT_TASK_QUEUE = "lattice-risk"
DEFAULT_TEMPORAL_HOST = "localhost:7233"


async def create_worker(
    client: "Client",
    task_queue: str = DEFAULT_TASK_QUEUE,
) -> "Worker":
    """Create a Temporal worker configured for Lattice workflows.

    Args:
        client: Connected Temporal client
        task_queue: Task queue name to listen on

    Returns:
        Configured Worker instance (not yet running)

    Raises:
        RuntimeError: If temporalio is not installed
    """
    if not TEMPORALIO_AVAILABLE:
        raise RuntimeError(
            "temporalio is not installed. Install with: pip install lattice[temporal]"
        )

    return Worker(
        client,
        task_queue=task_queue,
        workflows=[
            ComputeGreeksWorkflow,
            StressTestWorkflow,
            BatchRiskWorkflow,
        ],
        activities=[
            compute_instrument_greeks,
            compute_stress_test,
        ],
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules(
                "numpy", "dag", "lattice", "livetable"
            )
        ),
    )


async def run_worker(
    temporal_host: str = DEFAULT_TEMPORAL_HOST,
    task_queue: str = DEFAULT_TASK_QUEUE,
    namespace: str = "default",
) -> None:
    """Start a Temporal worker for Lattice risk calculations.

    This function connects to a Temporal server and starts processing
    workflow and activity tasks. It runs until interrupted (Ctrl+C).

    Args:
        temporal_host: Temporal server address (host:port)
        task_queue: Task queue name to listen on
        namespace: Temporal namespace

    Raises:
        RuntimeError: If temporalio is not installed

    Example:
        import asyncio
        from lattice.workflows.worker import run_worker

        asyncio.run(run_worker(
            temporal_host="localhost:7233",
            task_queue="lattice-risk",
        ))
    """
    if not TEMPORALIO_AVAILABLE:
        raise RuntimeError(
            "temporalio is not installed. Install with: pip install lattice[temporal]"
        )

    logging.info(
        f"Connecting to Temporal at {temporal_host}, namespace={namespace}"
    )

    client = await Client.connect(temporal_host, namespace=namespace)

    logging.info(f"Starting worker on task queue: {task_queue}")

    worker = await create_worker(client, task_queue)

    logging.info("Worker started. Waiting for tasks...")
    await worker.run()


def main() -> None:
    """Entry point for running the worker from command line."""
    parser = argparse.ArgumentParser(
        description="Start Lattice Temporal worker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_TEMPORAL_HOST,
        help="Temporal server address (host:port)",
    )
    parser.add_argument(
        "--queue",
        default=DEFAULT_TASK_QUEUE,
        help="Task queue name",
    )
    parser.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        asyncio.run(
            run_worker(
                temporal_host=args.host,
                task_queue=args.queue,
                namespace=args.namespace,
            )
        )
    except KeyboardInterrupt:
        logging.info("Worker stopped")


if __name__ == "__main__":
    main()
