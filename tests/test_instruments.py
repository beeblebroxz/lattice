"""Tests for financial instruments."""

import pytest
import math
import dag
from lattice import Stock, Bond, InterestRateSwap, Forward, Future, FXPair, FXForward


@pytest.fixture(autouse=True)
def reset_dag():
    """Reset dag state before each test."""
    dag.reset()
    yield
    dag.reset()


class TestStock:
    """Tests for Stock instrument."""

    def test_default_values(self):
        stock = Stock()
        assert stock.Spot() == 100.0
        assert stock.DividendYield() == 0.0
        assert stock.Rate() == 0.05
        assert stock.TimeToExpiry() == 1.0

    def test_forward_price_no_dividend(self):
        """Forward price with no dividend: F = S * e^(r*T)"""
        stock = Stock()
        stock.Spot.set(100.0)
        stock.Rate.set(0.05)
        stock.DividendYield.set(0.0)
        stock.TimeToExpiry.set(1.0)

        expected = 100.0 * math.exp(0.05)
        assert abs(stock.ForwardPrice() - expected) < 0.0001

    def test_forward_price_with_dividend(self):
        """Forward price with dividend: F = S * e^((r-q)*T)"""
        stock = Stock()
        stock.Spot.set(100.0)
        stock.Rate.set(0.05)
        stock.DividendYield.set(0.02)
        stock.TimeToExpiry.set(1.0)

        expected = 100.0 * math.exp(0.03)  # r - q = 0.03
        assert abs(stock.ForwardPrice() - expected) < 0.0001

    def test_dividend_pv(self):
        """PV of dividends over the period."""
        stock = Stock()
        stock.Spot.set(100.0)
        stock.DividendYield.set(0.02)
        stock.TimeToExpiry.set(1.0)

        # PV(div) = S * (1 - e^(-q*T))
        expected = 100.0 * (1 - math.exp(-0.02))
        assert abs(stock.DividendPV() - expected) < 0.0001

    def test_carry_cost(self):
        """Carry cost = Forward - Spot"""
        stock = Stock()
        stock.Spot.set(100.0)
        stock.Rate.set(0.05)
        stock.DividendYield.set(0.02)
        stock.TimeToExpiry.set(1.0)

        carry = stock.CarryCost()
        assert abs(carry - (stock.ForwardPrice() - 100.0)) < 0.0001

    def test_reactivity(self):
        """Test that values update when inputs change."""
        stock = Stock()
        stock.Spot.set(100.0)
        stock.Rate.set(0.05)

        fwd1 = stock.ForwardPrice()

        stock.Spot.set(110.0)
        fwd2 = stock.ForwardPrice()

        assert fwd2 > fwd1


