import pandas as pd
from orion_trading.data_quality import validate_candles

def test_valid_candles_pass():
    idx = pd.date_range("2026-01-01", periods=4, freq="15min", tz="UTC")
    df = pd.DataFrame({"open":[1,2,3,4],"high":[2,3,4,5],"low":[0,1,2,3],"close":[1.5,2.5,3.5,4.5]}, index=idx)
    report = validate_candles(df, "M15")
    assert report.passed
    assert report.missing_bars == 0

def test_gap_is_reported():
    idx = pd.DatetimeIndex(["2026-01-01T00:00:00Z","2026-01-01T00:30:00Z"])
    df = pd.DataFrame({"open":[1,2],"high":[2,3],"low":[0,1],"close":[1.5,2.5]}, index=idx)
    assert validate_candles(df, "M15").missing_bars == 1
