# ORION Adaptive Forex Strategy (OAFS) — V1.0

Status: Research specification — NOT approved for live trading.

## Objective
A regime-aware, multi-module FX strategy for the ORION trading system. It is designed to produce deterministic, backtestable trade candidates while allowing later research versions to improve parameters without bypassing hard risk controls.

## Instruments
Initial universe:
EUR_USD, GBP_USD, USD_JPY, USD_CHF, AUD_USD, USD_CAD, NZD_USD

Crosses are excluded from V1 until the major-pair system is validated.

## Timeframes
- D1: macro/regime context
- H4: primary structure and directional context
- H1: setup formation
- M15: entry confirmation
- Lower timeframes are not used for V1 signal generation.

## Core pipeline
SCAN -> REGIME -> BIAS -> OPPORTUNITY -> CONFIRMATION -> PLAN -> RISK -> EXECUTE -> MONITOR

A signal is a candidate, not an order. Risk Engine approval is mandatory.

---

## A. Data-derived features

For every timeframe ORION calculates:

### Structure
- swing highs/lows
- HH/HL/LH/LL
- break of structure (BOS)
- change of character / structure shift
- consolidation range
- recent high/low
- distance to higher-timeframe structure

### Volatility
- ATR(14)
- ATR percentile versus rolling history
- candle range relative to ATR
- volatility expansion/contraction

### Momentum
- RSI(14)
- rate of change
- directional candle persistence
- momentum acceleration/deceleration

RSI is confirmation only; fixed overbought/oversold rules do not create trades.

### Execution
- bid/ask spread
- spread relative to recent median
- available price/liquidity data
- observed slippage
- market-data freshness

---

# B. Market Regime

ORION classifies each pair into one primary regime:

1. TREND_UP
2. TREND_DOWN
3. RANGE
4. COMPRESSION
5. EXPANSION
6. TRANSITION
7. NEWS_SHOCK
8. PROTECTION

The regime classifier uses D1/H4 structure, directional persistence, volatility state and recent price behaviour.

No trade is allowed solely because a regime label is present.

## Regime restrictions

TREND_UP:
- prefer bullish pullback, continuation and momentum candidates
- bearish reversal requires exceptional confirmation

TREND_DOWN:
- prefer bearish pullback, continuation and momentum candidates
- bullish reversal requires exceptional confirmation

RANGE:
- breakout module may prepare for confirmed expansion
- mean-reversion is NOT a V1 standalone strategy
- avoid entries in the middle of the range

COMPRESSION:
- monitor breakout boundaries
- no entry before confirmed expansion

EXPANSION:
- breakout/momentum candidates permitted
- reject entries where price is already excessively extended from the breakout structure

TRANSITION:
- reversal candidates permitted only after structural confirmation
- continuation candidates require renewed trend evidence

NEWS_SHOCK:
- new entries blocked during the initial shock window unless a separately validated news strategy is enabled
- open trades are monitored under emergency rules

PROTECTION:
- no new trades
- existing trades managed conservatively

---

# C. Directional Bias

A directional bias is established only when higher-timeframe structure agrees.

Bullish bias:
- D1 is not structurally bearish
- H4 has bullish progression or confirmed bullish structure shift
- H4 price is not materially extended beyond the current structural regime

Bearish bias:
- D1 is not structurally bullish
- H4 has bearish progression or confirmed bearish structure shift
- H4 price is not materially extended beyond the current structural regime

If higher-timeframe evidence conflicts materially:
- BIAS = NEUTRAL
- no directional continuation trade

---

# D. Opportunity Module 1 — BREAKOUT

A breakout candidate requires:

1. A clearly defined H1/M15 consolidation or compression boundary.
2. At least two meaningful reactions defining the boundary.
3. Volatility was compressed or price range contracted before the break.
4. A completed candle closes beyond the boundary by a meaningful amount.
5. Break candle range is not an extreme outlier that indicates obvious exhaustion.
6. Momentum confirms the direction.
7. Spread remains within the execution threshold.
8. No prohibited news condition exists.
9. Risk Engine approves the resulting plan.

Preferred setup:
BREAK -> RETEST -> HOLD -> M15 confirmation.

Immediate-breakout entries may be tested separately and must not be assumed superior.

Invalidation:
- price returns through the broken structure and fails to hold it
- or structural stop is hit.

---

# E. Opportunity Module 2 — PULLBACK