class TestBond:
    """Tests for Bond instrument."""

    def test_default_values(self):
        bond = Bond()
        assert bond.FaceValue() == 1000.0
        assert bond.CouponRate() == 0.05
        assert bond.Maturity() == 10.0
        assert bond.YieldToMaturity() == 0.05
        assert bond.Frequency() == 2

    def test_par_bond_price(self):
        """A bond priced at par when coupon rate equals YTM."""
        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.CouponRate.set(0.05)
        bond.YieldToMaturity.set(0.05)
        bond.Maturity.set(10.0)
        bond.Frequency.set(2)

        # Price should be very close to face value
        assert abs(bond.Price() - 1000.0) < 0.01

    def test_premium_bond(self):
        """Bond trades at premium when coupon > YTM."""
        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.CouponRate.set(0.06)  # 6% coupon
        bond.YieldToMaturity.set(0.04)  # 4% YTM
        bond.Maturity.set(10.0)

        assert bond.Price() > 1000.0

    def test_discount_bond(self):
        """Bond trades at discount when coupon < YTM."""
        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.CouponRate.set(0.04)  # 4% coupon
        bond.YieldToMaturity.set(0.06)  # 6% YTM
        bond.Maturity.set(10.0)

        assert bond.Price() < 1000.0

    def test_duration_positive(self):
        """Duration should always be positive."""
        bond = Bond()
        bond.Maturity.set(10.0)
        assert bond.Duration() > 0

    def test_duration_less_than_maturity(self):
        """Duration should be less than maturity for coupon-paying bonds."""
        bond = Bond()
        bond.CouponRate.set(0.05)
        bond.Maturity.set(10.0)

        assert bond.Duration() < 10.0

    def test_modified_duration(self):
        """Modified duration = Duration / (1 + y/freq)"""
        bond = Bond()
        bond.YieldToMaturity.set(0.06)
        bond.Frequency.set(2)

        expected = bond.Duration() / (1 + 0.03)
        assert abs(bond.ModifiedDuration() - expected) < 0.0001

    def test_convexity_positive(self):
        """Convexity should be positive."""
        bond = Bond()
        assert bond.Convexity() > 0

    def test_dv01_positive(self):
        """DV01 should be positive."""
        bond = Bond()
        assert bond.DV01() > 0

    def test_price_yield_inverse(self):
        """Price and yield move in opposite directions."""
        bond = Bond()
        bond.YieldToMaturity.set(0.04)
        price1 = bond.Price()

        bond.YieldToMaturity.set(0.05)
        price2 = bond.Price()

        assert price2 < price1


class TestForward:
    """Tests for Forward instrument."""

    def test_default_values(self):
        forward = Forward()
        assert forward.Spot() == 100.0
        assert forward.Rate() == 0.05
        assert forward.TimeToExpiry() == 1.0

    def test_forward_price_simple(self):
        """Forward price: F = S * e^(r*T)"""
        forward = Forward()
        forward.Spot.set(100.0)
        forward.Rate.set(0.05)
        forward.DividendYield.set(0.0)
        forward.TimeToExpiry.set(1.0)

        expected = 100.0 * math.exp(0.05)
        assert abs(forward.ForwardPrice() - expected) < 0.0001

    def test_forward_price_with_yield(self):
        """Forward price with dividend yield."""
        forward = Forward()
        forward.Spot.set(100.0)
        forward.Rate.set(0.05)
        forward.DividendYield.set(0.02)
        forward.TimeToExpiry.set(1.0)

        expected = 100.0 * math.exp(0.03)
        assert abs(forward.ForwardPrice() - expected) < 0.0001

    def test_value_at_inception(self):
        """Forward value is zero at inception (when contract price = forward price)."""
        forward = Forward()
        forward.Spot.set(100.0)
        forward.Rate.set(0.05)
        forward.TimeToExpiry.set(1.0)

        # Set contract price to fair forward price
        forward.ContractPrice.set(forward.ForwardPrice())

        assert abs(forward.Value()) < 0.0001

    def test_value_long_positive(self):
        """Long forward gains when forward price > contract price."""
        forward = Forward()
        forward.Spot.set(100.0)
        forward.Rate.set(0.05)
        forward.TimeToExpiry.set(1.0)
        forward.ContractPrice.set(100.0)  # Below fair forward
        forward.IsLong.set(True)

        assert forward.Value() > 0

    def test_value_short_positive(self):
        """Short forward gains when forward price < contract price."""
        forward = Forward()
        forward.Spot.set(100.0)
        forward.Rate.set(0.05)
        forward.TimeToExpiry.set(1.0)
        forward.ContractPrice.set(110.0)  # Above fair forward
        forward.IsLong.set(False)

        assert forward.Value() > 0

    def test_delta_long(self):
        """Long forward has positive delta."""
        forward = Forward()
        forward.IsLong.set(True)
        assert forward.Delta() > 0

    def test_delta_short(self):
        """Short forward has negative delta."""
        forward = Forward()
        forward.IsLong.set(False)
        assert forward.Delta() < 0

    def test_gamma_zero(self):
        """Forward has zero gamma (linear payoff)."""
        forward = Forward()
        assert forward.Gamma() == 0.0


