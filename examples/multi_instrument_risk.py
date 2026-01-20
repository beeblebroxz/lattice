#!/usr/bin/env python3
"""
Multi-Instrument Risk - Risk Analysis Across Asset Classes.

This example demonstrates:
1. How different instruments have different risk sensitivities
2. Options: Delta, Gamma, Vega, Theta, Rho
3. Bonds: DV01, Duration, Convexity
4. Forwards: Delta (linear), Theta (carry cost)
5. FX: Delta (currency exposure)
6. Using RiskEngine for batch calculations
7. Stress testing across asset classes

Key insight: The same risk framework (bump-and-reval) works universally
for all instrument types, but each instrument has its own relevant Greeks.

Run: python examples/multi_instrument_risk.py
"""

from lattice import VanillaOption, Bond, Forward, risk
from lattice.instruments.fx import FXForward
from lattice.risk import RiskEngine


def create_sample_portfolio():
    """Create a diverse portfolio of financial instruments."""
    # 1. Equity Option - AAPL Call
    option = VanillaOption()
    option.Spot.set(150.0)
    option.Strike.set(155.0)
    option.Volatility.set(0.25)
    option.Rate.set(0.05)
    option.TimeToExpiry.set(0.25)  # 3 months
    option.IsCall.set(True)

    # 2. Fixed Income - 10Y Treasury Bond
    bond = Bond()
    bond.FaceValue.set(1000.0)
    bond.CouponRate.set(0.05)       # 5% coupon
    bond.Maturity.set(10.0)         # 10 years
    bond.YieldToMaturity.set(0.04)  # 4% YTM (trading at premium)
    bond.Frequency.set(2)           # Semi-annual

    # 3. Commodity Forward - Gold 6M
    forward = Forward()
    forward.Spot.set(1900.0)        # Gold spot
    forward.Rate.set(0.05)          # Risk-free rate
    forward.DividendYield.set(0.0)  # No yield (commodity)
    forward.StorageCost.set(0.005)  # 0.5% storage cost
    forward.TimeToExpiry.set(0.5)   # 6 months
    forward.ContractPrice.set(1920.0)  # Agreed forward price
    forward.IsLong.set(True)
    forward.ContractSize.set(100)   # 100 oz contract

    # 4. FX Forward - EUR/USD 1Y
    fx_fwd = FXForward()
    fx_fwd.BaseCurrency.set("EUR")
    fx_fwd.QuoteCurrency.set("USD")
    fx_fwd.Spot.set(1.10)
    fx_fwd.BaseRate.set(0.04)       # EUR rate
    fx_fwd.QuoteRate.set(0.05)      # USD rate
    fx_fwd.TimeToExpiry.set(1.0)    # 1 year
    fx_fwd.ContractRate.set(1.095)  # Agreed rate
    fx_fwd.BaseNotional.set(1000000.0)  # 1M EUR
    fx_fwd.IsLongBase.set(True)     # Long EUR / Short USD

    return {
        "AAPL_C_155": option,
        "UST_10Y": bond,
        "GOLD_FWD_6M": forward,
        "EURUSD_FWD_1Y": fx_fwd,
    }


def show_portfolio_summary(portfolio):
    """Display portfolio instruments and their market values."""
    print("\n" + "=" * 70)
    print("  PORTFOLIO SUMMARY")
    print("=" * 70)

    print("\n  Instruments:")
    print("  " + "-" * 65)
    print(f"  {'Name':<18} {'Type':<15} {'Summary':<20} {'Value':>12}")
    print("  " + "-" * 65)

    for name, inst in portfolio.items():
        # Use the polymorphic Summary() and MarketValue() methods
        inst_type = type(inst).__name__
        summary = inst.Summary()
        value = inst.MarketValue()
        print(f"  {name:<18} {inst_type:<15} {summary:<20} ${value:>11,.2f}")

    print("  " + "-" * 65)


