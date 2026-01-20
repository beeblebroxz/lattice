#!/usr/bin/env python3
"""
Interest Rate Swap Risk Analysis.

This example demonstrates:
1. Creating and valuing interest rate swaps
2. Par swap rate calculation
3. DV01 and PV01 risk metrics
4. Rate scenario P&L ladder
5. Hedging swaps with bonds using DV01 matching

Run: python examples/swap_risk_analysis.py
"""

import dag
from lattice import InterestRateSwap, Bond


def create_swap(
    notional: float = 10_000_000.0,
    fixed_rate: float = 0.03,
    maturity: float = 5.0,
    is_payer: bool = True,
    discount_rate: float = 0.035,
) -> InterestRateSwap:
    """Create a swap with specified parameters."""
    swap = InterestRateSwap()
    swap.Notional.set(notional)
    swap.FixedRate.set(fixed_rate)
    swap.Maturity.set(maturity)
    swap.IsPayer.set(is_payer)
    swap.DiscountRate.set(discount_rate)
    swap.FloatingRate.set(0.03)
    return swap


def swap_basics(swap: InterestRateSwap):
    """Demonstrate basic swap valuation."""
    print("\n" + "=" * 70)
    print("  INTEREST RATE SWAP BASICS")
    print("=" * 70)

    print(f"\n  Swap Parameters:")
    print(f"    Notional:       ${swap.Notional():,.0f}")
    print(f"    Fixed Rate:     {swap.FixedRate()*100:.2f}%")
    print(f"    Maturity:       {swap.Maturity():.0f} years")
    freq_name = {1: "Annual", 2: "Semi-annual", 4: "Quarterly"}.get(swap.Frequency(), f"{swap.Frequency()}x/year")
    print(f"    Frequency:      {freq_name}")
    direction = "Pay Fixed / Receive Floating" if swap.IsPayer() else "Receive Fixed / Pay Floating"
    print(f"    Direction:      {direction}")

    print(f"\n  Market Data:")
    print(f"    Discount Rate:  {swap.DiscountRate()*100:.2f}%")
    print(f"    Floating Rate:  {swap.FloatingRate()*100:.2f}%")

    print(f"\n  Valuation:")
    print(f"    Fixed Leg PV:   ${swap.FixedLegPV():>15,.2f}")
    print(f"    Float Leg PV:   ${swap.FloatingLegPV():>15,.2f}")
    print(f"    NPV:            ${swap.NPV():>15,.2f}")
    print(f"    Par Swap Rate:  {swap.ParSwapRate()*100:>15.4f}%")

    print(f"\n  Risk Metrics:")
    print(f"    DV01:           ${swap.DV01():>15,.2f}  (per 1bp rate move)")
    print(f"    PV01:           ${swap.PV01():>15,.2f}  (per 1bp fixed rate move)")
    print(f"    Annuity:        {swap.Annuity():>16.4f}")


def rate_scenario_ladder(swap: InterestRateSwap):
    """Build a P&L ladder across rate scenarios."""
    print("\n" + "=" * 70)
    print("  RATE SCENARIO LADDER")
    print("=" * 70)

    base_npv = swap.NPV()
    base_rate = swap.DiscountRate()

    rate_changes_bp = [-100, -50, -25, -10, 0, 10, 25, 50, 100]

    print(f"\n  Base: NPV = ${base_npv:,.2f}, Discount Rate = {base_rate*100:.2f}%")
    print("\n  " + "━" * 65)
    print(f"  {'Rate':>8} {'Change':>10} {'NPV':>18} {'P&L':>18}")
    print("  " + "━" * 65)

    for bp in rate_changes_bp:
        new_rate = base_rate + bp / 10000

        with dag.scenario():
            swap.DiscountRate.override(new_rate)
            npv = swap.NPV()

        pnl = npv - base_npv
        marker = "  <-- base" if bp == 0 else ""

        print(f"  {new_rate*100:>7.2f}% {bp:>+9}bp ${npv:>17,.2f} ${pnl:>+17,.2f}{marker}")

    print("  " + "━" * 65)

    # Verify DV01 approximation
    with dag.scenario():
        swap.DiscountRate.override(base_rate + 0.0001)
        npv_up = swap.NPV()

    actual_dv01 = abs(npv_up - base_npv)
    print(f"\n  DV01 Verification:")
    print(f"    Analytic DV01:  ${swap.DV01():,.2f}")
    print(f"    Numerical DV01: ${actual_dv01:,.2f}")
    print(f"    Difference:     ${abs(swap.DV01() - actual_dv01):,.2f}")


