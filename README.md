# ccQuant 期权策略回测平台

**ccQuant** 是一个专门为期权策略研发和回测设计的量化平台，基于 VeighNa (vnpy) 4.3.0 的核心架构（事件驱动、Bar/Tick 回测引擎、高性能图表缓存）进行重新开发。目标是在保留底层回测思想的基础上，针对期权场景（多到期日、多行权价、希腊字母、组合盈亏）提供完整支持，并配备现代化、浅色系的 Web UI。

---

## 项目状态（截至当前会话）

- ✅ **Phase 1 完成**：项目结构、`core/` 基础模块（EventEngine、数据类、常量、工具类、数据库接口、Gateway 抽象）
- ✅ **Phase 2 完成**：`option/` 核心模块（期权链 `OptionChain`、B-S 定价 `pricing.py`、Greeks `greeks.py`、多腿组合 `portfolio.py`、盈亏图 `payoff.py`）
- ✅ **Phase 3 完成**：`backtest/` 回测引擎（撮合器 `matcher.py`、回测引擎 `engine.py`、记录器 `recorder.py`、结果统计 `result.py`）、策略基类 `strategy/template.py`
- ✅ **Phase 4 完成**：
  - FastAPI 服务端 `ui/server.py`（支持真实数据加载、标的切换）
  - React + Vite + ECharts 前端（Google Material You 设计风格、中文界面）
  - 回测配置页（策略选择【可折叠面板】、标的池【弹窗搜索选择】、回测参数）
  - 结果展示（收益曲线图、到期盈亏图、Greeks 时序图、绩效指标、交易记录表）
  - 错误处理（API 错误提示）
- ✅ **Phase 5 完成**：
  - 示例策略：`BuyCallStrategy`、`StraddleStrategy`、`IronCondorStrategy`
  - 单元测试覆盖 Greeks、期权链、组合盈亏、回测引擎
  - 示例数据生成器（`examples/generate_sample_data.py`）

---

## 技术栈决策（已确定）

| 维度 | 选择 | 说明 |
|------|------|------|
| **UI** | **Web 前端 (React + Vite + ECharts)** | 现代化浅色系设计，通过 FastAPI REST API 与 Python 回测引擎通信。 |
| **数据** | **本地 CSV/Parquet + Data API 扩展** | 内置本地数据加载器（`server.py` 中有 demo synthetic data），同时预留 `BaseDatafeed` 接口。 |
| **策略** | **任意多腿组合** | 从第一版即支持 Butterfly、Iron Condor、Calendar Spread 等复杂组合的 Greeks 与盈亏归因。 |
| **后端** | Python 3.10+ | 事件驱动回测引擎，保留 `EventEngine` 核心，新增 `OptionBacktestEngine`。 |

---

## 目录结构

```
ccQuant/
├── ccquant/                       # 核心 Python 包
│   ├── core/                      # 事件引擎、数据模型、常量、数据库接口、工具类
│   ├── option/                    # 期权特有：期权链、Greeks、组合、定价、盈亏图
│   ├── backtest/                  # 回测引擎：撮合器、日终结算、结果聚合
│   ├── strategy/                  # 策略基类与示例策略
│   ├── data/                      # 数据加载与缓存（待扩展）
│   └── ui/                        # Web UI 服务端（FastAPI）
├── ccquant-web/                   # React + Vite + ECharts 前端项目
│   ├── src/
│   │   ├── App.tsx                # 主应用（回测配置 + 结果展示）
│   │   ├── App.css                # 浅色系样式
│   │   ├── api.ts                 # API 封装
│   │   └── ...
│   └── package.json
├── examples/                      # 回测示例与数据样例（待填充）
├── tests/                         # 单元测试
├── assets/                        # UI 图标、字体、设计稿
├── README.md                      # 本文件（记忆文档）
├── requirements.txt               # 后端依赖
└── pyproject.toml                 # （可选）后续添加
```

---

## 快速启动

### 1. 安装后端依赖
```bash
cd ccQuant
pip install -r requirements.txt
```

### 2. 生成示例数据（首次运行）
```bash
python examples/generate_sample_data.py
```
将在 `data_storage/` 目录下生成：
- `contracts/510050.csv` - 期权合约定义
- `bars/2024/510050_202401.csv` - 日 K 行情数据

### 3. 启动 FastAPI 服务端
```bash
# 方式一：直接运行（需设置 PYTHONPATH）
set PYTHONPATH=%CD% && python -m ccquant.ui.server

# 方式二：使用 uvicorn
uvicorn ccquant.ui.server:app --host 0.0.0.0 --port 8080
```
服务默认运行在 `http://127.0.0.1:8080`。

