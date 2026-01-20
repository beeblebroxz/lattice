"""Financial instruments."""

from .options import VanillaOption
from .equity import Stock
from .fixedincome import Bond, InterestRateSwap
from .derivatives import Forward, Future
from .fx import FXPair, FXForward

__all__ = [
    # Options
    "VanillaOption",
    # Equity
    "Stock",
    # Fixed Income
    "Bond",
    "InterestRateSwap",
    # Derivatives
    "Forward",
    "Future",
    # FX
    "FXPair",
    "FXForward",
]
