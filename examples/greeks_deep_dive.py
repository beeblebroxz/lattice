#!/usr/bin/env python3
"""
Greeks Deep Dive - Analytic vs Numerical Greeks Comparison.

This example demonstrates:
1. Closed-form Black-Scholes Greeks (exact, computed instantly)
2. Numerical bump-and-reval Greeks (general, works for any model)
3. How bump size affects numerical accuracy
4. Greeks behavior across the moneyness spectrum

Key insight: Analytic Greeks are exact but model-specific. Numerical Greeks
are approximate but work universally for any pricing model.

Run: python examples/greeks_deep_dive.py
"""

from lattice import VanillaOption, risk


def create_option(spot: float = 100.0, strike: float = 100.0,
                  vol: float = 0.20, rate: float = 0.05,
                  time: float = 1.0, is_call: bool = True) -> VanillaOption:
    """Create a vanilla option with specified parameters."""
    option = VanillaOption()
    option.Spot.set(spot)
    option.Strike.set(strike)
    option.Volatility.set(vol)
    option.Rate.set(rate)
    option.TimeToExpiry.set(time)
    option.IsCall.set(is_call)
    return option


def compare_greeks(option: VanillaOption) -> None:
    """Compare analytic and numerical Greeks side by side."""
    print("\n" + "=" * 70)
    print("  GREEK COMPARISON: Analytic vs Numerical")
    print("=" * 70)

    # Option parameters
    print(f"\n  Option: {'Call' if option.IsCall() else 'Put'}")
    print(f"  Spot: ${option.Spot():.2f}  |  Strike: ${option.Strike():.2f}  |  "
          f"Vol: {option.Volatility()*100:.0f}%  |  Rate: {option.Rate()*100:.0f}%  |  "
          f"T: {option.TimeToExpiry():.2f}Y")
    print(f"  Price: ${option.Price():.4f}")

    # Get both analytic and numerical Greeks
    greeks = [
        ("Delta", option.Delta(), risk.delta(option)),
        ("Gamma", option.Gamma(), risk.gamma(option)),
        ("Vega",  option.Vega(),  risk.vega(option)),
        ("Theta", option.Theta(), risk.theta(option)),
        ("Rho",   option.Rho(),   risk.rho(option)),
    ]

    print("\n" + "━" * 70)
    print(f"  {'Greek':<10} {'Analytic':>12} {'Numerical':>12} {'Difference':>12} {'Rel. Error':>12}")
    print("━" * 70)

    for name, analytic, numerical in greeks:
        diff = numerical - analytic
        rel_err = (diff / analytic * 100) if abs(analytic) > 1e-10 else 0.0
        print(f"  {name:<10} {analytic:>12.6f} {numerical:>12.6f} {diff:>12.6f} {rel_err:>11.2f}%")

    print("━" * 70)
    print("\n  Interpretation:")
    print("  - Analytic Greeks come from closed-form Black-Scholes formulas")
    print("  - Numerical Greeks use bump-and-reval (finite difference)")
    print("  - Small differences are due to finite bump size (default: $0.01)")


def bump_size_analysis(option: VanillaOption) -> None:
    """Show how bump size affects numerical accuracy."""
    print("\n" + "=" * 70)
    print("  BUMP SIZE ANALYSIS: Effect on Numerical Accuracy")
    print("=" * 70)

    analytic_delta = option.Delta()
    analytic_gamma = option.Gamma()

    bump_sizes = [0.001, 0.01, 0.1, 1.0, 5.0]

    print(f"\n  Analytic Delta: {analytic_delta:.6f}")
    print(f"  Analytic Gamma: {analytic_gamma:.6f}")

    print("\n  Delta Convergence:")
    print("  " + "-" * 50)
    print(f"  {'Bump Size':>12} {'Num. Delta':>12} {'Error':>12} {'Note':<15}")
    print("  " + "-" * 50)

    for bump in bump_sizes:
        num_delta = risk.delta(option, bump=bump)
        error = abs(num_delta - analytic_delta)
        note = "<-- default" if bump == 0.01 else ""
        print(f"  ${bump:>11.3f} {num_delta:>12.6f} {error:>12.6f} {note:<15}")

    print("\n  Gamma Convergence (uses central difference):")
    print("  " + "-" * 50)
    print(f"  {'Bump Size':>12} {'Num. Gamma':>12} {'Error':>12}")
    print("  " + "-" * 50)

    for bump in bump_sizes:
        num_gamma = risk.gamma(option, bump=bump)
        error = abs(num_gamma - analytic_gamma)
        print(f"  ${bump:>11.3f} {num_gamma:>12.6f} {error:>12.6f}")

    print("\n  Key Insight:")
    print("  - Smaller bumps are more accurate but can have numerical instability")
    print("  - Larger bumps are stable but less accurate (truncation error)")
    print("  - Default bump of $0.01 balances accuracy and stability")
    print("  - Gamma uses central difference: (f(x+h) - 2f(x) + f(x-h)) / h^2")


