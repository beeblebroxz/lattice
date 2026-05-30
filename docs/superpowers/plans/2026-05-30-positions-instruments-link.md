# Positions ↔ Instruments Link — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Link each `Position` to a live `Instrument` so book value, multi-factor stress, and portfolio Greeks derive reactively from instrument pricing.

**Architecture:** A `Position` gains an optional `LinkedInstrument` dag-Input node; `EffectivePrice` returns the instrument's `MarketValue()` when linked, else today's `MarketPrice`. `TradingSystem` holds a `symbol → Instrument` registry. Book stress overrides the linked instruments' factors (deduped); `Book.Delta/Vega/Gamma` sum per-instrument sensitivities. A shared shock convention (spot/vol relative, rate absolute) unifies all stress paths.

**Tech Stack:** Python 3, `dag` (reactive graph), `livetable`, pytest. All risk is bump-and-reval inside `dag.scenario()`.

**Spec:** `docs/superpowers/specs/2026-05-30-positions-instruments-link-design.md`

**Conventions:** computed functions are PascalCase; run tests with `python3 -m pytest`; commit after each green task; co-author trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## Task 1: Position instrument link

**Files:**
- Modify: `lattice/trading/position.py` (the `MarketValue` computed, ~line 64-67)
- Test: `tests/test_trading.py`

- [ ] **Step 1: Write the failing tests**

Add these imports near the top of `tests/test_trading.py` (it currently imports only `from lattice.trading import PositionTable, TradeBlotter`):

```python
import dag
from lattice.trading import Position
from lattice import VanillaOption
```

Append this test class to `tests/test_trading.py`:

```python
class TestPositionInstrumentLink:
    """Position can optionally derive its value from a live instrument."""

    def _option(self):
        o = VanillaOption()
        o.Spot.set(100.0); o.Strike.set(100.0)
        o.Volatility.set(0.20); o.Rate.set(0.04)
        return o

    def test_unlinked_uses_market_price(self):
        pos = Position()
        pos.Quantity.set(10); pos.AvgPrice.set(5.0); pos.MarketPrice.set(6.0)
        assert pos.EffectivePrice() == 6.0
        assert pos.MarketValue() == 60.0
        assert pos.UnrealizedPnL() == 10.0   # 60 - 10*5

    def test_linked_uses_instrument_value(self):
        opt = self._option()
        pos = Position(); pos.Quantity.set(10); pos.AvgPrice.set(5.0)
        pos.LinkedInstrument.set(opt)
        assert pos.EffectivePrice() == opt.MarketValue()
        assert pos.MarketValue() == 10 * opt.MarketValue()

    def test_dynamic_link_recomputes_then_reverts(self):
        opt = self._option()
        pos = Position(); pos.Quantity.set(10); pos.MarketPrice.set(5.0)
        assert pos.MarketValue() == 50.0          # evaluated while unlinked
        pos.LinkedInstrument.set(opt)             # link AFTER first eval
        assert abs(pos.MarketValue() - 10 * opt.MarketValue()) < 1e-9
        pos.LinkedInstrument.set(None)            # unlink
        assert pos.MarketValue() == 50.0

    def test_linked_reprices_on_instrument_change(self):
        opt = self._option()
        pos = Position(); pos.Quantity.set(10); pos.LinkedInstrument.set(opt)
        before = pos.MarketValue()
        opt.Spot.set(120.0)                       # ITM call -> higher value
        assert pos.MarketValue() > before
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_trading.py::TestPositionInstrumentLink -v`
Expected: FAIL — `AttributeError: 'Position' object has no attribute 'LinkedInstrument'` (and `EffectivePrice`).

- [ ] **Step 3: Implement the link on `Position`**

In `lattice/trading/position.py`, add the two computed nodes in the `# Inputs` / `# Computed` area, and change `MarketValue` to use `EffectivePrice`. Replace the existing `MarketValue`:

```python
    @dag.computed
    def MarketValue(self) -> float:
        """Current market value (signed)."""
        return self.Quantity() * self.MarketPrice()
```

with:

