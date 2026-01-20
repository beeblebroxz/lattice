#!/usr/bin/env python3
"""
Sensitivity Analysis - Understanding Bump-and-Reval Methodology.

This example demonstrates:
1. How dag.scenario() enables isolated state changes
2. Manual step-by-step bump-and-reval calculation
3. Forward difference vs central difference methods
4. The general risk.sensitivity() function for custom Greeks
5. Building sensitivity ladders (P&L profiles)

Key insight: The bump-and-reval technique is the foundation of numerical
risk management. Understanding it helps you build custom risk measures
for any instrument or model.

Run: python examples/sensitivity_analysis.py
"""

import dag
from lattice import VanillaOption, risk


def create_option(spot: float = 100.0) -> VanillaOption:
    """Create a standard ATM call option."""
    option = VanillaOption()
    option.Spot.set(spot)
    option.Strike.set(100.0)
    option.Volatility.set(0.20)
    option.Rate.set(0.05)
    option.TimeToExpiry.set(1.0)
    option.IsCall.set(True)
    return option


def manual_bump_and_reval_demo(option: VanillaOption):
    """Walk through bump-and-reval step by step."""
    print("\n" + "=" * 70)
    print("  MANUAL BUMP-AND-REVAL: Step by Step")
    print("=" * 70)

    print(f"\n  Option Parameters:")
    print(f"    Spot: ${option.Spot():.2f}  |  Strike: ${option.Strike():.2f}")
    print(f"    Vol: {option.Volatility()*100:.0f}%  |  Rate: {option.Rate()*100:.0f}%  |  T: {option.TimeToExpiry():.2f}Y")

    # Step 1: Get base values
    base_spot = option.Spot()
    base_price = option.Price()
    bump = 0.01  # $0.01 bump

    print(f"\n  Step 1: Record base values")
    print(f"    Base Spot:  ${base_spot:.2f}")
    print(f"    Base Price: ${base_price:.4f}")
    print(f"    Bump Size:  ${bump:.2f}")

    # Step 2: Enter scenario and apply bump
    print(f"\n  Step 2: Enter dag.scenario() and bump spot")
    print(f"    with dag.scenario():")
    print(f"        option.Spot.override({base_spot + bump})")

    with dag.scenario():
        option.Spot.override(base_spot + bump)
        bumped_price = option.Price()
        print(f"        Bumped Spot:  ${option.Spot():.2f}")
        print(f"        Bumped Price: ${bumped_price:.4f}")

    # Step 3: Scenario exits - values restored
    print(f"\n  Step 3: Exit scenario - values automatically restored")
    print(f"    Spot after scenario: ${option.Spot():.2f} (restored!)")
    print(f"    Price after scenario: ${option.Price():.4f}")

    # Step 4: Calculate delta
    delta = (bumped_price - base_price) / bump

    print(f"\n  Step 4: Calculate Delta")
    print(f"    Delta = (bumped_price - base_price) / bump")
    print(f"    Delta = ({bumped_price:.4f} - {base_price:.4f}) / {bump}")
    print(f"    Delta = {delta:.6f}")

    # Compare with analytic
    analytic_delta = option.Delta()
    print(f"\n  Verification:")
    print(f"    Numerical Delta: {delta:.6f}")
    print(f"    Analytic Delta:  {analytic_delta:.6f}")
    print(f"    Difference:      {abs(delta - analytic_delta):.6f}")