def option_risk_analysis(option, name):
    """Deep dive into option Greeks."""
    print(f"\n  {name} - Option Greeks:")
    print("  " + "━" * 60)

    greeks = [
        ("Delta", option.Delta(), "Price change per $1 spot move"),
        ("Gamma", option.Gamma(), "Delta change per $1 spot move"),
        ("Vega", option.Vega(), "Price change per 1% vol move"),
        ("Theta", option.Theta(), "Daily time decay"),
        ("Rho", option.Rho(), "Price change per 1% rate move"),
    ]

    for greek, value, description in greeks:
        print(f"    {greek:<8} {value:>10.4f}  ({description})")

    # Risk interpretation
    print("\n  Interpretation:")
    print(f"    - If spot moves +$1: option gains ${option.Delta():.4f}")
    print(f"    - If vol rises 1%:   option gains ${option.Vega():.4f}")
    print(f"    - Each day:          option loses ${abs(option.Theta()):.4f}")


def bond_risk_analysis(bond, name):
    """Deep dive into bond risk metrics."""
    print(f"\n  {name} - Bond Risk Metrics:")
    print("  " + "━" * 60)

    metrics = [
        ("Price", f"${bond.Price():,.2f}", "Current market price"),
        ("Duration", f"{bond.Duration():.2f} yrs", "Weighted avg time to cash flows"),
        ("Mod. Duration", f"{bond.ModifiedDuration():.2f}", "Price sensitivity to yield"),
        ("Convexity", f"{bond.Convexity():.1f}", "Curvature adjustment"),
        ("DV01", f"${bond.DV01():.2f}", "$ change per 1bp yield move"),
    ]

    for metric, value, description in metrics:
        print(f"    {metric:<14} {value:>12}  ({description})")

    # Risk interpretation
    print("\n  Interpretation:")
    print(f"    - If yield rises 1%:   price falls ~{bond.ModifiedDuration():.1f}%")
    print(f"    - If yield rises 1bp:  price falls ${bond.DV01():.2f}")


def forward_risk_analysis(forward, name):
    """Analyze forward contract risk."""
    print(f"\n  {name} - Forward Risk Metrics:")
    print("  " + "━" * 60)

    metrics = [
        ("Forward Price", f"${forward.ForwardPrice():,.2f}", "Fair delivery price"),
        ("Contract Price", f"${forward.ContractPrice():,.2f}", "Agreed delivery price"),
        ("Current Value", f"${forward.Value():,.2f}", "MTM value of contract"),
        ("Delta", f"{forward.Delta():.4f}", "Spot sensitivity (per unit)"),
        ("Gamma", f"{forward.Gamma():.4f}", "Always 0 (linear payoff)"),
    ]

    for metric, value, description in metrics:
        print(f"    {metric:<14} {value:>12}  ({description})")

    print("\n  Interpretation:")
    print(f"    - Forward payoff is linear (Delta ~1.0, Gamma = 0)")
    print(f"    - Contract is {'in profit' if forward.Value() > 0 else 'underwater'} by ${abs(forward.Value()):,.2f}")


def fx_risk_analysis(fx_fwd, name):
    """Analyze FX forward risk."""
    print(f"\n  {name} - FX Forward Risk Metrics:")
    print("  " + "━" * 60)

    metrics = [
        ("Spot", f"{fx_fwd.Spot():.4f}", f"{fx_fwd.PairName()} spot rate"),
        ("Forward", f"{fx_fwd.ForwardRate():.4f}", "1Y forward rate"),
        ("Contract", f"{fx_fwd.ContractRate():.4f}", "Agreed rate"),
        ("Fwd Points", f"{fx_fwd.ForwardPointsPips():,.1f} pips", "Forward - Spot"),
        ("Value", f"${fx_fwd.Value():,.2f}", "MTM in quote currency"),
        ("Delta", f"{fx_fwd.Delta():,.0f} EUR", "EUR exposure"),
    ]

    for metric, value, description in metrics:
        print(f"    {metric:<14} {value:>15}  ({description})")

    print("\n  Interpretation:")
    direction = "premium" if fx_fwd.ForwardRate() > fx_fwd.Spot() else "discount"
    print(f"    - Forward at {direction} (USD rate > EUR rate)")
    print(f"    - Long {fx_fwd.BaseNotional()/1e6:.1f}M EUR / Short {fx_fwd.QuoteNotional()/1e6:.2f}M USD")


