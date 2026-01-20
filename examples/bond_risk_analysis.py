#!/usr/bin/env python3
"""
Bond Risk Analysis - Fixed Income Risk Deep Dive.

This example demonstrates:
1. Duration as weighted average time to cash flows
2. Modified duration vs Macaulay duration
3. Duration-convexity approximation vs actual repricing
4. DV01 and basis point value analysis
5. Yield scenario P&L ladder
6. Hedging with DV01 matching

Key insight: Duration is a linear approximation of price sensitivity.
Convexity adds the curvature adjustment, improving estimates for large moves.

Run: python examples/bond_risk_analysis.py
"""

import dag
from lattice import Bond, risk


def create_bond(face: float = 1000.0, coupon: float = 0.05,
                maturity: float = 10.0, ytm: float = 0.04,
                frequency: int = 2) -> Bond:
    """Create a bond with specified parameters."""
    bond = Bond()
    bond.FaceValue.set(face)
    bond.CouponRate.set(coupon)
    bond.Maturity.set(maturity)
    bond.YieldToMaturity.set(ytm)
    bond.Frequency.set(frequency)
    return bond


def duration_explained(bond: Bond):
    """Explain what duration actually measures."""
    print("\n" + "=" * 70)
    print("  UNDERSTANDING DURATION")
    print("=" * 70)

    print(f"\n  Bond Parameters:")
    print(f"    Face Value:    ${bond.FaceValue():,.0f}")
    print(f"    Coupon Rate:   {bond.CouponRate()*100:.1f}%")
    print(f"    Maturity:      {bond.Maturity():.0f} years")
    print(f"    YTM:           {bond.YieldToMaturity()*100:.1f}%")
    print(f"    Frequency:     {'Semi-annual' if bond.Frequency() == 2 else 'Annual'}")

    print(f"\n  Key Metrics:")
    print(f"    Bond Price:        ${bond.Price():,.2f}")
    print(f"    Macaulay Duration: {bond.Duration():.2f} years")
    print(f"    Modified Duration: {bond.ModifiedDuration():.2f}")
    print(f"    Convexity:         {bond.Convexity():.1f}")
    print(f"    DV01:              ${bond.DV01():.2f}")

    print(f"\n  What Does Duration Mean?")
    print("  " + "-" * 60)
    print(f"    Macaulay Duration ({bond.Duration():.2f} years):")
    print(f"      - Weighted average time to receive all cash flows")
    print(f"      - If you receive the face value earlier, duration is lower")
    print(f"      - A zero-coupon bond has duration = maturity")
    print(f"")
    print(f"    Modified Duration ({bond.ModifiedDuration():.2f}):")
    print(f"      - Macaulay Duration / (1 + y/freq)")
    print(f"      - Price sensitivity: if yield rises 1%, price falls ~{bond.ModifiedDuration():.1f}%")


def cash_flow_breakdown(bond: Bond):
    """Show the cash flow structure and how duration is calculated."""
    print("\n" + "=" * 70)
    print("  CASH FLOW ANALYSIS: How Duration is Calculated")
    print("=" * 70)

    y = bond.PeriodicYield()
    C = bond.CouponPayment()
    n = bond.NumPeriods()
    FV = bond.FaceValue()
    freq = bond.Frequency()

    print(f"\n  Cash Flow Schedule (first 5 and last 2 periods):")
    print("  " + "━" * 65)
    print(f"  {'Period':>8} {'Time(Y)':>10} {'Cash Flow':>12} {'Discount':>12} {'PV':>12}")
    print("  " + "━" * 65)

    total_pv = 0.0
    weighted_pv = 0.0

    for t in range(1, n + 1):
        time_years = t / freq
        cf = C if t < n else C + FV  # Last period includes face value
        discount = (1 + y) ** t
        pv = cf / discount
        total_pv += pv
        weighted_pv += time_years * pv

        # Only show first 5 and last 2
        if t <= 5 or t >= n - 1:
            print(f"  {t:>8} {time_years:>10.2f} ${cf:>11.2f} {discount:>12.4f} ${pv:>11.2f}")
        elif t == 6:
            print(f"  {'...':>8} {'...':>10} {'...':>12} {'...':>12} {'...':>12}")

    print("  " + "━" * 65)
    print(f"  {'Total':>8} {'':<10} {'':<12} {'':<12} ${total_pv:>11.2f}")

    duration = weighted_pv / total_pv
    print(f"\n  Duration Calculation:")
    print(f"    Sum of (Time × PV) / Total PV = {weighted_pv:.2f} / {total_pv:.2f} = {duration:.2f} years")