A pullback candidate requires:

1. A valid H4 directional structure.
2. H1 structure remains consistent with that direction.
3. Price retraces toward a meaningful structural area.
4. Retracement does not invalidate the higher-timeframe thesis.
5. Price shows rejection, absorption or a lower-timeframe structure shift.
6. M15 momentum begins to align with the original direction.
7. Entry is not excessively far from the structural invalidation point.
8. Spread/news/execution conditions are acceptable.

Preferred sequence:
TREND -> RETRACEMENT -> LOCATION -> REACTION -> STRUCTURE SHIFT -> ENTRY.

A pullback in the middle of nowhere is not valid.

---

# F. Opportunity Module 3 — MOMENTUM

A momentum candidate requires:

1. Directional structure or a confirmed breakout.
2. Volatility expansion relative to recent conditions.
3. Directional price persistence.
4. Momentum confirmation.
5. No obvious exhaustion signature.
6. Entry occurs before the move becomes excessively extended relative to ATR.
7. News/execution conditions are acceptable.

Momentum entries are rejected when:
- the move is already statistically extended
- the entry is directly into major opposing higher-timeframe structure
- spread/liquidity is abnormal
- the move is an unconfirmed news spike.

---

# G. Opportunity Module 4 — TREND CONTINUATION

A continuation candidate requires:

1. Established H4 trend.
2. H1 pullback, pause or consolidation.
3. No higher-timeframe invalidation.
4. M15 continuation structure.
5. Momentum recovery in trend direction.
6. Price has room toward the next meaningful opposing structure.
7. Execution and risk conditions pass.

Typical pattern:
TREND -> PAUSE/PULLBACK -> STRUCTURE HOLDS -> MOMENTUM RECOVERS -> CONTINUATION.

Continuation is allowed to combine with PULLBACK and MOMENTUM.

---

# H. Opportunity Module 5 — REVERSAL

Reversal has the strictest requirements.

Required sequence:

1. Price reaches a meaningful higher-timeframe extreme/structure area.
2. Evidence of extension or failed continuation.
3. Liquidity sweep or comparable failed-break behaviour where observable.
4. Failure to maintain the new extreme.
5. Confirmed M15/H1 structure shift.
6. Momentum reversal confirms.
7. There is sufficient room to the first meaningful target.
8. News/fundamental conditions do not create an obvious contradiction.
9. Risk Engine approves.

A reversal is rejected if it is based only on:
- RSI overbought/oversold
- one large candle
- subjective support/resistance
- "price has moved too far."

---

# I. Confluence / Signal Decision

Opportunity modules are allowed to overlap.

Example:
TREND_CONTINUATION + PULLBACK + MOMENTUM

The Signal Engine creates a structured candidate containing:
- opportunity types
- regime
- direction
- evidence
- invalidation
- entry zone
- stop candidate
- target candidates
- news state
- execution state
- confidence metadata

V1 does NOT use an arbitrary 0-100 score as the sole decision mechanism.

Instead, critical conditions are gates:
- structural validity
- execution validity
- news validity
- risk validity

Additional evidence is recorded for research and later statistical weighting.

---

# J. Entry Model

Entries are triggered only after the setup has completed its required confirmation sequence.

Preferred entry:
- confirmation candle close on M15
- or a tested limit/retest model when the module explicitly supports it.

No entry is triggered merely because price touches a level.

If the entry becomes materially extended before execution:
- candidate expires
- ORION waits for a new setup.

---

# K. Stop Loss

Stop placement is structural first, volatility second.

For a long:
- below the structural invalidation area
- with an ATR-based minimum buffer

For a short:
- above the structural invalidation area
- with an ATR-based minimum buffer

Stop distance must pass:
- minimum execution distance
- maximum strategy distance
- account risk calculation
- broker/instrument constraints

The stop is determined BEFORE position size.

---

# L. Target / Exit Framework

V1 records multiple possible exit methods for research:

1. opposing structure
2. volatility projection
3. fixed R multiple
4. trailing structure
5. momentum exhaustion
6. time-based exit

The backtest engine compares these methods.

Live V1 must use one explicitly selected, versioned exit model rather than dynamically choosing whichever would have looked best historically.

---

# M. Open Trade Re-evaluation

Every open trade retains its original thesis.

At each monitoring cycle ORION evaluates:

- thesis strength
- current regime
- structure
- momentum
- volatility
- news
- spread
- correlation/exposure
- distance to invalidation
- progress toward target
- time in trade

States:
OPEN -> STRENGTHENING / STABLE / WEAKENING / INVALIDATED

Possible actions are constrained by the Plan + Risk Engine:
- HOLD
- REDUCE
- MOVE_STOP
- TAKE_PARTIAL
- CLOSE

ORION must not move a stop farther away from the original risk boundary unless a future tested strategy version explicitly permits it.

---

# N. News Rules

Scheduled high-impact events create a configurable restricted window.

V1 default research parameters:
- pre-event restriction: 15 minutes
- post-event shock restriction: 15 minutes
- emergency shock detection can extend the restriction automatically

These are research defaults, not proven optimal values.

News handling:
1. identify event
2. identify affected currency
3. compare expected vs actual when available
4. measure immediate reaction
5. measure follow-through
6. detect structural change
7. classify NORMAL / EVENT / NEWS_SHOCK

ORION does not trade the headline alone.

---

# O. Correlation / Currency Exposure

Risk Engine tracks exposure by currency, not just by pair.

Example:
EUR/USD BUY + GBP/USD BUY + USD/CHF SELL

These may represent a large implicit USD-short exposure.

ORION therefore calculates:
- pair exposure
- base-currency exposure
- quote-currency exposure
- correlated-position exposure

A technically valid trade can still be rejected because portfolio exposure is already too concentrated.

---

# P. Hard Risk Rules

Strategy V1 assumes configurable limits.

Initial research defaults:
- risk per trade: 0.50% maximum
- daily loss limit: 1.50%
- maximum consecutive losses: 3
- new-trade drawdown protection: enabled
- maximum correlated exposure: configurable
- spread filter: enabled
- slippage filter: enabled
- news filter: enabled
- emergency shutdown: enabled

These values are configuration, not claims of optimality.

Risk Engine has final authority.

No model, strategy module, learning system or news model may bypass it.

---

# Q. Trade Quality Research

Every candidate, including rejected candidates, should be logged.

Store:
- pair
- timestamp
- regime
- opportunity modules
- direction
- feature values
- news state
- spread
- planned entry/stop/target
- risk decision
- rejection reason
- eventual market outcome

This allows ORION to study:
- which conditions actually predict outcomes
- which filters remove good trades
- which filters remove bad trades
- regime-specific performance
- pair-specific behaviour
- session behaviour
- news behaviour

---

# R. Learning Rules

The live system does NOT self-modify its strategy from a single trade or short sample.

Learning workflow:

LIVE DATA
-> PERFORMANCE DATA
-> HYPOTHESIS
-> BACKTEST
-> OUT-OF-SAMPLE TEST
-> WALK-FORWARD TEST
-> COST/SLIPPAGE TEST
-> MONTE CARLO
-> VERSION COMPARISON
-> APPROVAL
-> DEPLOY NEW VERSION

Every live strategy has:
- version
- parameter set
- deployment timestamp
- test dataset
- validation results
- rollback version

---

# S. Research Standards

A strategy version is not promoted because it has a high backtest return.

Promotion requires review of:
- expectancy
- profit factor
- drawdown
- return distribution
- win/loss distribution
- trade count
- stability across periods
- stability across pairs
- stability across regimes
- sensitivity to parameter changes
- spread/commission/slippage impact
- out-of-sample results
- walk-forward results
- Monte Carlo drawdown
- failure modes

No guarantee of profitability is assumed.

---

# T. Safety State Machine

SYSTEM NORMAL
-> NEWS RESTRICTION
-> NEWS SHOCK
-> PROTECTION
-> RECOVERY
-> NORMAL

Protection can be triggered by:
- daily loss limit
- drawdown limit
- data-feed failure
- execution failure
- abnormal spread
- broker/API outage
- model inconsistency
- unexpected position state

In PROTECTION:
- no new trades
- existing trades remain governed by deterministic risk rules
- alerts are generated
- recovery requires explicit conditions.

---

## V1 Design Principle

The strategy is not "buy when indicators agree."

It is:

MARKET REGIME
+ STRUCTURE
+ OPPORTUNITY
+ LOCATION
+ CONFIRMATION
+ FUNDAMENTAL/NEWS CONTEXT
+ EXECUTION QUALITY
+ POSITIVE TESTED EXPECTANCY
+ RISK APPROVAL

Only then can a trade be executed.
