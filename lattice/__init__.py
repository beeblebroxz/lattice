"""
Lattice - Quant pricing and trading library.

Built on dag (computation graphs) and livetable (fast tables).
"""

import dag

# Re-export dag's scenario for convenience
scenario = dag.scenario
flush = dag.flush
reset = dag.reset

from .instruments import VanillaOption
from .trading import PositionTable, TradeBlotter

__all__ = [
    # Core functions
    "scenario",
    "flush",
    "reset",
    # Instruments
    "VanillaOption",
    # Trading
    "PositionTable",
    "TradeBlotter",
]

__version__ = "0.1.0"