### 4. 启动前端开发服务器（新终端）
```bash
cd ccquant-web
npm install   # 首次运行
npm run dev
```
前端默认运行在 `http://localhost:5173`。

### 5. 生产部署
```bash
cd ccquant-web
npm run build
```
构建后的文件位于 `dist/` 目录，FastAPI 会自动托管静态文件。

### 6. 运行测试
```bash
cd ccQuant
python -m pytest tests/ -v
```

---

## 数据格式说明

### 合约定义 CSV (`data_storage/contracts/{underlying}.csv`)
| 字段 | 说明 |
|------|------|
| `symbol` | 合约代码 |
| `exchange` | 交易所 (SSE/SZSE) |
| `option_type` | CALL 或 PUT |
| `strike` | 行权价 |
| `expiry` | 到期日 (YYYY-MM-DD) |
| `underlying` | 标的代码 |
| `size` | 合约乘数 |
| `pricetick` | 最小变动价位 |

### 行情数据 CSV (`data_storage/bars/{year}/{underlying}_{year}{month}.csv`)
| 字段 | 说明 |
|------|------|
| `symbol` | 合约代码 |
| `exchange` | 交易所 |
| `datetime` | 时间戳 (ISO 格式) |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `implied_vol` | 隐含波动率 (可选) |

---

## 核心设计思想（必读）

### 1. 回测引擎设计

- **数据来源**：优先支持 `BarData`（1 分钟 / 日 K），Tick 模式作为后续扩展。
- **撮合逻辑**：限价单在当前 Bar 的 `[low, high]` 区间内撮合，成交价由开盘价约束，**严格避免未来函数**（与 vnpy CTA 回测引擎一致）。
- **持仓模型**：使用 `OptionPortfolio` 替代 vnpy 中简单的 `pos` 整数持仓，每一腿独立记录数量、成本、当期 Greeks、浮动盈亏。
- **日终结算**：每日计算组合市值、 Greeks 归因、保证金占用、当日盈亏。
- **信号模式**：除了传统事件驱动策略，还支持 **预计算信号矩阵**（`signal_df`）模式，方便机器学习 / 深度学习模型直接接入回测。

### 2. 机器学习 / 深度学习接入方式

- **模型在线推理**：在策略 `__init__` 中加载训练好的模型（PyTorch / LightGBM / XGBoost）。每 Bar 的 `on_bars(df)` 回调中，引擎传入特征 DataFrame（包含标的价格、各合约 IV、期限结构、当前持仓 Greeks），策略调用 `model.predict(df)` 得到目标持仓，引擎执行调仓。
- **预计算信号模式（推荐）**：离线用 GPU 训练模型并生成 `(datetime, vt_symbol)` 维度的 `signal_df`（Polars/Pandas），回测引擎直接读取信号矩阵。此方式避免了在回测循环里反复加载深度学习模型，效率最高。
- 对 Transformer / MLP 等深度学习模型，建议在 `on_bars()` 中做 **batch inference**（一次性预测整个截面），而不是逐合约循环 `predict`。

### 3. 图表层设计

- Web 前端使用 **ECharts** 绘制组合市值走势图、Greeks 时序图、盈亏图（Payoff Diagram）、期权链热力图。
- Python 后端通过 FastAPI 将回测结果推送到前端渲染。Bar 级回测数据量小，不会有性能瓶颈。
- **真正的性能瓶颈在 Python 后端的 Greeks 重算**（尤其是多到期日、多行权价的截面），后续可通过 **Polars / Numba** 向量化优化。

### 4. 与 vnpy 的关系

- **不修改 vnpy 源码**：`ccQuant` 是一个完全独立的新目录。
- **复用清单**：`EventEngine`、`BarGenerator`、数据类（`TickData`, `BarData`, `OrderData`, `TradeData`, `ContractData`）、`BaseDatabase` 接口、`BaseGateway` 抽象。
- **重写清单**：`CtaTemplate` → `OptionStrategy`，`BacktestingEngine` → `OptionBacktestEngine`，所有 UI 组件，所有图表渲染逻辑。

---

## 已完成功能清单

