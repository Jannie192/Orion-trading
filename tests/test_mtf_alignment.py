import pandas as pd

from orion_trading.mtf import align_completed_frames


def _frame(start, periods, freq):
    idx = pd.date_range(start, periods=periods, freq=freq, tz='UTC')
    return pd.DataFrame({'open':1.0,'high':2.0,'low':0.0,'close':1.0}, index=idx)


def test_higher_timeframes_only_use_completed_bars():
    frames = {
        'D': _frame('2026-01-01', 3, '1D'),
        'H4': _frame('2026-01-01', 6, '4h'),
        'H1': _frame('2026-01-01', 24, '1h'),
        'M15': _frame('2026-01-01 00:00', 16, '15min'),
    }
    event = pd.Timestamp('2026-01-01 03:15', tz='UTC')
    aligned = align_completed_frames(frames, event)
    assert aligned['M15'].index[-1] == pd.Timestamp('2026-01-01 03:00', tz='UTC')
    assert aligned['H1'].index[-1] == pd.Timestamp('2026-01-01 02:00', tz='UTC')
    assert aligned['H4'].empty
    assert aligned['D'].empty
