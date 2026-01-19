#!/usr/bin/env python3
"""
Quick Start - Show a VanillaOption with one line of code.

Usage:
    python examples/quick_start.py
"""

from lattice import VanillaOption
from lattice.ui import show


def main():
    # Create an option with default values
    option = VanillaOption()
    option.Spot.set(105.0)
    option.Strike.set(100.0)
    option.Volatility.set(0.25)

    print(f"Option Price: ${option.Price():.4f}")
    print(f"Delta: {option.Delta():.4f}")
    print()
    print("Launching browser UI...")

    # One line to show in browser!
    show(option, port=8080)


if __name__ == "__main__":
    main()
