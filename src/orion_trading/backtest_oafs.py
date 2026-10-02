from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .features import calculate_features
from .models import Direction, Opportunity
from .mtf import align_completed_frames, build_context
from .oafs import OAFSConfig, generate_candidates
from .planner import build_plan
from .regime import classify_regime
from .risk import RiskConfig, RiskEngine

@dataclass(frozen=True)
class OAFSBacktestConfig:
    risk_fraction: float = 0.005
    reward_multiple: float = 2.0
    atr_stop_multiple: float = 1.5
    max_daily_loss_pct: float = 1.5
    max_consecutive_losses: int = 3
    conservative_same_bar: bool = True


def _stop(m15, direction, multiple):
    x = calculate_features(m15).dropna()
    last = x.iloc[-1]
    atr = float(last.atr14)
    if direction is Direction.LONG:
        return min(float(m15.low.iloc[-6:].min()), float(last.close) - atr * multiple)
    return max(float(m15.high.iloc[-6:].max()), float(last.close) + atr * multiple)


def _simulate(plan, future, conservative):
    for ts, row in future.iterrows():
        hi, lo = float(row.high), float(row.low)
        if plan.direction is Direction.LONG:
            stop_hit, target_hit = lo <= plan.stop, hi >= plan.target
        else:
            stop_hit, target_hit = hi >= plan.stop, lo <= plan.target
        if stop_hit and target_hit:
            return ts, plan.stop if conservative else plan.target, 'STOP_AND_TARGET_SAME_BAR'
        if stop_hit:
            return ts, plan.stop, 'STOP'
        if target_hit:
            return ts, plan.target, 'TARGET'
    return future.index[-1], float(future.close.iloc[-1]), 'END_OF_DATA'


def run_oafs_backtest(frames, instrument, config=None, start=None, end=None):
    cfg = config or OAFSBacktestConfig()
    risk = RiskEngine(RiskConfig(max_risk_per_trade_pct=cfg.risk_fraction * 100,
                                 max_daily_loss_pct=cfg.max_daily_loss_pct,
                                 max_consecutive_losses=cfg.max_consecutive_losses))
    m15 = frames['M15'].sort_index()
    if start is not None:
        s = pd.Timestamp(start); s = s.tz_localize('UTC') if s.tzinfo is None else s.tz_convert('UTC'); m15 = m15.loc[m15.index >= s]
    if end is not None:
        e = pd.Timestamp(end); e = e.tz_localize('UTC') if e.tzinfo is None else e.tz_convert('UTC'); m15 = m15.loc[m15.index < e]
    trades, rejects = [], []
    equity_r = peak_r = max_dd = 0.0
    consecutive_losses = 0
    daily_r = {}
    i = 0
    while i < len(m15):
        ts = m15.index[i]
        event_time = ts + pd.Timedelta(minutes=15)
        aligned = align_completed_frames(frames, event_time)
        if any(len(aligned[t]) < 100 for t in ('D','H4','H1','M15')):
            i += 1; continue
        regime, direction = classify_regime(aligned['H4'])
        context = build_context(aligned, regime, direction)
        candidates = generate_candidates(aligned, context, instrument, OAFSConfig())
        chosen = next((c for c in candidates if c.valid), None)
        if chosen is None:
            i += 1; continue
        entry = float(aligned['M15'].close.iloc[-1])
        stop = _stop(aligned['M15'], chosen.direction, cfg.atr_stop_multiple)
        if (chosen.direction is Direction.LONG and stop >= entry) or (chosen.direction is Direction.SHORT and stop <= entry):
            rejects.append({'time': ts.isoformat(), 'reason': 'INVALID_STOP'}); i += 1; continue
        day = ts.date()
        daily_loss_pct = max(0.0, -daily_r.get(day, 0.0) * cfg.risk_fraction * 100)
        decision = risk.approve(risk_pct=cfg.risk_fraction * 100, daily_loss_pct=daily_loss_pct,
                                consecutive_losses=consecutive_losses)
        if not decision.approved:
            rejects.append({'time': ts.isoformat(), 'reason': decision.reason}); i += 1; continue
        opportunity = chosen.opportunities[0] if chosen.opportunities else Opportunity.MOMENTUM
        plan = build_plan(instrument, chosen.direction, opportunity, entry, stop,
                          reward_multiple=cfg.reward_multiple, risk_fraction=cfg.risk_fraction)
        future = m15.iloc[i+1:]
        if future.empty: break
        exit_time, exit_price, reason = _simulate(plan, future, cfg.conservative_same_bar)
        distance = abs(plan.entry - plan.stop)
        pnl_r = ((exit_price-plan.entry)/distance if plan.direction is Direction.LONG else (plan.entry-exit_price)/distance)
        trades.append({'instrument':instrument,'direction':plan.direction.value,
                       'regime': context.regime.value,
                       'opportunities':[o.value for o in chosen.opportunities],
                       'entry_time':event_time,'exit_time':exit_time,'entry_price':plan.entry,
                       'exit_price':exit_price,'stop_price':plan.stop,'target_price':plan.target,
                       'pnl_r':float(pnl_r),'exit_reason':reason})
        equity_r += pnl_r; daily_r[day] = daily_r.get(day, 0.0) + pnl_r
        peak_r = max(peak_r, equity_r); max_dd = max(max_dd, peak_r-equity_r)
        consecutive_losses = consecutive_losses + 1 if pnl_r < 0 else 0
        i = m15.index.get_indexer([exit_time])[0] + 1
    wins = sum(t['pnl_r'] > 0 for t in trades)
    losses = sum(t['pnl_r'] < 0 for t in trades)
    gp = sum(t['pnl_r'] for t in trades if t['pnl_r'] > 0)
    gl = abs(sum(t['pnl_r'] for t in trades if t['pnl_r'] < 0))
    return {'instrument':instrument,'trades':len(trades),'wins':wins,'losses':losses,
            'win_rate_pct':wins/len(trades)*100 if trades else 0.0,'net_r':float(equity_r),
            'profit_factor':gp/gl if gl else None,'expectancy_r':equity_r/len(trades) if trades else 0.0,
            'max_drawdown_r':float(max_dd),'rejected_candidates':len(rejects),
            'trade_log':trades,'rejections':rejects}