### Python 后端
- [x] `ccquant/core/event.py` — `EventEngine`, `Event`
- [x] `ccquant/core/constant.py` — `Direction`, `Offset`, `Status`, `Product`, `OptionType`, `Exchange`, `Interval`, `OrderType`
- [x] `ccquant/core/object.py` — `BaseData`, `TickData`, `BarData`, `OrderData`, `TradeData`, `PositionData`, `AccountData`, `ContractData`, `LogData`, `QuoteData`, 请求类
- [x] `ccquant/core/utility.py` — `BarGenerator`, `round_to`, `floor_to`, `ceil_to`, `get_digits`, JSON 读写
- [x] `ccquant/core/database.py` — `BaseDatabase`, `BarOverview`, `TickOverview`
- [x] `ccquant/core/gateway.py` — `BaseGateway`
- [x] `ccquant/option/pricing.py` — Black-Scholes 定价、Delta/Gamma/Theta/Vega/Rho 解析解、隐含波动率牛顿迭代
- [x] `ccquant/option/greeks.py` — `Greeks` dataclass，支持加减乘和 `to_dict`
- [x] `ccquant/option/chain.py` — `OptionChain`，支持 expiry/strike 组织、ATM 查找
- [x] `ccquant/option/portfolio.py` — `OptionPortfolio` + `LegPosition`，支持任意多腿组合的 Greeks/PnL/市值聚合
- [x] `ccquant/option/payoff.py` — `payoff_at_expiry`（到期盈亏）和 `payoff_at_date`（当前 TTE 理论盈亏），含 breakeven 计算
- [x] `ccquant/backtest/matcher.py` — Bar 模式限价单撮合（无未来函数）
- [x] `ccquant/backtest/engine.py` — `OptionBacktestEngine`，多标的事件驱动回测，每 Bar 组合 Greeks+PnL 结算
- [x] `ccquant/backtest/recorder.py` — `BacktestRecorder`，记录交易、快照、日志
- [x] `ccquant/backtest/result.py` — `BacktestResult` + `BacktestStatistics`，返回/夏普/最大回撤
- [x] `ccquant/strategy/template.py` — `OptionStrategyTemplate`, `BuyCallStrategy`, `StraddleStrategy`, `IronCondorStrategy`
- [x] `ccquant/ui/server.py` — FastAPI 服务端，支持真实数据加载、标的切换、静态文件托管

### Web 前端
- [x] 项目初始化（Vite + React + TypeScript）
- [x] Google Material You 设计风格（渐变色彩、圆角、阴影）
- [x] 完整中文界面
- [x] 回测配置面板
  - [x] 策略选择（可折叠面板，带图标提示）
  - [x] 标的池配置（弹窗搜索选择，显示已选缩略）
  - [x] 回测参数（日期区间、资金、滑点、手续费）
- [x] 错误处理（API 错误提示、加载状态）
- [x] 结果展示面板（绩效指标、收益曲线、到期盈亏图、Greeks 时序图、交易记录）
- [x] API 封装（`api.ts`）

### 测试
- [x] `tests/test_option_core.py` — B-S 定价、Greeks、期权链、组合 PnL、Payoff 图
- [x] `tests/test_backtest_engine.py` — 回測引擎端到端测试（Buy Call）

---

## 下一步待做（供后续会话参考）

1. **数据层增强**
   - 接入 `BaseDatafeed` 接口，支持 RQData / Tushare / AKShare 实时数据下载
   - 支持 Tick 级别数据回测

2. **前端功能扩展**
   - T 型报价页面（Option Chain Viewer）
   - ~~策略参数编辑器（动态表单）~~ ✅ 已完成
   - 回测结果导出（CSV / JSON）
   - 回测结果对比（多策略绩效对比）
   - WebSocket 实时推送回测进度

3. **策略示例扩展**
   - `ButterflyStrategy`
   - `CalendarSpreadStrategy`
   - ML 信号接入示例（展示如何加载 `signal_df`）

4. **性能优化**
   - Greeks 计算向量化（Numba / Polars）
   - Bar 数据预索引和内存缓存优化

5. **工程完善**
   - `pyproject.toml` 配置（支持 `pip install -e .`）
   - CI / lint 配置（ruff / mypy / tsc）

---

## 参考资料

- `CODE_REFERENCE_GUIDE.md` — 对 vnpy 的架构梳理（需审慎参考，部分路径可能不准确）
- `vnpy/trader/object.py` — `ContractData` 已原生包含期权字段
- `vnpy_ctastrategy/backtesting.py` — 限价单撮合与日终结算逻辑
- `vnpy/alpha/strategy/backtesting.py` — 多标的投资组合回测逻辑、信号矩阵驱动模式