class TestFuture:
    """Tests for Future instrument (inherits from Forward)."""

    def test_inherits_forward(self):
        """Future should have all Forward methods."""
        future = Future()
        assert hasattr(future, 'ForwardPrice')
        assert hasattr(future, 'Value')
        assert hasattr(future, 'Delta')

    def test_notional_value(self):
        """Notional = Forward Price * Contract Size"""
        future = Future()
        future.Spot.set(100.0)
        future.Rate.set(0.05)
        future.TimeToExpiry.set(1.0)
        future.ContractSize.set(100)

        expected = future.ForwardPrice() * 100
        assert abs(future.NotionalValue() - expected) < 0.01


class TestFXPair:
    """Tests for FXPair instrument."""

    def test_default_values(self):
        fx = FXPair()
        assert fx.BaseCurrency() == "EUR"
        assert fx.QuoteCurrency() == "USD"
        assert fx.Spot() == 1.0
        assert fx.BaseRate() == 0.05
        assert fx.QuoteRate() == 0.05

    def test_pair_name(self):
        fx = FXPair()
        fx.BaseCurrency.set("GBP")
        fx.QuoteCurrency.set("JPY")
        assert fx.PairName() == "GBP/JPY"

    def test_forward_rate_interest_parity(self):
        """Forward rate follows covered interest rate parity."""
        fx = FXPair()
        fx.Spot.set(1.10)
        fx.BaseRate.set(0.02)  # EUR rate
        fx.QuoteRate.set(0.05)  # USD rate
        fx.TimeToExpiry.set(1.0)

        # F = S * e^((r_quote - r_base) * T)
        expected = 1.10 * math.exp(0.03)  # 5% - 2% = 3%
        assert abs(fx.ForwardRate() - expected) < 0.0001

    def test_forward_premium(self):
        """Forward premium when quote rate > base rate."""
        fx = FXPair()
        fx.Spot.set(1.10)
        fx.BaseRate.set(0.02)
        fx.QuoteRate.set(0.05)

        # Forward should be higher than spot (premium)
        assert fx.ForwardRate() > fx.Spot()
        assert fx.ForwardPoints() > 0

    def test_forward_discount(self):
        """Forward discount when base rate > quote rate."""
        fx = FXPair()
        fx.Spot.set(1.10)
        fx.BaseRate.set(0.05)
        fx.QuoteRate.set(0.02)

        # Forward should be lower than spot (discount)
        assert fx.ForwardRate() < fx.Spot()
        assert fx.ForwardPoints() < 0

    def test_forward_points_pips(self):
        """Forward points in pips (10000x)."""
        fx = FXPair()
        fx.Spot.set(1.10)
        fx.BaseRate.set(0.04)
        fx.QuoteRate.set(0.05)
        fx.TimeToExpiry.set(1.0)

        points = fx.ForwardPoints()
        pips = fx.ForwardPointsPips()
        assert abs(pips - points * 10000) < 0.01

    def test_inverse_spot(self):
        """Inverse spot = 1 / spot."""
        fx = FXPair()
        fx.Spot.set(1.25)
        assert abs(fx.InverseSpot() - 0.8) < 0.0001

    def test_carry_return(self):
        """Carry return = (r_base - r_quote) * T."""
        fx = FXPair()
        fx.BaseRate.set(0.04)
        fx.QuoteRate.set(0.02)
        fx.TimeToExpiry.set(1.0)

        expected = 0.02  # 4% - 2%
        assert abs(fx.CarryReturn() - expected) < 0.0001


