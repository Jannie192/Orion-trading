from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class BacktestResult:
    trades: int
    pnl_r: float
    win_rate: float
    max_drawdown_r: float

class Backtester:
    """Deterministic result calculator for already-generated trades."""
    def run(self, trades: pd.DataFrame) -> BacktestResult:
        if trades.empty:
            return BacktestResult(0, 0.0, 0.0, 0.0)
        pnl = trades["pnl_r"].astype(float)
        equity = pnl.cumsum()
        drawdown = equity - equity.cummax()
        return BacktestResult(len(pnl), float(pnl.sum()), float((pnl > 0).mean()), float(abs(drawdown.min())))
