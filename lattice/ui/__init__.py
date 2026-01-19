"""
Lattice UI Framework - Reactive web UI for dag models.

Example:
    from lattice import VanillaOption
    from lattice.ui import show, DagApp, bind

    # Quick display in Jupyter
    option = VanillaOption()
    show(option)  # Opens IFrame with auto-generated UI

    # Custom app with layout
    app = DagApp("Option Pricer")
    app.register(option, name="option")
    app.layout = {
        "title": "Black-Scholes Pricer",
        "sections": [
            {"name": "Market", "inputs": [
                bind(option.Spot, label="Spot"),
                bind(option.Volatility, label="Vol", format="%"),
            ]},
            {"name": "Results", "outputs": [
                bind(option.Price, label="Price", format="$,.4f"),
                bind(option.Delta, label="Delta"),
            ]}
        ]
    }
    app.show()  # Jupyter
    # OR
    app.run(port=8080)  # Standalone
"""

from .bindings import bind, InputBinding, OutputBinding, TwoWayBinding
from .app import DagApp, show

__all__ = [
    "DagApp",
    "show",
    "bind",
    "InputBinding",
    "OutputBinding",
    "TwoWayBinding",
]
