# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ccQuant is an option-focused quantitative backtesting platform with a Web UI. It is built on top of the VeighNa (vnpy) 4.3.0 event-driven architecture but rewritten for option strategies (multi-leg, Greeks, multi-expiry).

- **Backend**: Python 3.10+ with FastAPI, SQLAlchemy (SQLite), and a vnpy-style event-driven backtest engine.
- **Frontend**: React 19 + TypeScript + Vite 8 + ECharts 6. Runs on port 3000 (dev) and proxies `/api` to the backend on port 8080.
- **Database**: SQLite at `~/.ccquant/ccquant.db`, auto-created on first backend start.

The repository also contains two research subprojects that feed into the main platform:
- `IV_Predict/` — Original XGBoost + B-Spline research code.
- `strategy/` — Adapted IV Predict strategies (A/B/C) with a data pipeline that bridges into ccQuant.

---

## Common Commands

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start FastAPI server (port 8080)
python -m ccquant.ui.server

# Import 50ETF option CSV into SQLite
python import_50etf.py
```

### Frontend
```bash
cd ccquant-web
npm install
npm run dev          # Dev server on http://localhost:3000
```

**Production build note**: `npm run build` runs `tsc -b && vite build`. If pre-existing TypeScript errors block the build, use `npx vite build` directly (skips type checking). The backend automatically serves `ccquant-web/dist/` as static files.

### Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_backtest_engine.py -v
python -m pytest tests/test_option_core.py -v
```

---

## High-Level Architecture

### Backend (ccquant/)

**FastAPI Server** (`ccquant/ui/server.py`):
- All REST API routes are defined in this single file (~2400 lines).
- Serves the frontend static files from `ccquant-web/dist/` when built.
- Database API (`/api/data/*`): underlyings, contracts, option bars, daily bars, CSV upload.
- Visualization API (`/api/viz/*`): volatility smile/surface, option chain, market overview.
- Strategy API (`/api/strategies/*`): list strategies, read/write code, open in IDE.
- Backtest API (`/api/backtest/run`, `/api/backtest/optimize`, `/api/backtest/history`).

**Backtest Engine** (`ccquant/backtest/engine.py`):
- `BacktestingEngine` follows the vnpy lifecycle: `set_parameters()` → `add_strategy()` → `load_data()` → `run_backtesting()` → `calculate_result()` → `calculate_statistics()`.
- Supports **per-contract settings**: `rates`, `slippages`, `sizes`, `priceticks` are all `dict[str, float]` keyed by `vt_symbol`.
- Data sources: SQLite via `load_bar_data()` (default), or direct `bars_dict` injection (used by IV Predict strategies to bypass the database).
- Daily mark-to-market P&L with `PortfolioDailyResult`.
- Parameter optimization: brute-force (multiprocessing) and genetic algorithm via `OptimizationSetting` in `ccquant/backtest/optimization.py`.

**Strategy Template** (`ccquant/backtest/template.py`):
- Base class: `StrategyTemplate`.
- Lifecycle: `on_init()` → `on_start()` → `on_bars(bars: dict[str, BarData])` → `on_stop()`.
- Trading helpers: `buy()`, `sell()`, `short()`, `cover()`, `set_target()`, `rebalance_portfolio()`.
- Parameters can be defined as either:
  1. vnpy-style list of strings: `parameters = ["param1", "param2"]`
  2. UI metadata list of dicts: `parameters = [{"name": "param1", "displayName": "...", "type": "number", "default": 0}]`

**Strategy Registry** (`ccquant/strategy/template.py`):
- All strategies must be registered in `get_strategy_class(strategy_name: str)` to be selectable from the frontend.
- Currently registered: option examples (BuyCall, Straddle, IronCondor, spreads), CTA strategies (AtrRsi, BollChannel, etc.), and IV Predict variants (IvPredictStrategy, A, B, C).

**Database** (`ccquant/database.py`):
- SQLAlchemy ORM with `DatabaseManager` singleton (`db`).
- Key tables: `underlyings`, `option_contracts`, `option_daily_bars`, `daily_bars`, `risk_free_rates`, `backtest_records`.
- `db.get_session()` yields a SQLAlchemy session context manager.

### Frontend (ccquant-web/)

**Key files**:
- `src/App.tsx` — Router with 4 pages: Database, Visualization, StrategyEditor, Backtest.
- `src/api.ts` — Axios wrappers for all backend APIs.
- `src/types.ts` — Shared TypeScript interfaces.
- `vite.config.ts` — Proxy `/api` → `http://127.0.0.1:8080`.

