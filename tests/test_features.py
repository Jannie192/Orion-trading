import pandas as pd

from orion_trading.features import calculate_features


def test_feature_pipeline_adds_core_features():
    close = [1 + i * 0.001 for i in range(80)]
    df = pd.DataFrame({"high": [x+0.001 for x in close], "low": [x-0.001 for x in close], "close": close})
    out = calculate_features(df)
    for column in ["atr14", "rsi14", "roc10", "ema20", "ema50"]:
        assert column in out.columns
    assert out["ema50"].notna().any()