class TestFXForward:
    """Tests for FXForward instrument."""

    def test_inherits_fx_pair(self):
        """FXForward should have all FXPair methods."""
        fwd = FXForward()
        assert hasattr(fwd, 'ForwardRate')
        assert hasattr(fwd, 'ForwardPoints')
        assert hasattr(fwd, 'PairName')

    def test_value_at_inception(self):
        """Value is zero when contract rate = forward rate."""
        fwd = FXForward()
        fwd.Spot.set(1.10)
        fwd.BaseRate.set(0.04)
        fwd.QuoteRate.set(0.05)
        fwd.TimeToExpiry.set(1.0)
        fwd.ContractRate.set(fwd.ForwardRate())

        assert abs(fwd.Value()) < 0.01

    def test_value_long_gains(self):
        """Long base gains when forward > contract rate."""
        fwd = FXForward()
        fwd.Spot.set(1.10)
        fwd.BaseRate.set(0.04)
        fwd.QuoteRate.set(0.05)
        fwd.TimeToExpiry.set(1.0)
        fwd.ContractRate.set(1.08)  # Below forward
        fwd.IsLongBase.set(True)
        fwd.BaseNotional.set(1000000)

        assert fwd.Value() > 0

    def test_value_short_gains(self):
        """Short base gains when forward < contract rate."""
        fwd = FXForward()
        fwd.Spot.set(1.10)
        fwd.BaseRate.set(0.04)
        fwd.QuoteRate.set(0.05)
        fwd.TimeToExpiry.set(1.0)
        fwd.ContractRate.set(1.15)  # Above forward
        fwd.IsLongBase.set(False)
        fwd.BaseNotional.set(1000000)

        assert fwd.Value() > 0

    def test_delta_long(self):
        """Long base has positive delta."""
        fwd = FXForward()
        fwd.IsLongBase.set(True)
        assert fwd.Delta() > 0

    def test_delta_short(self):
        """Short base has negative delta."""
        fwd = FXForward()
        fwd.IsLongBase.set(False)
        assert fwd.Delta() < 0


