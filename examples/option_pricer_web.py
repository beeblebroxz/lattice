#!/usr/bin/env python3
"""
Interactive Black-Scholes Option Pricer with Web UI.

Run this script and open http://localhost:8080 in your browser.
Edit the inputs and watch the option price and Greeks update in real-time.

Usage:
    python examples/option_pricer_web.py
"""

from lattice import VanillaOption
from lattice.ui import DagApp, bind


def main():
    # Create the option model
    option = VanillaOption()

    # Set some initial values
    option.Strike.set(100.0)
    option.Spot.set(100.0)
    option.Volatility.set(0.20)
    option.Rate.set(0.05)
    option.TimeToExpiry.set(1.0)
    option.IsCall.set(True)

    # Create the app
    app = DagApp("Black-Scholes Option Pricer")
    app.register(option, name="option")

    # Define the layout with bindings
    app.add_section(
        "Market Data",
        inputs=[
            bind(option.Spot, label="Spot Price", format="$,.2f"),
            bind(option.Strike, label="Strike Price", format="$,.2f"),
        ],
    )

    app.add_section(
        "Model Parameters",
        inputs=[
            bind(option.Volatility, label="Volatility", format="%"),
            bind(option.Rate, label="Risk-Free Rate", format="%"),
            bind(option.TimeToExpiry, label="Time to Expiry (years)"),
            bind(option.IsCall, label="Is Call Option"),
        ],
    )

    app.add_section(
        "Option Price",
        outputs=[
            bind(option.Price, label="Option Price", format="$,.4f"),
            bind(option.IntrinsicValue, label="Intrinsic Value", format="$,.4f"),
            bind(option.TimeValue, label="Time Value", format="$,.4f"),
        ],
    )

    app.add_section(
        "Greeks",
        outputs=[
            bind(option.Delta, label="Delta", format=".4f"),
            bind(option.Gamma, label="Gamma", format=".6f"),
            bind(option.Vega, label="Vega", format=".4f"),
            bind(option.Theta, label="Theta", format=".4f"),
            bind(option.Rho, label="Rho", format=".4f"),
        ],
    )

    print("Starting Black-Scholes Option Pricer...")
    print("Open http://localhost:8080 in your browser")
    print("Press Ctrl+C to stop")
    print()

    # Run the server (opens browser automatically)
    app.run(port=8080, open_browser=True)


if __name__ == "__main__":
    main()
