# Positions ↔ Instruments Link — Design

**Date:** 2026-05-30
**Status:** Approved (pending spec review)
**Author:** Abhishek Gulati (with Claude)

## Context

The trading layer today models market data as `symbol → scalar price`
(`TradingSystem._market_prices: Dict[str, float]`, pushed to positions via
`set_market_price`). A `Position` holds a dead number (`MarketPrice`), not a
live instrument, and a `Book`'s P&L is `Σ Quantity × MarketPrice`.

This is the root cause of several limitations:

- **Book stress is price-only.** `risk.stress(book, spot_shock=0.0)` can only
  shock price; a book has no volatility or rate sensitivity by construction.
  The `applied_shocks` / `skipped_shocks` reporting added earlier is an honest
  *symptom* of this, not a desired design.
- **No portfolio Greeks.** Delta/Vega/Gamma exist only per-instrument via
  `RiskEngine`, never aggregated to a book.
- **Book-level simulation VaR is impossible** — you cannot reprice a book under
  a new market state.

Linking each `Position` to a live `Instrument` (option, bond, …) so its value
derives reactively from the instrument's own pricing defuses all three at once:
override an instrument's factor inside a `dag.scenario()`, the position
reprices, the book reprices — multi-factor stress and portfolio Greeks fall out
of dag's cross-model dependency tracking.

## Goals

1. A `Position` can optionally reference a live `Instrument`; when linked, its
   value derives reactively from `instrument.MarketValue()`.
2. Book-level stress genuinely applies spot **and** volatility/rate shocks by
   overriding the linked instruments' factors.
3. Book-level Greeks: `Book.Delta()`, `Book.Vega()`, `Book.Gamma()` aggregate
   per-instrument sensitivities across positions.
4. A coherent shock convention shared by book stress and instrument stress,
   resolving the existing absolute-vs-relative inconsistency.

## Non-Goals (v1)

- Persistence of linked positions (storing the instrument by Store path). The
  registry holds live in-memory objects; `TradingSystem` is in-memory today.
- Historical / Monte-Carlo VaR (a separate deferred fork; portfolio Greeks is
  its stepping stone).
- Changing the parametric VaR in `risk/var.py`.

## Backward Compatibility (hard constraint)

The existing price-only flow must keep working unchanged: `PositionTable.add`,
`system.trade(...)` + `system.set_market_price(symbol, scalar)`, and every
current test and example. Instrument-linking is **additive and opt-in**: a
position with no linked instrument behaves exactly as today.

## Verified Assumptions

Both load-bearing mechanisms were confirmed against the current dag build
before this design was accepted:

1. **Cross-model reactivity:** a model whose computed calls
   `instrument.MarketValue()` reprices when the instrument's `Spot`/`Volatility`
   is overridden in a `dag.scenario()`, and reverts on exit.
2. **Dynamic linking via an Input node:** modelling the link as
   `dag.Input | dag.Optional` means `pos.LinkedInstrument.set(inst)` invalidates
   dependents, so linking a position *after* it has already been valued
   recomputes correctly; `set(None)` reverts to the fallback price.

## Design

### Component 1 — `Position` (lattice/trading/position.py)

Add two computed nodes; leave `MarketPrice` (Input | Overridable) untouched.

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
```

`MarketValue` changes from `Quantity() * MarketPrice()` to
`Quantity() * EffectivePrice()`. For an unlinked position
`EffectivePrice() == MarketPrice()`, so behavior is identical to today.
`UnrealizedPnL` (= `MarketValue - Quantity*AvgPrice`) is unchanged.

Dimensional note: `instrument.MarketValue()` is the per-unit value (e.g. an
option's premium), so `Position.MarketValue = Quantity × instrument.MarketValue()`
is the correct total position value.

### Component 2 — `TradingSystem` registry (lattice/trading/system.py)

```python
self._instruments: Dict[str, Instrument] = {}   # symbol -> live instrument

def register_instrument(self, symbol: str, instrument: Instrument) -> None:
    """Back a symbol with a live instrument; link existing + future positions."""
    self._instruments[symbol] = instrument
    for (book_id, sym), pos in self._positions.items():
        if sym == symbol:
            pos.LinkedInstrument.set(instrument)

def get_instrument(self, symbol: str) -> Optional[Instrument]:
    return self._instruments.get(symbol)
```

- `_update_position` links a newly created position when its symbol is already
  registered (`pos.LinkedInstrument.set(self._instruments[symbol])`).
- `set_market_price(symbol, price)` **raises** `ValueError` when `symbol` is
  instrument-linked, with a message directing the caller to drive the
  instrument's inputs instead (e.g. `instrument.Spot.set(...)`). Fail-loud, not
  silently-ignored.

A registered symbol is driven by mutating the instrument's inputs; a
non-registered symbol continues to use `set_market_price` exactly as today.

### Component 3 — Multi-factor stress (lattice/risk/portfolio.py)

`stress` regains volatility and rate shocks — legitimate now that a linked book
can absorb them:

```python
def stress(book, spot_shock=0.0, vol_shock=0.0, rate_shock=0.0) -> dict:
    ...