def risk_engine_batch_demo(portfolio):
    """Use RiskEngine for batch calculations."""
    print("\n" + "=" * 70)
    print("  RISKENGINE: Batch Greeks Calculation")
    print("=" * 70)

    engine = RiskEngine()
    for name, inst in portfolio.items():
        engine.add(inst, name)

    print(f"\n  Registered {len(portfolio)} instruments")

    greeks = engine.compute_greeks()

    print("\n  Greeks Summary:")
    print("  " + "━" * 65)
    print(f"  {'Instrument':<18} {'Delta':>10} {'Gamma':>10} {'Vega':>10} {'Theta':>10} {'DV01':>10}")
    print("  " + "━" * 65)

    for name, metrics in greeks.items():
        delta = metrics.get("delta", "")
        gamma = metrics.get("gamma", "")
        vega = metrics.get("vega", "")
        theta = metrics.get("theta", "")
        dv01 = metrics.get("dv01", "")

        # Format values
        delta_str = f"{delta:.4f}" if isinstance(delta, float) else "-"
        gamma_str = f"{gamma:.4f}" if isinstance(gamma, float) else "-"
        vega_str = f"{vega:.4f}" if isinstance(vega, float) else "-"
        theta_str = f"{theta:.4f}" if isinstance(theta, float) else "-"
        dv01_str = f"{dv01:.2f}" if isinstance(dv01, float) else "-"

        print(f"  {name:<18} {delta_str:>10} {gamma_str:>10} {vega_str:>10} {theta_str:>10} {dv01_str:>10}")

    print("  " + "━" * 65)
    print("\n  Note: '-' means that Greek is not applicable for that instrument type")


def stress_testing_demo(portfolio):
    """Demonstrate stress testing across instruments."""
    print("\n" + "=" * 70)
    print("  STRESS TESTING: Multi-Asset Scenarios")
    print("=" * 70)

    engine = RiskEngine()
    for name, inst in portfolio.items():
        engine.add(inst, name)

    # Define scenarios
    scenarios = {
        "Market Crash": {"Spot": -0.20},           # -20% spot
        "Vol Spike": {"Volatility": 0.50},         # +50% relative vol increase
        "Rate Hike +100bp": {"Rate": 0.20},        # +20% relative (5% -> 6%)
        "Combined Stress": {"Spot": -0.15, "Volatility": 0.30},
    }

    print("\n  Stress Scenario Results:")
    print("  " + "━" * 70)
    print(f"  {'Scenario':<20} {'Instrument':<18} {'Base':>10} {'Stressed':>10} {'Impact':>10}")
    print("  " + "━" * 70)

    for scenario_name, shocks in scenarios.items():
        results = engine.stress_test(**shocks)
        first = True
        for inst_name, result in results.items():
            if "error" in result:
                continue
            scenario_col = scenario_name if first else ""
            first = False
            base = result["base_price"]
            stressed = result["stressed_price"]
            impact = result["price_impact"]
            print(f"  {scenario_col:<20} {inst_name:<18} ${base:>9,.2f} ${stressed:>9,.2f} ${impact:>+9,.2f}")
        if not first:  # Print separator after each scenario
            print()

    print("  " + "━" * 70)


def main():
    print("=" * 70)
    print("  MULTI-INSTRUMENT RISK ANALYSIS")
    print("  Risk Calculations Across Asset Classes")
    print("=" * 70)

    # Create portfolio
    portfolio = create_sample_portfolio()

    # 1. Portfolio summary
    show_portfolio_summary(portfolio)

    # 2. Instrument-specific risk analysis
    print("\n" + "=" * 70)
    print("  INSTRUMENT-SPECIFIC RISK METRICS")
    print("=" * 70)

    option_risk_analysis(portfolio["AAPL_C_155"], "AAPL_C_155")
    bond_risk_analysis(portfolio["UST_10Y"], "UST_10Y")
    forward_risk_analysis(portfolio["GOLD_FWD_6M"], "GOLD_FWD_6M")
    fx_risk_analysis(portfolio["EURUSD_FWD_1Y"], "EURUSD_FWD_1Y")

    # 3. Batch calculation with RiskEngine
    risk_engine_batch_demo(portfolio)

    # 4. Stress testing
    stress_testing_demo(portfolio)

    print("\n" + "=" * 70)
    print("  END OF MULTI-INSTRUMENT RISK ANALYSIS")
    print("=" * 70)


if __name__ == "__main__":
    main()