def duration_convexity_approximation(bond: Bond):
    """Compare duration/convexity approximation to actual repricing."""
    print("\n" + "=" * 70)
    print("  DURATION-CONVEXITY APPROXIMATION vs ACTUAL REPRICING")
    print("=" * 70)

    base_price = bond.Price()
    base_ytm = bond.YieldToMaturity()
    md = bond.ModifiedDuration()
    conv = bond.Convexity()

    print(f"\n  Base Case: Price = ${base_price:,.2f}, YTM = {base_ytm*100:.2f}%")
    print(f"  Modified Duration = {md:.2f}, Convexity = {conv:.1f}")

    print(f"\n  Formula: dP/P = -MD × dy + 0.5 × Convexity × dy²")
    print(f"           dP/P = -{md:.2f} × dy + 0.5 × {conv:.1f} × dy²")

    # Test various yield changes
    yield_changes = [-1.0, -0.5, -0.25, 0.25, 0.5, 1.0, 2.0]  # in percentage points

    print("\n  " + "━" * 75)
    print(f"  {'Yield Chg':>10} {'New YTM':>10} {'Actual':>12} {'Duration':>12} {'Dur+Conv':>12} {'Error':>10}")
    print("  " + "━" * 75)

    for dyield_pct in yield_changes:
        dy = dyield_pct / 100  # Convert to decimal

        # Actual repricing using scenario
        with dag.scenario():
            bond.YieldToMaturity.override(base_ytm + dy)
            actual_price = bond.Price()

        actual_change = actual_price - base_price
        actual_pct = actual_change / base_price * 100

        # Duration-only approximation
        duration_pct = -md * dy * 100
        duration_approx = base_price * (1 + duration_pct / 100)
        duration_change = duration_approx - base_price

        # Duration + convexity approximation
        durconv_pct = (-md * dy + 0.5 * conv * (dy ** 2)) * 100
        durconv_approx = base_price * (1 + durconv_pct / 100)
        durconv_change = durconv_approx - base_price

        # Error (convexity vs actual)
        error = durconv_change - actual_change

        new_ytm = (base_ytm + dy) * 100

        print(f"  {dyield_pct:>+9.2f}% {new_ytm:>9.2f}% ${actual_change:>+11.2f} "
              f"${duration_change:>+11.2f} ${durconv_change:>+11.2f} ${error:>+9.2f}")

    print("  " + "━" * 75)

    print(f"\n  Key Insights:")
    print(f"    - Duration alone underestimates gains and overestimates losses")
    print(f"    - Convexity correction is more important for larger yield changes")
    print(f"    - Bonds benefit from convexity: gains > losses for equal yield moves")


def dv01_analysis(bond: Bond):
    """Deep dive into DV01 (Dollar Value of a Basis Point)."""
    print("\n" + "=" * 70)
    print("  DV01 ANALYSIS: Dollar Value of a Basis Point")
    print("=" * 70)

    dv01 = bond.DV01()
    base_price = bond.Price()
    base_ytm = bond.YieldToMaturity()

    print(f"\n  Bond: ${bond.FaceValue():,.0f} {bond.CouponRate()*100:.1f}% {bond.Maturity():.0f}Y @ {base_ytm*100:.2f}% YTM")
    print(f"  Price: ${base_price:,.2f}")
    print(f"  DV01:  ${dv01:.2f} per basis point")

    print(f"\n  DV01 = Modified Duration × Price × 0.0001")
    print(f"       = {bond.ModifiedDuration():.4f} × ${base_price:,.2f} × 0.0001")
    print(f"       = ${dv01:.2f}")

    # Verify with actual bump
    print(f"\n  Verification (actual 1bp bump):")
    with dag.scenario():
        bond.YieldToMaturity.override(base_ytm + 0.0001)  # +1bp
        price_up = bond.Price()

    with dag.scenario():
        bond.YieldToMaturity.override(base_ytm - 0.0001)  # -1bp
        price_down = bond.Price()

    actual_dv01 = (price_down - price_up) / 2  # Central difference
    print(f"    Price at YTM + 1bp: ${price_up:,.4f}")
    print(f"    Price at YTM - 1bp: ${price_down:,.4f}")
    print(f"    Actual DV01:        ${actual_dv01:.2f}")
    print(f"    Analytic DV01:      ${dv01:.2f}")

    # DV01 for portfolio of multiple bonds
    print(f"\n  Portfolio DV01 Example:")
    print("  " + "-" * 55)

    # Create additional bonds - keep references alive in a list
    short_bond = create_bond(maturity=2.0, coupon=0.03, ytm=0.035)
    long_bond = create_bond(maturity=30.0, coupon=0.045, ytm=0.045)

    # Keep all bonds in a list to prevent garbage collection
    all_bonds = [bond, short_bond, long_bond]

    positions = [
        ("10Y Treasury", bond, 100),       # $100K position
        ("2Y Note", short_bond, 500),      # $500K position
        ("30Y Bond", long_bond, 50),       # $50K position
    ]

    print(f"  {'Bond':<15} {'Duration':>10} {'DV01/Bond':>12} {'Position':>10} {'Total DV01':>12}")
    print("  " + "-" * 55)

    total_dv01 = 0.0
    for name, b, qty in positions:
        pos_dv01 = b.DV01() * qty
        total_dv01 += pos_dv01
        print(f"  {name:<15} {b.ModifiedDuration():>10.2f} ${b.DV01():>11.2f} {qty:>10,} ${pos_dv01:>11.2f}")

    print("  " + "-" * 55)
    print(f"  {'Portfolio':<15} {'':<10} {'':<12} {'':<10} ${total_dv01:>11.2f}")

    print(f"\n  Interpretation:")
    print(f"    If yields rise 1bp across the curve, portfolio loses ${total_dv01:.2f}")
    print(f"    If yields fall 10bp, portfolio gains ${total_dv01 * 10:.2f}")