```python
    @dag.computed(dag.Input | dag.Optional)
    def LinkedInstrument(self):
        """Optional live instrument backing this position (None = price-only)."""
        return None

    @dag.computed
    def EffectivePrice(self) -> float:
        """Per-unit price: the instrument's market value if linked, else MarketPrice."""
        inst = self.LinkedInstrument()
        return inst.MarketValue() if inst is not None else self.MarketPrice()

    @dag.computed
    def MarketValue(self) -> float:
        """Current market value (signed). Uses the linked instrument when present."""
        return self.Quantity() * self.EffectivePrice()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_trading.py -v`
Expected: PASS (new class + all existing `test_trading.py` tests still green).

- [ ] **Step 5: Commit**

```bash
git add lattice/trading/position.py tests/test_trading.py
git commit -m "$(cat <<'EOF'
Add optional instrument link to Position

Position gains a LinkedInstrument dag-Input node and an EffectivePrice
computed; MarketValue derives from the instrument's MarketValue() when linked,
else the existing MarketPrice (unlinked behavior unchanged).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: TradingSystem instrument registry

**Files:**
- Modify: `lattice/trading/system.py` (`__init__` ~line 56-83; `_update_position` ~line 195-220; `set_market_price` ~line 254-273)
- Test: `tests/test_trading.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_trading.py` (imports `TradingSystem`, `VanillaOption`, `pytest` — add `from lattice.trading import TradingSystem` to the imports if not present):

```python
class TestInstrumentRegistry:
    """TradingSystem can back a symbol with a live instrument."""

    def _option(self):
        o = VanillaOption()
        o.Spot.set(100.0); o.Strike.set(100.0)
        o.Volatility.set(0.20); o.Rate.set(0.04)
        return o

    def test_register_links_existing_position(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        sys.trade(desk, client, "AAPL", 100, 5.0)        # position created first
        opt = self._option()
        sys.register_instrument("AAPL", opt)             # then registered
        pos = sys.positions_for(desk)[0]
        assert pos.LinkedInstrument() is opt
        assert abs(pos.MarketValue() - 100 * opt.MarketValue()) < 1e-9

    def test_register_links_future_position(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        opt = self._option()
        sys.register_instrument("AAPL", opt)             # registered first
        sys.trade(desk, client, "AAPL", 100, 5.0)        # position created after
        pos = sys.positions_for(desk)[0]
        assert pos.LinkedInstrument() is opt

    def test_set_market_price_raises_for_linked_symbol(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        opt = self._option()
        sys.register_instrument("AAPL", opt)
        with pytest.raises(ValueError):
            sys.set_market_price("AAPL", 5.5)

    def test_set_market_price_still_works_for_unlinked(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        sys.trade(desk, client, "AAPL", 100, 5.0)
        sys.set_market_price("AAPL", 6.0)                # unlinked symbol: fine
        assert sys.get_market_price("AAPL") == 6.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_trading.py::TestInstrumentRegistry -v`
Expected: FAIL — `AttributeError: 'TradingSystem' object has no attribute 'register_instrument'`.

- [ ] **Step 3: Implement the registry**

In `lattice/trading/system.py`, add the import near the top (after `from .position import Position`):

```python
from lattice.instruments.base import Instrument
```

In `__init__`, after the `self._market_prices: Dict[str, float] = {}` line, add:

```python
        # Symbol -> live instrument (optional reactive pricing source)
        self._instruments: Dict[str, Instrument] = {}
```

Add these two methods (e.g. right after `get_market_price`):

```python
    def register_instrument(self, symbol: str, instrument: Instrument) -> None:
        """Back a symbol with a live instrument.

        Existing and future positions in this symbol price reactively off the
        instrument. For a registered symbol, move the market by setting the
        instrument's inputs (e.g. instrument.Spot.set(...)), not set_market_price.
        """
        self._instruments[symbol] = instrument
        for (book_id, sym), pos in self._positions.items():
            if sym == symbol:
                pos.LinkedInstrument.set(instrument)

    def get_instrument(self, symbol: str) -> Optional[Instrument]:
        """Return the instrument registered for a symbol, or None."""
        return self._instruments.get(symbol)
```

In `_update_position`, inside the new-position branch (right after the existing
`if symbol in self._market_prices: pos.MarketPrice.set(...)` block), add:

```python
            # Link to a registered instrument if one exists for this symbol
            if symbol in self._instruments:
                pos.LinkedInstrument.set(self._instruments[symbol])
```

In `set_market_price`, add the guard as the first statement:

```python
    def set_market_price(self, symbol: str, price: float) -> None:
        if symbol in self._instruments:
            raise ValueError(
                f"Symbol '{symbol}' is instrument-linked; set the instrument's "
                f"inputs instead (e.g. instrument.Spot.set(...)), not a scalar "
                f"market price."
            )
        self._market_prices[symbol] = price
        # ... existing body unchanged ...
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_trading.py -v`
Expected: PASS (registry class + existing tests green).

- [ ] **Step 5: Commit**

```bash
git add lattice/trading/system.py tests/test_trading.py
git commit -m "$(cat <<'EOF'
Add symbol->instrument registry to TradingSystem

register_instrument links existing and future positions for a symbol;
set_market_price raises for linked symbols (drive the instrument instead).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Shared shock convention (fixes absolute-vs-relative bug)

**Files:**
- Create: `lattice/risk/shocks.py`
- Modify: `lattice/risk/engine.py` (`stress_test`, ~line 179-184)
- Modify: `lattice/workflows/activities.py` (`compute_stress_test`, ~line 308-313)
- Test: `tests/test_risk.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_risk.py`:

```python
class TestShockConvention:
    """Spot/vol shocks are relative; rate/yield shocks are absolute (bp)."""

    def test_relative_for_spot_and_vol(self):
        from lattice.risk.shocks import shocked_value
        assert shocked_value("Spot", 100.0, -0.20) == pytest.approx(80.0)
        assert shocked_value("Volatility", 0.20, 0.50) == pytest.approx(0.30)

    def test_absolute_for_rate_and_yield(self):
        from lattice.risk.shocks import shocked_value
        assert shocked_value("Rate", 0.04, 0.01) == pytest.approx(0.05)
        assert shocked_value("YieldToMaturity", 0.05, 0.01) == pytest.approx(0.06)

    def test_engine_stress_test_rate_is_additive(self):
        option = VanillaOption()
        option.Spot.set(100.0); option.Strike.set(100.0)
        option.Volatility.set(0.20); option.Rate.set(0.04)
        engine = RiskEngine(); engine.add(option, "OPT")
        # Expected stressed price = price with Rate moved +100bp (0.04 -> 0.05)
        with dag.scenario():
            option.Rate.override(0.05)
            expected = option.Price()
        res = engine.stress_test(Rate=0.01)
        assert res["OPT"]["stressed_price"] == pytest.approx(expected)
```

(`tests/test_risk.py` already imports `pytest`, `dag`, `VanillaOption`, `RiskEngine`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_risk.py::TestShockConvention -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lattice.risk.shocks'`.

- [ ] **Step 3: Create the helper and wire it in**

Create `lattice/risk/shocks.py`:

```python
"""Shock-application convention shared by all stress paths.

Rate-like factors are quoted in absolute terms (basis points), so a +100bp
shock is ``Rate + 0.01``. Price- and vol-like factors are quoted in relative
terms, so a shock ``s`` means ``value * (1 + s)``.
"""

# Instrument inputs shocked additively (rates / yields). Everything else relative.
ABSOLUTE_FACTORS = frozenset({"Rate", "YieldToMaturity"})


def shocked_value(factor: str, current: float, shock: float) -> float:
    """Return the post-shock value of an instrument input under the convention.

    Args:
        factor: Instrument input name (e.g. "Spot", "Volatility", "Rate").
        current: Current value of that input.
        shock: Shock magnitude (relative fraction, or absolute for rate-like).
    """
    if factor in ABSOLUTE_FACTORS:
        return current + shock
    return current * (1 + shock)
```

In `lattice/risk/engine.py`, add the import near the top:

```python
from .shocks import shocked_value
```

In `stress_test`, replace:

```python
                        accessor.override(current_value * (1 + shock))
```

with:

```python
                        accessor.override(shocked_value(input_name, current_value, shock))
```

In `lattice/workflows/activities.py`, add the import near the top:

```python
from lattice.risk.shocks import shocked_value
```

In `compute_stress_test`, replace:

```python
                accessor.override(current_value * (1 + shock))
```

with:

```python
                accessor.override(shocked_value(input_name, current_value, shock))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_risk.py tests/test_workflows.py -v`
Expected: PASS (new class green; existing engine/workflow stress tests still green — they assert only direction/sign, not rate magnitude).

- [ ] **Step 5: Commit**

```bash
git add lattice/risk/shocks.py lattice/risk/engine.py lattice/workflows/activities.py tests/test_risk.py
git commit -m "$(cat <<'EOF'
Unify shock convention: rates additive, spot/vol relative

Adds risk.shocks.shocked_value and applies it in engine.stress_test and the
Temporal compute_stress_test activity. Fixes the latent bug where rate/vol
shocks were applied relatively (a +100bp rate shock moved 0.04 to 0.0404
instead of 0.05).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Multi-factor book stress

**Files:**
- Modify: `lattice/risk/portfolio.py` (`stress`, ~line 52-93)
- Modify: `lattice/risk/scenarios.py` (`run_scenario` ~line 86-118; `SCENARIOS` vol legs)
- Test: `tests/test_risk.py` (remove the now-obsolete Area-A rejection test; add multi-factor tests)

- [ ] **Step 1: Update tests — remove obsolete rejection, add multi-factor**

In `tests/test_risk.py`, DELETE `test_stress_rejects_unsupported_shocks` (in `TestPortfolioRisk`). It asserted `stress(desk, vol_shock=...)` raises `TypeError`; `stress` now accepts vol/rate. Replace it with:

```python
    def test_stress_accepts_vol_rate_skipped_on_unlinked_book(self, trading_system):
        """An unlinked book has no instrument to absorb vol/rate; report them skipped."""
        system, desk = trading_system
        result = risk.stress(desk, spot_shock=-0.10, vol_shock=0.5, rate_shock=0.01)
        assert "spot_shock" in result["applied_shocks"]
        assert result["skipped_shocks"] == {"vol_shock": 0.5, "rate_shock": 0.01}
        assert result["pnl_impact"] < 0          # spot leg still moves the book
```

Append a new class for the linked path:

```python
class TestMultiFactorStress:
    """A book of instrument-linked positions absorbs vol and rate shocks."""

    def _linked_book(self):
        from lattice.trading import TradingSystem
        system = TradingSystem()
        desk = system.book("DESK"); client = system.book("CLIENT")
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0)
        opt.Volatility.set(0.20); opt.Rate.set(0.04)
        system.register_instrument("OPT", opt)
        system.trade(desk, client, "OPT", 100, opt.MarketValue())
        return system, desk, opt

    def test_vol_shock_moves_linked_book(self):
        system, desk, opt = self._linked_book()
        base = desk.TotalPnL()
        result = risk.stress(desk, vol_shock=0.5)        # +50% vol -> higher option value
        assert result["pnl_impact"] > 0
        assert result["applied_shocks"] == {"vol_shock": 0.5}
        assert desk.TotalPnL() == pytest.approx(base)    # reverted after scenario

    def test_rate_shock_is_additive_on_linked_book(self):
        system, desk, opt = self._linked_book()          # desk holds +100 of the option
        base_value = opt.MarketValue()
        with dag.scenario():
            opt.Rate.override(0.05)                       # +100bp absolute (0.04 -> 0.05)
            bumped_value = opt.MarketValue()
        expected_impact = 100 * (bumped_value - base_value)
        result = risk.stress(desk, rate_shock=0.01)
        assert result["applied_shocks"] == {"rate_shock": 0.01}
        assert result["pnl_impact"] == pytest.approx(expected_impact, abs=1e-6)

    def test_shared_instrument_not_compounded(self):
        """One instrument backing two symbols: a shock is applied once, not twice."""
        from lattice.trading import TradingSystem
        system = TradingSystem()
        desk = system.book("DESK"); client = system.book("C")
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0); opt.Volatility.set(0.20); opt.Rate.set(0.04)
        system.register_instrument("SYMA", opt)
        system.register_instrument("SYMB", opt)          # same instrument object, two symbols
        system.trade(desk, client, "SYMA", 10, opt.MarketValue())
        system.trade(desk, client, "SYMB", 10, opt.MarketValue())
        # desk now has two positions both linked to `opt`. Stress spot once.
        result = risk.stress(desk, spot_shock=0.10)
        with dag.scenario():
            opt.Spot.override(110.0)                      # a SINGLE override of the shared instrument
            single = desk.TotalPnL()
        # Without dedup, opt.Spot would be overridden twice (110 -> 121); dedup keeps it at 110.
        assert result["stressed_pnl"] == pytest.approx(single)
```

- [ ] **Step 2: Run to verify the new/updated tests fail**

Run: `python3 -m pytest tests/test_risk.py::TestMultiFactorStress tests/test_risk.py::TestPortfolioRisk -v`
Expected: FAIL — `stress() got an unexpected keyword argument 'vol_shock'` (and linked-book assertions fail).

- [ ] **Step 3: Rewrite `stress` for multi-factor + update `run_scenario`**

Replace the body of `stress` in `lattice/risk/portfolio.py` with:

```python
def stress(
    book: "Book",
    spot_shock: float = 0.0,
    vol_shock: float = 0.0,
    rate_shock: float = 0.0,
) -> dict:
    """Apply spot/vol/rate shocks to a book and return the P&L impact.

    For positions linked to a live instrument, the instrument's Spot/Volatility/
    Rate are overridden (each unique instrument once) and the book reprices
    reactively. For price-only positions, spot_shock moves MarketPrice; vol/rate
    have nothing to act on. Shocks that found nothing to act on are reported
    under ``skipped_shocks`` rather than silently dropped.

    Shock convention (see lattice.risk.shocks): spot/vol relative, rate absolute.
    """
    from .shocks import shocked_value

    base_pnl = book.TotalPnL()
    legs = {
        "spot_shock": ("Spot", spot_shock),
        "vol_shock": ("Volatility", vol_shock),
        "rate_shock": ("Rate", rate_shock),
    }
    applied: dict = {}
    skipped: dict = {}

    with dag.scenario():
        # Unique linked instruments + the price-only positions.
        instruments = []
        seen = set()
        unlinked = []
        for pos in book.Positions():
            inst = pos.LinkedInstrument()
            if inst is not None:
                if id(inst) not in seen:
                    seen.add(id(inst))
                    instruments.append(inst)
            else:
                unlinked.append(pos)

        for leg, (factor, shock) in legs.items():
            if shock == 0.0:
                continue
            acted = False
            for inst in instruments:
                if hasattr(inst, factor):
                    acc = getattr(inst, factor)
                    acc.override(shocked_value(factor, acc(), shock))
                    acted = True
            if factor == "Spot":
                for pos in unlinked:
                    pos.MarketPrice.override(
                        shocked_value("Spot", pos.MarketPrice(), shock)
                    )
                    acted = True
            (applied if acted else skipped)[leg] = shock

        stressed_pnl = book.TotalPnL()

    return {
        "base_pnl": base_pnl,
        "stressed_pnl": stressed_pnl,
        "pnl_impact": stressed_pnl - base_pnl,
        "spot_shock": spot_shock,
        "vol_shock": vol_shock,
        "rate_shock": rate_shock,
        "applied_shocks": applied,
        "skipped_shocks": skipped,
    }
```

In `lattice/risk/scenarios.py`, simplify `run_scenario` to pass all legs through
(the applied/skipped split now happens inside `stress`). Replace the body after
the `if scenario_name not in SCENARIOS:` guard with:

```python
    params = SCENARIOS[scenario_name]
    result = stress(book, **params)
    result["scenario"] = scenario_name
    return result
```

Delete the now-unused `_BOOK_APPLICABLE_SHOCKS` constant and the
`applied`/`skipped` computation that preceded the old `stress` call in
`run_scenario`.

Reconcile the `SCENARIOS` vol legs to the relative convention so each scenario's
intended end-state holds (only `vol_spike` and `vol_crush` change value):

```python
    "vol_spike": {
        "vol_shock": 0.50,    # +50% rel vol: 0.20 -> 0.30
    },
    "vol_crush": {
        "vol_shock": -0.25,   # -25% rel vol: 0.20 -> 0.15
    },
```

- [ ] **Step 4: Run to verify pass (and no regressions)**

Run: `python3 -m pytest tests/test_risk.py -v`
Expected: PASS — new multi-factor tests green; the existing
`test_run_scenario_reports_applied_and_skipped` and
`test_run_scenario_rate_only_is_zero_and_transparent` still pass (their fixture
book is unlinked, so spot applies and vol/rate skip exactly as before).

- [ ] **Step 5: Commit**

```bash
git add lattice/risk/portfolio.py lattice/risk/scenarios.py tests/test_risk.py
git commit -m "$(cat <<'EOF'
Multi-factor book stress for instrument-linked positions

stress() regains vol_shock/rate_shock: for linked positions it overrides each
unique instrument's Spot/Volatility/Rate (deduped to avoid compounding) and the
book reprices reactively; for price-only positions spot still moves MarketPrice
and vol/rate are reported as skipped. run_scenario passes all legs through.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Portfolio Greeks on Book

**Files:**
- Modify: `lattice/trading/book.py` (add Greeks computeds + helper, after `ShortExposure` ~line 122-125)
- Test: `tests/test_trading.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_trading.py`:

```python
class TestPortfolioGreeks:
    """Book.Delta/Vega/Gamma aggregate per-instrument sensitivities."""

    def test_book_delta_aggregates_linked_positions(self):
        import lattice.risk as risk
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0)
        opt.Volatility.set(0.20); opt.Rate.set(0.04)
        sys.register_instrument("OPT", opt)
        sys.trade(desk, client, "OPT", 10, opt.MarketValue())
        expected = 10 * risk.delta(opt)
        assert abs(desk.Delta() - expected) < 1e-6
        assert desk.Vega() != 0.0           # option has vega

    def test_unlinked_book_has_zero_greeks(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        sys.trade(desk, client, "AAPL", 100, 5.0)
        sys.set_market_price("AAPL", 5.5)
        assert desk.Delta() == 0.0
        assert desk.Vega() == 0.0

    def test_bond_contributes_no_delta_or_vega(self):
        from lattice import Bond
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        bond = Bond()
        bond.FaceValue.set(1000.0); bond.CouponRate.set(0.05)
        bond.YieldToMaturity.set(0.04); bond.Maturity.set(10)
        sys.register_instrument("UST", bond)
        sys.trade(desk, client, "UST", 5, bond.MarketValue())
        assert desk.Delta() == 0.0          # bond has no Spot
        assert desk.Vega() == 0.0           # bond has no Volatility
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_trading.py::TestPortfolioGreeks -v`
Expected: FAIL — `AttributeError: 'Book' object has no attribute 'Delta'`.

- [ ] **Step 3: Implement Book Greeks**

In `lattice/trading/book.py`, add a module-level constant near the top (after the imports):

```python
# Instrument input each Greek requires; positions whose instrument lacks it skip.
_GREEK_REQUIRES = {"delta": "Spot", "vega": "Volatility", "gamma": "Spot"}
```

Add these to the `Book` class (after `ShortExposure`):

```python
    @dag.computed
    def Delta(self) -> float:
        """Aggregate delta: sum of quantity * instrument delta over linked positions."""
        return self._book_greek("delta")

    @dag.computed
    def Vega(self) -> float:
        """Aggregate vega across linked positions."""
        return self._book_greek("vega")

    @dag.computed
    def Gamma(self) -> float:
        """Aggregate gamma across linked positions."""
        return self._book_greek("gamma")

    def _book_greek(self, name: str) -> float:
        """Quantity-weighted sum of a numerical Greek over linked positions.

        Positions with no linked instrument, or whose instrument lacks the
        required input (e.g. a bond has no Spot), contribute nothing.
        """
        from lattice.risk import sensitivities

        fn = getattr(sensitivities, name)
        required = _GREEK_REQUIRES[name]
        total = 0.0
        for pos in self.Positions():
            inst = pos.LinkedInstrument()
            if inst is None or not hasattr(inst, required):
                continue
            total += pos.Quantity() * fn(inst)
        return total
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_trading.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lattice/trading/book.py tests/test_trading.py
git commit -m "$(cat <<'EOF'
Add portfolio Greeks to Book

Book.Delta/Vega/Gamma sum quantity-weighted numerical sensitivities over
instrument-linked positions; positions whose instrument lacks the required
factor (e.g. a bond has no Spot/Volatility) contribute nothing.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Documentation + full verification

**Files:**
- Modify: `docs/api/trading.md`, `docs/api/risk.md`
- Verify: full test suite + a smoke test

- [ ] **Step 1: Update `docs/api/trading.md`**

In the `TradingSystem` Methods table, add a row:

```markdown
| `register_instrument(symbol, inst)` | Back a symbol with a live instrument (reactive pricing) |
```

In the `PositionTable`/`Position` area, add a short subsection after the Position docs:

```markdown
### Instrument-linked positions

A position can derive its value from a live instrument instead of a static
price. Register the instrument on the system; positions in that symbol reprice
reactively as the instrument's inputs change:

```python
opt = VanillaOption(); opt.Spot.set(100.0); opt.Strike.set(100.0)
system.register_instrument("AAPL_C_150", opt)
system.trade(desk, client, "AAPL_C_150", 10, opt.MarketValue())

opt.Spot.set(110.0)        # the position and book reprice automatically
desk.Delta()               # portfolio delta from the linked instrument
```

For a linked symbol, drive the market through the instrument's inputs;
`set_market_price` raises for linked symbols.
```

Add a `Book` Greeks note (in the Book section):

```markdown
| `Delta()` / `Vega()` / `Gamma()` | Portfolio Greeks (sum over instrument-linked positions) |
```

- [ ] **Step 2: Update `docs/api/risk.md`**

Replace the `risk.stress` signature and parameter table to reflect multi-factor:

```markdown
### `risk.stress(book, spot_shock=0.0, vol_shock=0.0, rate_shock=0.0)`

Apply spot/vol/rate shocks to a book and measure the P&L impact.

For positions linked to a live instrument, the shocks override the instrument's
`Spot`/`Volatility`/`Rate` and the book reprices reactively. For price-only
positions, only `spot_shock` applies (to `MarketPrice`); vol/rate are reported
under `skipped_shocks`.

**Shock convention:** `spot_shock` and `vol_shock` are relative (`× (1+s)`);
`rate_shock` is absolute (`+s`, i.e. basis points).

**Returns:** Dict with `base_pnl`, `stressed_pnl`, `pnl_impact`, `spot_shock`,
`vol_shock`, `rate_shock`, `applied_shocks`, `skipped_shocks`.
```

Update the `vol_spike` / `vol_crush` rows in the Available Scenarios table to
`+50% vol` and `-25% vol` respectively.

- [ ] **Step 3: Smoke-test the documented APIs**

Run this and confirm it prints `DOCS OK`:

```bash
python3 - <<'PY'
from lattice.trading import TradingSystem
from lattice import VanillaOption, risk
sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
opt = VanillaOption(); opt.Spot.set(100.0); opt.Strike.set(100.0); opt.Volatility.set(0.2); opt.Rate.set(0.04)
sys.register_instrument("AAPL", opt)
sys.trade(desk, client, "AAPL", 10, opt.MarketValue())
opt.Spot.set(110.0)
assert desk.Delta() != 0.0
r = risk.stress(desk, vol_shock=0.5)
assert r["applied_shocks"] == {"vol_shock": 0.5}
try:
    sys.set_market_price("AAPL", 5.0); raise SystemExit("should have raised")
except ValueError:
    pass
print("DOCS OK")
PY
```

Expected: `DOCS OK`.

- [ ] **Step 4: Run the full suite**

Run: `python3 -m pytest -q`
Expected: PASS (all tests, no regressions).

- [ ] **Step 5: Commit**

```bash
git add docs/api/trading.md docs/api/risk.md
git commit -m "$(cat <<'EOF'
Document instrument-linked positions, multi-factor stress, portfolio Greeks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done

After Task 6: the link, registry, multi-factor stress, portfolio Greeks, and the
unified shock convention are all implemented, tested, and documented. The
deferred follow-ons (book-level historical/Monte-Carlo VaR, persistence of
linked positions) remain out of scope.