**Strategy Params Form** (`src/components/StrategyParamsForm.tsx`):
- `STRATEGY_DEFINITIONS` declares UI metadata for each strategy (parameters, types, defaults).
- `STRATEGY_CATEGORIES` groups strategies into: `single_single` (单标的单合约), `single_multi` (单标的多合约), `multi_multi` (多标的多合约).
- When adding a new strategy, it must be added to both `STRATEGY_DEFINITIONS` and the appropriate category.

### IV Predict Integration (strategy/)

This subproject contains the XGBoost + B-Spline research code adapted for ccQuant backtesting.

**Data Pipeline** (`strategy/src/core/data_loader.py`):
- `prepare_backtest_data(data_dir, model_path)` is the one-stop entry point.
- Loads raw CSV (`strategy/data/raw/50etf_options.csv`), forward table, and B-Spline cache.
- `mw_checkpoint_v2.pkl` (in `strategy/data/output/two_step_v2/`) contains pre-computed B-Spline fits (`baseline_iv`, `residual_iv`) and the `daily_mw_data` spline dictionary. This file is ~108MB and loading it avoids re-fitting splines on every run.
- `forward_table.csv` (in `strategy/data/output/two_step_v2/`) contains Put-Call Parity implied forwards.
- `model_abs_iv.pkl` (in `strategy/data/output/baseline_xgb/`) is the XGBoost model used by Strategy A. It expects exactly 26 features defined in `FEATURE_COLS`.
- Returns a dict with `bars_dict`, `daily_groups`, `daily_mw_data`, `forward_table`, `xgb_model`, `feature_cols`.

**Signal Modules** (`strategy/src/strategies/`):
- `strategy_a_residual.py` — XGBoost predicts T+1 absolute IV, subtracts B-Spline baseline → residual signal. Long/Short: pred_residual < 0 → Long, > 0 → Short.
- `strategy_b_section.py` — Pure B-Spline section logic. `residual_zscore` by maturity bucket, threshold + rank.
- `strategy_c_doublesort.py` — Stricter threshold (1.5 vs 1.0) section sort with liquidity filter. No XGBoost direction filtering (deprecated in v3).

**Bridge** (`ccquant/strategy/iv_predict.py`):
- `IvPredictStrategy` wraps A/B/C into a single `StrategyTemplate`. `strategy_type` parameter selects A/B/C.
- Uses a class-level `_data_cache` dict to avoid reloading the 108MB B-Spline cache across optimization iterations.
- `model_path` and `data_dir` are configurable parameters defaulting to the `strategy/data/` paths.

**Server-side Data Injection** (`ccquant/ui/server.py`):
- `_get_ivpredict_bars_and_symbols()` detects when the chosen strategy is `IvPredict*` and loads data via `prepare_backtest_data()` instead of querying the SQLite database.
- For parameter optimization, `bars_dict` is passed through `evaluate()` / `wrap_evaluate()` to each worker process so data is loaded once by the parent and injected into children.

---

## Important Patterns

### Adding a New Strategy
1. Create the strategy class inheriting from `StrategyTemplate` (or `OptionStrategyTemplate`).
2. Add it to `get_strategy_class()` in `ccquant/strategy/template.py`.
3. Add its parameter metadata to `STRATEGY_DEFINITIONS` in `ccquant-web/src/components/StrategyParamsForm.tsx`.
4. Add it to the correct `STRATEGY_CATEGORIES` bucket.
5. If it needs external data injection (like IV Predict), add a branch in `_get_ivpredict_bars_and_symbols()` or similar in `server.py`.

### Data Import Workflow
- Raw 50ETF option CSV → `import_50etf.py` → SQLite (`~/.ccquant/ccquant.db`).
- Alternative: use the frontend Database page to upload CSVs directly.
- The visualization and backtest pages read from SQLite. Only IV Predict strategies read from the `strategy/data/` pipeline.

### Backtest Result Flow
1. Frontend POST `/api/backtest/run` with `BacktestRequest`.
2. Server resolves `vt_symbols` (from database or IV Predict pipeline).
3. `BacktestingEngine` loads data → runs backtest → `calculate_result()` returns a DataFrame → `calculate_statistics()` returns a dict.
4. Server returns JSON with `statistics`, `trades`, `daily_results`, and `logs`.
5. Frontend renders: equity curve (ECharts), statistics table, trade log table.