def forward_vs_central_difference(option: VanillaOption):
    """Compare forward difference and central difference methods."""
    print("\n" + "=" * 70)
    print("  FORWARD vs CENTRAL DIFFERENCE")
    print("=" * 70)

    bump = 0.01

    # Analytic values for comparison
    analytic_delta = option.Delta()
    analytic_gamma = option.Gamma()

    print(f"\n  Computing Delta (first derivative):")
    print(f"  " + "-" * 50)

    # Forward difference: (f(x+h) - f(x)) / h
    base_price = option.Price()
    with dag.scenario():
        option.Spot.override(option.Spot() + bump)
        price_up = option.Price()
    forward_delta = (price_up - base_price) / bump

    # Central difference: (f(x+h) - f(x-h)) / (2h)
    with dag.scenario():
        option.Spot.override(option.Spot() + bump)
        price_up = option.Price()
    with dag.scenario():
        option.Spot.override(option.Spot() - bump)
        price_down = option.Price()
    central_delta = (price_up - price_down) / (2 * bump)

    print(f"    Forward diff:  (f(x+h) - f(x)) / h       = {forward_delta:.6f}")
    print(f"    Central diff:  (f(x+h) - f(x-h)) / 2h    = {central_delta:.6f}")
    print(f"    Analytic:                                = {analytic_delta:.6f}")
    print(f"    ")
    print(f"    Forward error: {abs(forward_delta - analytic_delta):.6f}")
    print(f"    Central error: {abs(central_delta - analytic_delta):.6f}")
    print(f"    Central is ~{abs(forward_delta - analytic_delta) / max(abs(central_delta - analytic_delta), 1e-10):.0f}x more accurate")

    print(f"\n  Computing Gamma (second derivative):")
    print(f"  " + "-" * 50)

    # Second derivative: (f(x+h) - 2f(x) + f(x-h)) / h^2
    with dag.scenario():
        option.Spot.override(option.Spot() + bump)
        price_up = option.Price()
    with dag.scenario():
        option.Spot.override(option.Spot() - bump)
        price_down = option.Price()

    numerical_gamma = (price_up - 2*base_price + price_down) / (bump**2)

    print(f"    Formula: (f(x+h) - 2f(x) + f(x-h)) / h^2")
    print(f"    Numerical: {numerical_gamma:.6f}")
    print(f"    Analytic:  {analytic_gamma:.6f}")
    print(f"    Error:     {abs(numerical_gamma - analytic_gamma):.6f}")

    print(f"\n  Key Insight:")
    print(f"    - Forward difference has O(h) error (first-order)")
    print(f"    - Central difference has O(h^2) error (second-order)")
    print(f"    - For gamma, central difference is essential for accuracy")


def custom_sensitivity_demo(option: VanillaOption):
    """Demonstrate risk.sensitivity() for arbitrary Greeks."""
    print("\n" + "=" * 70)
    print("  CUSTOM SENSITIVITY CALCULATIONS")
    print("=" * 70)

    print(f"\n  The risk.sensitivity() function computes dOutput/dInput:")
    print(f"    sensitivity(instrument, input_name, output_name, bump, bump_type)")

    print(f"\n  Standard Greeks using sensitivity():")
    print(f"  " + "-" * 55)

    # Delta: dPrice/dSpot
    delta = risk.sensitivity(option, "Spot", "Price", bump=0.01)
    print(f"    dPrice/dSpot (Delta):    {delta:.6f}")

    # Vega: dPrice/dVol (scaled)
    dvol = risk.sensitivity(option, "Volatility", "Price", bump=0.01)
    print(f"    dPrice/dVol (per 1pt):   {dvol:.6f}")

    # Theta: dPrice/dTime (inverted and scaled)
    dtime = risk.sensitivity(option, "TimeToExpiry", "Price", bump=1/365)
    print(f"    dPrice/dTime (per day):  {-dtime * (1/365):.6f}")

    # Rho: dPrice/dRate
    drate = risk.sensitivity(option, "Rate", "Price", bump=0.01)
    print(f"    dPrice/dRate (per 1pt):  {drate:.6f}")

    print(f"\n  Custom/Creative Sensitivities:")
    print(f"  " + "-" * 55)

    # dDelta/dSpot (should equal Gamma)
    ddelta_dspot = risk.sensitivity(option, "Spot", "Delta", bump=0.01)
    print(f"    dDelta/dSpot (≈ Gamma):  {ddelta_dspot:.6f}")
    print(f"    Actual Gamma:            {option.Gamma():.6f}")

    # dDelta/dVol (Vanna-like)
    ddelta_dvol = risk.sensitivity(option, "Volatility", "Delta", bump=0.01)
    print(f"    dDelta/dVol (Vanna):     {ddelta_dvol:.6f}")

    # dVega/dSpot (Vanna from other direction)
    dvega_dspot = risk.sensitivity(option, "Spot", "Vega", bump=0.01)
    print(f"    dVega/dSpot (Vanna):     {dvega_dspot:.6f}")

    # dGamma/dSpot (Speed)
    dgamma_dspot = risk.sensitivity(option, "Spot", "Gamma", bump=0.01)
    print(f"    dGamma/dSpot (Speed):    {dgamma_dspot:.6f}")

    print(f"\n  Note: Vanna should be symmetric: dDelta/dVol ≈ dVega/dSpot")
    print(f"  (Small differences due to numerical approximation)")


