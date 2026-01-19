"""Tests for Black-Scholes pricing model."""

import pytest
import math
from lattice.models.blackscholes import (
    norm_cdf,
    norm_pdf,
    black_scholes_price,
    black_scholes_delta,
    black_scholes_gamma,
    black_scholes_vega,
    black_scholes_theta,
    black_scholes_rho,
)


class TestNormalDistribution:
    """Tests for normal distribution functions."""

    def test_norm_cdf_zero(self):
        assert norm_cdf(0) == pytest.approx(0.5)

    def test_norm_cdf_large_positive(self):
        assert norm_cdf(10) == pytest.approx(1.0, abs=1e-10)

    def test_norm_cdf_large_negative(self):
        assert norm_cdf(-10) == pytest.approx(0.0, abs=1e-10)

    def test_norm_cdf_symmetry(self):
        x = 1.5
        assert norm_cdf(x) + norm_cdf(-x) == pytest.approx(1.0)

    def test_norm_pdf_zero(self):
        expected = 1.0 / math.sqrt(2 * math.pi)
        assert norm_pdf(0) == pytest.approx(expected)

    def test_norm_pdf_symmetry(self):
        x = 1.5
        assert norm_pdf(x) == pytest.approx(norm_pdf(-x))


class TestBlackScholesPrice:
    """Tests for Black-Scholes price calculation."""

    def test_atm_call(self):
        """ATM call should have positive value."""
        price = black_scholes_price(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=True
        )
        assert price > 0
        assert price < 100  # Should be less than spot

    def test_atm_put(self):
        """ATM put should have positive value."""
        price = black_scholes_price(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=False
        )
        assert price > 0
        assert price < 100

    def test_put_call_parity(self):
        """Put-call parity: C - P = S*exp(-q*T) - K*exp(-r*T)."""
        spot, strike, rate, dividend, vol, T = 100, 100, 0.05, 0.02, 0.2, 1.0

        call = black_scholes_price(spot, strike, rate, dividend, vol, T, True)
        put = black_scholes_price(spot, strike, rate, dividend, vol, T, False)

        expected_diff = (
            spot * math.exp(-dividend * T) - strike * math.exp(-rate * T)
        )
        assert call - put == pytest.approx(expected_diff, rel=1e-6)

    def test_deep_itm_call(self):
        """Deep ITM call should be close to intrinsic value."""
        price = black_scholes_price(
            spot=150, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0.01, is_call=True
        )
        intrinsic = 150 - 100
        assert price >= intrinsic * 0.99

    def test_deep_otm_call(self):
        """Deep OTM call should be close to zero."""
        price = black_scholes_price(
            spot=50, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0.01, is_call=True
        )
        assert price < 1

    def test_expired_call_itm(self):
        """Expired ITM call should equal intrinsic value."""
        price = black_scholes_price(
            spot=110, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0, is_call=True
        )
        assert price == pytest.approx(10.0)

    def test_expired_call_otm(self):
        """Expired OTM call should be zero."""
        price = black_scholes_price(
            spot=90, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0, is_call=True
        )
        assert price == pytest.approx(0.0)

    def test_higher_vol_higher_price(self):
        """Higher volatility should increase option price."""
        base_args = dict(spot=100, strike=100, rate=0.05, dividend=0, time_to_expiry=1.0, is_call=True)
        low_vol = black_scholes_price(**base_args, volatility=0.1)
        high_vol = black_scholes_price(**base_args, volatility=0.3)
        assert high_vol > low_vol


class TestBlackScholesDelta:
    """Tests for Black-Scholes delta calculation."""

    def test_call_delta_range(self):
        """Call delta should be between 0 and 1."""
        delta = black_scholes_delta(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=True
        )
        assert 0 < delta < 1

    def test_put_delta_range(self):
        """Put delta should be between -1 and 0."""
        delta = black_scholes_delta(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=False
        )
        assert -1 < delta < 0

    def test_deep_itm_call_delta(self):
        """Deep ITM call delta should be close to 1."""
        delta = black_scholes_delta(
            spot=200, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0.1, is_call=True
        )
        assert delta > 0.95

    def test_deep_otm_call_delta(self):
        """Deep OTM call delta should be close to 0."""
        delta = black_scholes_delta(
            spot=50, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0.1, is_call=True
        )
        assert delta < 0.05


class TestBlackScholesGamma:
    """Tests for Black-Scholes gamma calculation."""

    def test_gamma_positive(self):
        """Gamma should always be positive."""
        gamma = black_scholes_gamma(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0
        )
        assert gamma > 0

    def test_gamma_max_at_atm(self):
        """Gamma should be highest ATM."""
        atm_gamma = black_scholes_gamma(100, 100, 0.05, 0, 0.2, 1.0)
        itm_gamma = black_scholes_gamma(120, 100, 0.05, 0, 0.2, 1.0)
        otm_gamma = black_scholes_gamma(80, 100, 0.05, 0, 0.2, 1.0)
        assert atm_gamma > itm_gamma
        assert atm_gamma > otm_gamma


class TestBlackScholesVega:
    """Tests for Black-Scholes vega calculation."""

    def test_vega_positive(self):
        """Vega should always be positive."""
        vega = black_scholes_vega(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0
        )
        assert vega > 0

    def test_vega_zero_at_expiry(self):
        """Vega should be zero at expiry."""
        vega = black_scholes_vega(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=0
        )
        assert vega == 0


class TestBlackScholesTheta:
    """Tests for Black-Scholes theta calculation."""

    def test_call_theta_negative(self):
        """Call theta should typically be negative (time decay)."""
        theta = black_scholes_theta(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=True
        )
        assert theta < 0


class TestBlackScholesRho:
    """Tests for Black-Scholes rho calculation."""

    def test_call_rho_positive(self):
        """Call rho should be positive."""
        rho = black_scholes_rho(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=True
        )
        assert rho > 0

    def test_put_rho_negative(self):
        """Put rho should be negative."""
        rho = black_scholes_rho(
            spot=100, strike=100, rate=0.05, dividend=0,
            volatility=0.2, time_to_expiry=1.0, is_call=False
        )
        assert rho < 0