class TestInterestRateSwap:
    """Tests for InterestRateSwap instrument."""

    def test_default_values(self):
        """Test default parameter values."""
        swap = InterestRateSwap()
        assert swap.Notional() == 1_000_000.0
        assert swap.FixedRate() == 0.03
        assert swap.Maturity() == 5.0
        assert swap.Frequency() == 4
        assert swap.IsPayer() is True

    def test_par_swap_zero_npv(self):
        """A swap at par rate should have zero NPV."""
        swap = InterestRateSwap()
        swap.Notional.set(10_000_000.0)
        swap.Maturity.set(5.0)
        swap.DiscountRate.set(0.04)

        # Set fixed rate to par rate
        par_rate = swap.ParSwapRate()
        swap.FixedRate.set(par_rate)

        assert abs(swap.NPV()) < 1.0  # Within $1

    def test_payer_swap_gains_when_rates_rise(self):
        """Payer swap should gain value when rates rise."""
        swap = InterestRateSwap()
        swap.IsPayer.set(True)
        swap.FixedRate.set(0.03)
        swap.DiscountRate.set(0.03)

        npv_base = swap.NPV()

        swap.DiscountRate.set(0.04)  # Rates rise
        npv_up = swap.NPV()

        assert npv_up > npv_base

    def test_receiver_swap_gains_when_rates_fall(self):
        """Receiver swap should gain value when rates fall."""
        swap = InterestRateSwap()
        swap.IsPayer.set(False)
        swap.FixedRate.set(0.03)
        swap.DiscountRate.set(0.03)

        npv_base = swap.NPV()

        swap.DiscountRate.set(0.02)  # Rates fall
        npv_down = swap.NPV()

        assert npv_down > npv_base

    def test_dv01_positive(self):
        """DV01 should always be positive."""
        swap = InterestRateSwap()
        assert swap.DV01() > 0

    def test_dv01_increases_with_maturity(self):
        """Longer swaps have higher DV01."""
        swap_short = InterestRateSwap()
        swap_short.Maturity.set(2.0)

        swap_long = InterestRateSwap()
        swap_long.Maturity.set(10.0)

        assert swap_long.DV01() > swap_short.DV01()

    def test_dv01_scales_with_notional(self):
        """DV01 should scale linearly with notional."""
        swap1 = InterestRateSwap()
        swap1.Notional.set(1_000_000.0)

        swap2 = InterestRateSwap()
        swap2.Notional.set(2_000_000.0)

        assert abs(swap2.DV01() / swap1.DV01() - 2.0) < 0.01

    def test_annuity_positive(self):
        """Annuity factor should be positive."""
        swap = InterestRateSwap()
        assert swap.Annuity() > 0

    def test_par_rate_close_to_discount_rate(self):
        """Par swap rate should be close to the discount rate."""
        swap = InterestRateSwap()
        swap.DiscountRate.set(0.04)

        par_rate = swap.ParSwapRate()
        # Par rate should be close to the discount rate
        assert abs(par_rate - 0.04) < 0.005

    def test_payer_vs_receiver_opposite_npv(self):
        """Payer and receiver swaps should have opposite NPVs."""
        swap_payer = InterestRateSwap()
        swap_payer.IsPayer.set(True)
        swap_payer.FixedRate.set(0.04)
        swap_payer.DiscountRate.set(0.03)

        swap_receiver = InterestRateSwap()
        swap_receiver.IsPayer.set(False)
        swap_receiver.FixedRate.set(0.04)
        swap_receiver.DiscountRate.set(0.03)

        assert abs(swap_payer.NPV() + swap_receiver.NPV()) < 1.0

    def test_scenario_override_reverts(self):
        """Scenario overrides should revert after context."""
        swap = InterestRateSwap()
        swap.DiscountRate.set(0.03)

        original_npv = swap.NPV()

        with dag.scenario():
            swap.DiscountRate.override(0.05)
            _ = swap.NPV()  # Different value inside scenario

        assert swap.NPV() == original_npv

    def test_summary_format(self):
        """Summary should follow expected format."""
        swap = InterestRateSwap()
        swap.FixedRate.set(0.035)
        swap.Maturity.set(7.0)
        swap.IsPayer.set(True)

        summary = swap.Summary()
        assert "3.50%" in summary
        assert "7Y" in summary
        assert "Payer" in summary

    def test_market_value_equals_npv(self):
        """MarketValue should equal NPV."""
        swap = InterestRateSwap()
        assert swap.MarketValue() == swap.NPV()

    def test_price_equals_npv(self):
        """Price should equal NPV (risk module compatibility)."""
        swap = InterestRateSwap()
        assert swap.Price() == swap.NPV()

    def test_yield_to_maturity_alias(self):
        """YieldToMaturity should return DiscountRate (for risk module)."""
        swap = InterestRateSwap()
        swap.DiscountRate.set(0.045)
        assert swap.YieldToMaturity() == swap.DiscountRate()

    def test_fixed_leg_pv_calculation(self):
        """Fixed leg PV should equal fixed payment times annuity."""
        swap = InterestRateSwap()
        swap.Notional.set(1_000_000.0)
        swap.FixedRate.set(0.04)
        swap.Frequency.set(4)

        expected = swap.FixedPayment() * swap.Annuity()
        assert abs(swap.FixedLegPV() - expected) < 0.01

    def test_floating_leg_pv_calculation(self):
        """Floating leg PV = Notional * (1 - DF_n) at reset."""
        swap = InterestRateSwap()
        swap.Notional.set(5_000_000.0)
        swap.Maturity.set(5.0)
        swap.Frequency.set(4)
        swap.DiscountRate.set(0.04)

        # Calculate expected: Notional * (1 - DF_n)
        r = swap.DiscountRate() / swap.Frequency()  # periodic rate
        n = int(swap.Maturity() * swap.Frequency())  # num periods
        df_n = 1 / ((1 + r) ** n)
        expected = swap.Notional() * (1 - df_n)

        assert abs(swap.FloatingLegPV() - expected) < 0.01

    def test_num_periods(self):
        """Number of periods should be maturity times frequency."""
        swap = InterestRateSwap()
        swap.Maturity.set(5.0)
        swap.Frequency.set(4)

        assert swap.NumPeriods() == 20