def sensitivity_ladder(option: VanillaOption):
    """Build a P&L ladder across spot levels."""
    print("\n" + "=" * 70)
    print("  SENSITIVITY LADDER: P&L Profile")
    print("=" * 70)

    base_price = option.Price()
    base_spot = option.Spot()

    print(f"\n  ATM Call: Strike=${option.Strike():.0f}, Current Spot=${base_spot:.0f}")
    print(f"  Current Price: ${base_price:.4f}")

    # Spot levels from -15% to +15%
    spot_moves = [-15, -10, -5, -2, 0, 2, 5, 10, 15]

    print(f"\n  P&L Ladder:")
    print("  " + "━" * 65)
    print(f"  {'Spot':>8} {'Move':>8} {'Price':>10} {'P&L':>10} {'Delta':>8} {'Gamma':>8}")
    print("  " + "━" * 65)

    for move_pct in spot_moves:
        spot = base_spot * (1 + move_pct/100)

        with dag.scenario():
            option.Spot.override(spot)
            price = option.Price()
            delta = option.Delta()
            gamma = option.Gamma()

        pnl = price - base_price
        marker = " <-- base" if move_pct == 0 else ""

        print(f"  ${spot:>7.2f} {move_pct:>+7}% ${price:>9.4f} ${pnl:>+9.4f} {delta:>8.4f} {gamma:>8.4f}{marker}")

    print("  " + "━" * 65)

    print(f"\n  Observations:")
    print(f"    - P&L is asymmetric (convex) due to gamma")
    print(f"    - Delta increases as spot rises (call becomes more ITM)")
    print(f"    - Gamma peaks near ATM")


def two_dimensional_sensitivity(option: VanillaOption):
    """Show a 2D sensitivity surface (spot vs vol)."""
    print("\n" + "=" * 70)
    print("  2D SENSITIVITY: Spot vs Volatility")
    print("=" * 70)

    base_spot = option.Spot()
    base_vol = option.Volatility()
    base_price = option.Price()

    # Grid of spot and vol changes
    spot_moves = [-10, -5, 0, 5, 10]  # %
    vol_moves = [-5, 0, 5, 10]  # absolute points (e.g., 20% -> 25%)

    print(f"\n  Base: Spot=${base_spot:.0f}, Vol={base_vol*100:.0f}%, Price=${base_price:.2f}")
    print(f"\n  Option Price by Spot Move (columns) and Vol Change (rows):")
    print("  " + "━" * 55)

    # Header
    header = "  Vol\\Spot "
    for sm in spot_moves:
        header += f" {sm:+5}%"
    print(header)
    print("  " + "━" * 55)

    for vm in vol_moves:
        new_vol = base_vol + vm/100
        row = f"  {new_vol*100:>5.0f}%   "

        for sm in spot_moves:
            new_spot = base_spot * (1 + sm/100)

            with dag.scenario():
                option.Spot.override(new_spot)
                option.Volatility.override(new_vol)
                price = option.Price()

            row += f" ${price:>5.2f}"

        print(row)

    print("  " + "━" * 55)

    print(f"\n  Reading the table:")
    print(f"    - Row: volatility level (15% to 30%)")
    print(f"    - Column: spot move from ${base_spot:.0f}")
    print(f"    - Cell: option price under that scenario")
    print(f"    - Higher vol + higher spot = highest prices (top-right)")


def main():
    print("=" * 70)
    print("  SENSITIVITY ANALYSIS")
    print("  Understanding Bump-and-Reval Methodology")
    print("=" * 70)

    # Create a single option to use throughout all demos
    # (keeping the object alive prevents garbage collection issues)
    option = create_option()

    # 1. Manual bump-and-reval walkthrough
    manual_bump_and_reval_demo(option)

    # 2. Forward vs central difference
    forward_vs_central_difference(option)

    # 3. Custom sensitivity calculations
    custom_sensitivity_demo(option)

    # 4. Sensitivity ladder
    sensitivity_ladder(option)

    # 5. 2D sensitivity surface
    two_dimensional_sensitivity(option)

    print("\n" + "=" * 70)
    print("  END OF SENSITIVITY ANALYSIS")
    print("=" * 70)


if __name__ == "__main__":
    main()