def moneyness_analysis() -> None:
    """Show Greeks across the moneyness spectrum."""
    print("\n" + "=" * 70)
    print("  MONEYNESS ANALYSIS: Greeks from Deep ITM to Deep OTM")
    print("=" * 70)

    base_spot = 100.0
    strike = 100.0

    # Different spot levels (from ITM to OTM for a call)
    spots = [80, 90, 95, 100, 105, 110, 120]

    print(f"\n  Strike: ${strike:.0f}  |  Vol: 20%  |  Rate: 5%  |  T: 1Y")
    print("\n  Call Option Greeks Across Moneyness:")
    print("  " + "━" * 65)
    print(f"  {'Spot':>8} {'Moneyness':>12} {'Price':>10} {'Delta':>8} {'Gamma':>8} {'Vega':>8}")
    print("  " + "━" * 65)

    for spot in spots:
        option = create_option(spot=spot, strike=strike)
        moneyness = "ITM" if spot > strike else ("ATM" if spot == strike else "OTM")
        pct = (spot - strike) / strike * 100
        moneyness_str = f"{moneyness} ({pct:+.0f}%)"

        print(f"  ${spot:>7.0f} {moneyness_str:>12} ${option.Price():>9.2f} "
              f"{option.Delta():>8.4f} {option.Gamma():>8.4f} {option.Vega():>8.2f}")

    print("  " + "━" * 65)
    print("\n  Key Observations:")
    print("  - Delta approaches 1.0 for deep ITM calls, 0.0 for deep OTM")
    print("  - Gamma peaks at ATM (maximum uncertainty)")
    print("  - Vega also peaks near ATM (most sensitive to vol changes)")

    # Now show puts
    print("\n  Put Option Greeks Across Moneyness:")
    print("  " + "━" * 65)
    print(f"  {'Spot':>8} {'Moneyness':>12} {'Price':>10} {'Delta':>8} {'Gamma':>8} {'Vega':>8}")
    print("  " + "━" * 65)

    for spot in spots:
        option = create_option(spot=spot, strike=strike, is_call=False)
        moneyness = "OTM" if spot > strike else ("ATM" if spot == strike else "ITM")
        pct = (spot - strike) / strike * 100
        moneyness_str = f"{moneyness} ({pct:+.0f}%)"

        print(f"  ${spot:>7.0f} {moneyness_str:>12} ${option.Price():>9.2f} "
              f"{option.Delta():>8.4f} {option.Gamma():>8.4f} {option.Vega():>8.2f}")

    print("  " + "━" * 65)
    print("\n  Note: Put delta is negative (price decreases as spot rises)")


def theta_decay_analysis() -> None:
    """Show theta decay as expiration approaches."""
    print("\n" + "=" * 70)
    print("  THETA DECAY: Time Value Erosion")
    print("=" * 70)

    # ATM option with different times to expiry
    times = [1.0, 0.5, 0.25, 1/12, 1/52, 1/365]  # 1Y, 6M, 3M, 1M, 1W, 1D
    labels = ["1 Year", "6 Months", "3 Months", "1 Month", "1 Week", "1 Day"]

    print(f"\n  ATM Call (Spot=Strike=$100, Vol=20%, Rate=5%)")
    print("\n  " + "━" * 60)
    print(f"  {'Time to Expiry':>15} {'Price':>10} {'Time Value':>12} {'Theta/Day':>12}")
    print("  " + "━" * 60)

    for time, label in zip(times, labels):
        option = create_option(time=time)
        intrinsic = max(0, option.Spot() - option.Strike())
        time_value = option.Price() - intrinsic

        print(f"  {label:>15} ${option.Price():>9.4f} ${time_value:>11.4f} ${option.Theta():>11.4f}")

    print("  " + "━" * 60)
    print("\n  Key Insight:")
    print("  - Theta accelerates as expiration approaches")
    print("  - ATM options have the most time value to lose")
    print("  - Time decay is fastest in the final weeks")


def main():
    print("=" * 70)
    print("  GREEKS DEEP DIVE")
    print("  Analytic vs Numerical Greeks Comparison")
    print("=" * 70)

    # Create a standard ATM call option
    option = create_option()

    # 1. Compare analytic vs numerical Greeks
    compare_greeks(option)

    # 2. Bump size sensitivity analysis
    bump_size_analysis(option)

    # 3. Greeks across moneyness
    moneyness_analysis()

    # 4. Theta decay analysis
    theta_decay_analysis()

    print("\n" + "=" * 70)
    print("  END OF GREEKS DEEP DIVE")
    print("=" * 70)


if __name__ == "__main__":
    main()