def payer_vs_receiver(swap: InterestRateSwap):
    """Compare payer and receiver swap behavior."""
    print("\n" + "=" * 70)
    print("  PAYER VS RECEIVER SWAP")
    print("=" * 70)

    # Create matching receiver swap
    receiver = InterestRateSwap()
    receiver.Notional.set(swap.Notional())
    receiver.FixedRate.set(swap.FixedRate())
    receiver.Maturity.set(swap.Maturity())
    receiver.DiscountRate.set(swap.DiscountRate())
    receiver.IsPayer.set(False)

    print(f"\n  With Fixed Rate = {swap.FixedRate()*100:.2f}%, Discount Rate = {swap.DiscountRate()*100:.2f}%:")
    print(f"\n  {'Swap Type':<15} {'NPV':>18} {'DV01':>12}")
    print("  " + "-" * 50)
    print(f"  {'Payer':<15} ${swap.NPV():>17,.2f} ${swap.DV01():>11,.2f}")
    print(f"  {'Receiver':<15} ${receiver.NPV():>17,.2f} ${receiver.DV01():>11,.2f}")
    print("  " + "-" * 50)
    print(f"  {'Net':<15} ${swap.NPV() + receiver.NPV():>17,.2f}")

    print(f"\n  Interpretation:")
    if swap.FixedRate() > swap.ParSwapRate():
        print(f"    - Fixed rate ({swap.FixedRate()*100:.2f}%) > Par rate ({swap.ParSwapRate()*100:.2f}%)")
        print(f"    - Payer swap is out-of-the-money (negative NPV)")
        print(f"    - Receiver swap is in-the-money (positive NPV)")
    else:
        print(f"    - Fixed rate ({swap.FixedRate()*100:.2f}%) < Par rate ({swap.ParSwapRate()*100:.2f}%)")
        print(f"    - Payer swap is in-the-money (positive NPV)")
        print(f"    - Receiver swap is out-of-the-money (negative NPV)")


def hedging_with_bond(swap: InterestRateSwap):
    """Demonstrate hedging a swap position with bonds."""
    print("\n" + "=" * 70)
    print("  HEDGING SWAP WITH BONDS (DV01 MATCHING)")
    print("=" * 70)

    swap_dv01 = swap.DV01()

    # Create a bond to hedge with
    bond = Bond()
    bond.FaceValue.set(1000.0)
    bond.CouponRate.set(0.04)
    bond.Maturity.set(5.0)
    bond.YieldToMaturity.set(swap.DiscountRate())

    # Calculate hedge ratio
    hedge_bonds = swap_dv01 / bond.DV01()

    print(f"\n  Swap Position:")
    print(f"    Notional:       ${swap.Notional():,.0f}")
    print(f"    Direction:      {'Payer (pay fixed)' if swap.IsPayer() else 'Receiver (receive fixed)'}")
    print(f"    DV01:           ${swap_dv01:,.2f}")

    print(f"\n  Hedge Instrument: 5Y Treasury Bond")
    print(f"    Price:          ${bond.Price():,.2f}")
    print(f"    DV01 per bond:  ${bond.DV01():.4f}")
    print(f"    Duration:       {bond.Duration():.2f} years")

    print(f"\n  Hedge Calculation:")
    print(f"    Bonds needed:   {hedge_bonds:,.0f} bonds")
    print(f"    Notional:       ${hedge_bonds * bond.Price():,.0f}")
    print(f"    Hedge DV01:     ${hedge_bonds * bond.DV01():,.2f}")

    # Verify hedge effectiveness with a rate shock
    print(f"\n  Hedge Effectiveness (+25bp rate shock):")

    swap_base = swap.NPV()
    bond_base = bond.Price()

    with dag.scenario():
        swap.DiscountRate.override(swap.DiscountRate() + 0.0025)
        bond.YieldToMaturity.override(bond.YieldToMaturity() + 0.0025)

        swap_stressed = swap.NPV()
        bond_stressed = bond.Price()

    swap_pnl = swap_stressed - swap_base
    # Short bonds to hedge payer swap (payer gains when rates rise, bonds lose)
    bond_pnl = -(bond_stressed - bond_base) * hedge_bonds

    net_pnl = swap_pnl + bond_pnl

    print(f"    Swap P&L:       ${swap_pnl:>+12,.2f}")
    print(f"    Bond P&L:       ${bond_pnl:>+12,.2f}")
    print(f"    Net P&L:        ${net_pnl:>+12,.2f}")
    print(f"\n    Hedge ratio:    {abs(net_pnl / swap_pnl) * 100:.1f}% residual")


def term_structure_example():
    """Show swaps across different tenors."""
    print("\n" + "=" * 70)
    print("  SWAP TERM STRUCTURE")
    print("=" * 70)

    print("\n  Swap characteristics by maturity (all at 3% fixed, 3.5% discount):")
    print("\n  " + "━" * 70)
    print(f"  {'Tenor':<8} {'NPV':>14} {'DV01':>12} {'Par Rate':>12} {'Annuity':>12}")
    print("  " + "━" * 70)

    tenors = [1, 2, 3, 5, 7, 10]

    for tenor in tenors:
        swap = create_swap(maturity=tenor, fixed_rate=0.03, discount_rate=0.035)
        print(f"  {tenor:>2}Y      ${swap.NPV():>13,.2f} ${swap.DV01():>11,.2f}  {swap.ParSwapRate()*100:>10.3f}%  {swap.Annuity():>11.4f}")

    print("  " + "━" * 70)


def main():
    print("=" * 70)
    print("  INTEREST RATE SWAP RISK ANALYSIS")
    print("=" * 70)

    # Create the main swap for examples
    swap = create_swap(
        notional=50_000_000.0,
        fixed_rate=0.03,
        maturity=5.0,
        is_payer=True,
        discount_rate=0.035,
    )

    swap_basics(swap)
    rate_scenario_ladder(swap)
    payer_vs_receiver(swap)
    hedging_with_bond(swap)
    term_structure_example()

    print("\n" + "=" * 70)
    print("  END OF SWAP RISK ANALYSIS")
    print("=" * 70)


if __name__ == "__main__":
    main()