def yield_scenario_ladder(bond: Bond):
    """Build a P&L ladder across yield scenarios."""
    print("\n" + "=" * 70)
    print("  YIELD SCENARIO LADDER: P&L Profile")
    print("=" * 70)

    base_price = bond.Price()
    base_ytm = bond.YieldToMaturity()

    print(f"\n  Bond: {bond.CouponRate()*100:.1f}% {bond.Maturity():.0f}Y @ {base_ytm*100:.2f}% YTM")
    print(f"  Base Price: ${base_price:,.2f}")

    # Yield changes in basis points
    yield_changes_bp = [-100, -50, -25, -10, 0, 10, 25, 50, 100, 150, 200]

    print("\n  P&L Ladder:")
    print("  " + "━" * 70)
    print(f"  {'YTM':>8} {'Change':>10} {'Price':>12} {'P&L':>12} {'P&L %':>10} {'DV01':>10}")
    print("  " + "━" * 70)

    for bp in yield_changes_bp:
        new_ytm = base_ytm + bp / 10000

        with dag.scenario():
            bond.YieldToMaturity.override(new_ytm)
            price = bond.Price()
            dv01 = bond.DV01()

        pnl = price - base_price
        pnl_pct = pnl / base_price * 100
        marker = " <-- base" if bp == 0 else ""

        print(f"  {new_ytm*100:>7.2f}% {bp:>+9}bp ${price:>11.2f} ${pnl:>+11.2f} {pnl_pct:>+9.2f}% ${dv01:>9.2f}{marker}")

    print("  " + "━" * 70)

    print(f"\n  Observations:")
    print(f"    - P&L is asymmetric: gains from falling yields > losses from rising yields")
    print(f"    - This asymmetry is due to convexity (price-yield curve is convex)")
    print(f"    - DV01 increases as yields fall (longer effective duration)")


