from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def _find_files(root: Path):
    return {p.name: p for p in root.rglob('*') if p.is_file()}

def _pick_number(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None

def build_report(root: Path) -> str:
    files = _find_files(root)
    summary_path = files.get('summary.json')
    summary = _load_json(summary_path) if summary_path else None
    lines = ['# ORION Research Analysis', '', 'This report is generated automatically after the research workflow completes.', '']
    if not summary:
        lines += ['## Status', '', 'No summary.json was found in the research artifact.', 'The raw artifact should be inspected before drawing conclusions.', '']
        return '\n'.join(lines)
    portfolio = summary.get('portfolio', summary) if isinstance(summary, dict) else {}
    lines += ['## Portfolio', '']
    for label, keys in [('Initial equity', ('initial_equity',)), ('Final equity', ('final_equity',)), ('Return %', ('total_return_pct', 'return_pct', 'net_return_pct')), ('Max drawdown %', ('max_drawdown_pct', 'drawdown_pct')), ('Trades', ('trades', 'total_trades')), ('Win rate %', ('win_rate_pct', 'win_rate')), ('Profit factor', ('profit_factor',)), ('Expectancy', ('expectancy',))]:
        value = _pick_number(portfolio, *keys)
        if value is not None:
            lines.append(f'- {label}: {value:g}')
    status = summary.get('status') if isinstance(summary, dict) else None
    live = summary.get('live_trading_enabled') if isinstance(summary, dict) else None
    if status is not None or live is not None:
        lines += ['', '## Safety state', '']
        if status is not None:
            lines.append(f'- Research status: {status}')
        if live is not None:
            lines.append(f'- Live trading enabled: {live}')
    csvs = {}
    for name, path in files.items():
        if path.suffix.lower() == '.csv':
            try:
                csvs[name] = pd.read_csv(path)
            except Exception:
                pass
    lines += ['', '## Available datasets', '']
    if csvs:
        for name, frame in sorted(csvs.items()):
            lines.append(f'- {name} — {len(frame):,} rows, {len(frame.columns)} columns')
    else:
        lines.append('- No CSV datasets found.')
    lines += ['', '## Automated interpretation', '', '- These figures are descriptive results from the completed research run.', '- They are not evidence of guaranteed future profitability.', '- Walk-forward and out-of-sample results should be prioritized over full-sample results when available.', '- Before paper trading, inspect drawdown, trade count, profit factor, expectancy, and performance stability across markets/regimes.', '', '## Next gate', '', '1. Inspect the research artifact.', '2. Compare in-sample and out-of-sample behavior.', '3. Reject unstable configurations rather than optimizing for a single headline return.', '4. Only then promote the strategy into paper-trading evaluation.']
    return '\n'.join(lines) + '\n'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='research-artifact')
    parser.add_argument('--output', default='research-analysis')
    args = parser.parse_args()
    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    report = build_report(root)
    (out / 'research_analysis.md').write_text(report)
    print(report)

if __name__ == '__main__':
    main()