```

Inside one `dag.scenario()`:

- **Linked positions:** collect the *unique* instruments across the book's
  linked positions (a symbol maps to one shared instrument, so two positions in
  the same name share it). Override each unique instrument's factors **once** —
  `Spot` by `spot_shock`, `Volatility` by `vol_shock`, `Rate` by `rate_shock`
  (using the shock convention below). Deduplicating is essential: overriding a
  shared instrument per-position would compound the shock. Factors an instrument
  lacks are skipped.
- **Unlinked positions:** apply `spot_shock` to each position's `MarketPrice`
  (today's behavior); `vol_shock`/`rate_shock` have nothing to act on and are
  reported as skipped.

The result dict retains `base_pnl`, `stressed_pnl`, `pnl_impact`, the applied
shocks, and (for transparency on mixed/price-only books) any shocks that found
nothing to act on. For a fully-linked book, nothing is skipped — Area A's
`skipped_shocks` collapses naturally.

`run_scenario` (lattice/risk/scenarios.py) passes the full scenario legs through
to `stress`; on a fully-linked book every leg now applies.

### Component 4 — Portfolio Greeks (lattice/trading/book.py)

```python
@dag.computed
def Delta(self) -> float:
    return self._book_greek("delta")   # Σ Quantity_i * risk.delta(instrument_i)
```

`Book.Delta()`, `Book.Vega()`, `Book.Gamma()` sum `Quantity_i × risk.<greek>(inst_i)`
over linked positions whose instrument exposes the relevant factor (reusing the
existing `lattice.risk.sensitivities` numerical functions). Unlinked positions
contribute nothing. Positions whose instrument lacks a factor are skipped (a
bond contributes to neither Delta nor Vega).

### Shock convention (resolves the latent absolute-vs-relative bug)

Today `engine.stress_test` and the Temporal `compute_stress_test` apply *every*
shock as `value * (1 + shock)` (relative), but the `SCENARIOS` catalog encodes
some legs as absolute (`rate_hike` = "+100bp", `vol_spike` = "+10% vol
absolute"). Confirmed mismatch: a `+10%` vol shock on 0.20 yields 0.22, not the
intended 0.30; `+100bp` on 0.04 yields 0.0404, not 0.05.

This feature defines one convention, applied everywhere shocks are interpreted
(book stress, `engine.stress_test`, the Temporal activity):

| Factor | Semantics | Example |
|--------|-----------|---------|
| `spot_shock` | relative: `Spot * (1 + s)` | `-0.20` = −20% |
| `vol_shock`  | relative: `Vol * (1 + s)`  | `+0.50` = +50% (0.20 → 0.30) |
| `rate_shock` | absolute: `Rate + s`       | `+0.01` = +100bp (0.04 → 0.05) |

`SCENARIOS` values are reconciled so each scenario's **intended end state**
(the market move described in its comment) is preserved under this convention.
For example `vol_spike` ("+10 vol points: 0.20 → 0.30") becomes a relative
`vol_shock` of `+0.50`; `rate_hike` ("+100bp") stays `rate_shock = 0.01` under
the absolute rule. Existing tests assert only spot-driven `pnl_impact`, so
reconciling the vol/rate legs does not change any currently-tested behavior;
the new values become live only for instrument-linked books.

## Data Flow

```
register_instrument(symbol, inst)
        │  links positions for symbol  →  pos.LinkedInstrument.set(inst)
        ▼
move the market:  inst.Spot.set(...)   (or scenario override during stress)
        │   dag invalidation
        ▼
pos.EffectivePrice() → inst.MarketValue()  →  pos.MarketValue → pos.UnrealizedPnL
        ▼
book.TotalPnL() / book.Delta() / book.Vega()   (all reactive)
```

## Error Handling

- `set_market_price` on a linked symbol → `ValueError` with guidance.
- Stress / Greeks: a linked position whose instrument lacks a shocked/queried
  factor is skipped, never errored.
- An unlinked position under `vol_shock`/`rate_shock`: the shock is reported as
  finding nothing to act on, not silently dropped.

## Testing Strategy (TDD)

1. Unlinked position: `MarketValue`/`UnrealizedPnL` identical to today (regression).
2. Linking a position reprices it from the instrument; `set(None)` reverts.
3. Dynamic link after the position has already been valued recomputes correctly.
4. Multi-factor book stress: a linked book moves on `vol_shock` and `rate_shock`,
   not just `spot_shock`; values match direct instrument revaluation.
5. Mixed linked/unlinked book: linked positions absorb vol/rate, unlinked report
   them as skipped.
5b. Shared instrument: two positions in the same symbol share one instrument; a
   stress shock is applied once, not compounded.
6. `set_market_price` raises on a linked symbol.
7. Portfolio Greeks: `Book.Delta/Vega/Gamma` equal the quantity-weighted sum of
   instrument sensitivities; bonds contribute to neither Delta nor Vega.
8. Shock convention: `rate_shock` is additive (bp), `vol_shock` multiplicative;
   `engine.stress_test` and the Temporal activity agree.
9. Scenario reversion: instrument inputs restored after stress.

## File Touch List

- `lattice/trading/position.py` — `LinkedInstrument`, `EffectivePrice`, `MarketValue`
- `lattice/trading/system.py` — registry, `register_instrument`, link wiring, `set_market_price` guard
- `lattice/trading/book.py` — `Delta`/`Vega`/`Gamma` + `_book_greek` helper
- `lattice/risk/portfolio.py` — multi-factor `stress`
- `lattice/risk/scenarios.py` — reconcile `SCENARIOS` to the shock convention; `run_scenario` passthrough
- `lattice/risk/engine.py` — `stress_test` shock convention
- `lattice/workflows/activities.py` — `compute_stress_test` shock convention
- `tests/test_trading.py`, `tests/test_risk.py` — new tests per the strategy above
- `docs/api/trading.md`, `docs/api/risk.md` — document the link, registry, multi-factor stress, portfolio Greeks