def hedging_example():
    """Demonstrate DV01 hedging."""
    print("\n" + "=" * 70)
    print("  HEDGING WITH DV01 MATCHING")
    print("=" * 70)

    # Portfolio: Long a 10Y bond
    long_bond = create_bond(maturity=10.0, coupon=0.05, ytm=0.04)

    # Hedge: Short a 5Y bond
    hedge_bond = create_bond(maturity=5.0, coupon=0.04, ytm=0.035)

    # Keep both bonds alive
    bonds = [long_bond, hedge_bond]

    long_qty = 100  # $100K face
    long_dv01 = long_bond.DV01() * long_qty

    print(f"\n  Portfolio Position:")
    print(f"    Long ${long_qty * long_bond.FaceValue() / 1000:.0f}K of 10Y {long_bond.CouponRate()*100:.1f}% bond")
    print(f"    Price: ${long_bond.Price():,.2f}, DV01/bond: ${long_bond.DV01():.2f}")
    print(f"    Total DV01 exposure: ${long_dv01:.2f}")

    print(f"\n  Hedge Instrument:")
    print(f"    5Y {hedge_bond.CouponRate()*100:.1f}% bond @ {hedge_bond.YieldToMaturity()*100:.2f}% YTM")
    print(f"    Price: ${hedge_bond.Price():,.2f}, DV01/bond: ${hedge_bond.DV01():.2f}")

    # Calculate hedge ratio
    hedge_qty = long_dv01 / hedge_bond.DV01()
    hedge_dv01 = hedge_bond.DV01() * hedge_qty

    print(f"\n  Hedge Calculation:")
    print(f"    Hedge Quantity = Long DV01 / Hedge DV01")
    print(f"                   = ${long_dv01:.2f} / ${hedge_bond.DV01():.2f}")
    print(f"                   = {hedge_qty:.1f} bonds (${hedge_qty * hedge_bond.FaceValue() / 1000:.0f}K face)")

    print(f"\n  Hedged Position:")
    print(f"    Long DV01:  ${long_dv01:>10.2f}")
    print(f"    Short DV01: ${-hedge_dv01:>+10.2f}")
    print(f"    Net DV01:   ${long_dv01 - hedge_dv01:>10.2f}")

    # Simulate a yield shift
    print(f"\n  Scenario: Parallel yield shift of +50bp")
    print("  " + "-" * 50)

    base_long_price = long_bond.Price()
    base_hedge_price = hedge_bond.Price()

    with dag.scenario():
        long_bond.YieldToMaturity.override(long_bond.YieldToMaturity() + 0.005)
        hedge_bond.YieldToMaturity.override(hedge_bond.YieldToMaturity() + 0.005)

        new_long_price = long_bond.Price()
        new_hedge_price = hedge_bond.Price()

    long_pnl = (new_long_price - base_long_price) * long_qty
    hedge_pnl = (new_hedge_price - base_hedge_price) * (-hedge_qty)  # Short position
    net_pnl = long_pnl + hedge_pnl

    print(f"    Long 10Y P&L:  ${long_pnl:>+10.2f} ({(new_long_price - base_long_price):>+.2f} per bond)")
    print(f"    Short 5Y P&L:  ${hedge_pnl:>+10.2f} ({-(new_hedge_price - base_hedge_price):>+.2f} per bond)")
    print(f"    Net P&L:       ${net_pnl:>+10.2f}")

    print(f"\n  Interpretation:")
    print(f"    - DV01 hedging neutralizes first-order interest rate risk")
    print(f"    - Small residual P&L due to:")
    print(f"      * Convexity mismatch (10Y more convex than 5Y)")
    print(f"      * Non-parallel curve shifts in reality")


def term_structure_comparison():
    """Compare risk across the yield curve."""
    print("\n" + "=" * 70)
    print("  TERM STRUCTURE: Duration Across Maturities")
    print("=" * 70)

    maturities = [1, 2, 3, 5, 7, 10, 15, 20, 30]

    print(f"\n  Fixed: 5% Coupon, 4% YTM across all maturities")
    print("\n  " + "━" * 70)
    print(f"  {'Maturity':>10} {'Price':>12} {'Duration':>12} {'Mod.Dur':>12} {'DV01':>10} {'Convexity':>12}")
    print("  " + "━" * 70)

    # Create all bonds and keep references
    bonds = []
    for mat in maturities:
        bond = create_bond(maturity=float(mat), coupon=0.05, ytm=0.04)
        bonds.append(bond)
        print(f"  {mat:>8}Y ${bond.Price():>11.2f} {bond.Duration():>12.2f} "
              f"{bond.ModifiedDuration():>12.2f} ${bond.DV01():>9.2f} {bond.Convexity():>12.1f}")

    print("  " + "━" * 70)

    print(f"\n  Key Observations:")
    print(f"    - Duration increases with maturity (more cash flows further out)")
    print(f"    - Duration < Maturity for coupon bonds (receive cash along the way)")
    print(f"    - DV01 increases with duration (more price sensitivity)")
    print(f"    - Convexity increases faster than duration (quadratic relationship)")


def main():
    print("=" * 70)
    print("  BOND RISK ANALYSIS")
    print("  Fixed Income Risk Deep Dive")
    print("=" * 70)

    # Create a single bond to use throughout most demos
    # (keeping the object alive prevents garbage collection issues)
    bond = create_bond()

    # 1. Duration concepts
    duration_explained(bond)

    # 2. Cash flow breakdown
    cash_flow_breakdown(bond)

    # 3. Duration-convexity approximation
    duration_convexity_approximation(bond)

    # 4. DV01 analysis
    dv01_analysis(bond)

    # 5. Yield scenario ladder
    yield_scenario_ladder(bond)

    # 6. Hedging example (creates its own bonds)
    hedging_example()

    # 7. Term structure comparison (creates multiple bonds)
    term_structure_comparison()

    print("\n" + "=" * 70)
    print("  END OF BOND RISK ANALYSIS")
    print("=" * 70)


if __name__ == "__main__":
    main()
