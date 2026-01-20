"""
Lattice - Quant pricing and trading library.

Built on dag (computation graphs) and livetable (fast tables).

Submodules:
    lattice.ui - Reactive web UI framework (DagApp, show, bind)
    lattice.risk - Risk analysis and sensitivity calculations
    lattice.store - Path-based persistent storage for dag.Model objects
"""

import dag

# Re-export dag's scenario for convenience
scenario = dag.scenario
flush = dag.flush
reset = dag.reset

from .instruments import VanillaOption, Stock, Bond, InterestRateSwap, Forward, Future, FXPair, FXForward
from .trading import PositionTable, TradeBlotter, TradingDashboard, Book, Trade, Position, TradingSystem
from . import risk
from . import store

__all__ = [
    # Core functions
    "scenario",
    "flush",
    "reset",
    # Submodules
    "risk",
    "store",
    # Instruments - Options
    "VanillaOption",
    # Instruments - Equity
    "Stock",
    # Instruments - Fixed Income
    "Bond",
    "InterestRateSwap",
    # Instruments - Derivatives
    "Forward",
    "Future",
    # Instruments - FX
    "FXPair",
    "FXForward",
    # Trading - Legacy table-based
    "PositionTable",
    "TradeBlotter",
    "TradingDashboard",
    # Trading - dag.Model-based
    "Book",
    "Trade",
    "Position",
    "TradingSystem",
]

__version__ = "0.1.0"
