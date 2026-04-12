# ccQuant 开发环境搭建指南

## 项目简介

ccQuant 是一个基于 Web 的期权量化交易研究平台，前后端分离架构。

- 前端：React 19 + TypeScript + Vite 8 + ECharts 6
- 后端：FastAPI + SQLAlchemy + SQLite
- 数据库文件位置：`~/.ccquant/ccquant.db`（首次启动后端自动创建）

---

## 1. 环境要求

| 工具 | 最低版本 |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 8+ |

---

## 2. 后端安装

```bash
cd ccQuant
pip install -r requirements.txt
```

`requirements.txt` 中已包含 fastapi、uvicorn、pydantic、pandas、numpy 等。但有两个实际用到的包没写进去，需要手动补装：

```bash
pip install sqlalchemy tqdm
```

完整依赖清单（供参考）：

| 包 | 用途 |
|----|------|
| fastapi + uvicorn | Web 服务 |
| pydantic | 请求/响应模型 |
| sqlalchemy | ORM，操作 SQLite |
| pandas | 数据处理、CSV 导入 |
| numpy / scipy | 数值计算 |
| tqdm | 数据导入进度条 |

---

## 3. 前端安装

```bash
cd ccQuant/ccquant-web
npm install
```

---

## 4. 启动服务

### 4.1 启动后端（端口 8080）

```bash
cd ccQuant
python -m ccquant.ui.server
```

首次启动时，后端会自动在 `~/.ccquant/` 目录下创建 `ccquant.db` SQLite 数据库，并建好所有表。无需手动建库。

### 4.2 启动前端开发服务器（端口 3000）

```bash
cd ccQuant/ccquant-web
npm run dev
```

浏览器访问 `http://localhost:3000`。

前端 Vite 已配置代理，所有 `/api` 和 `/ws` 请求会自动转发到后端 `127.0.0.1:8080`，无需额外配置。

### 4.3 生产模式

```bash
cd ccQuant/ccquant-web
npm run build
```

构建产物在 `ccquant-web/dist/`。后端 server.py 已内置静态文件服务，构建完成后直接访问 `http://localhost:8080` 即可使用，无需前端开发服务器。

---

## 5. 数据库说明

### 5.1 表结构

| 表名 | 说明 |
|------|------|
| `underlyings` | 标的资产（如 510050 = 50ETF） |
| `option_contracts` | 期权合约定义（行权价、到期日、C/P 类型） |
| `option_daily_bars` | 期权日K线（含 IV、Delta、Gamma、Theta、Vega、Rho） |
| `daily_bars` | 标的 ETF 日K线 |
| `risk_free_rates` | 无风险利率 |
| `backtest_records` | 回测记录 |

### 5.2 导入测试数据

项目自带了 50ETF 期权数据的导入脚本。如果你有原始 CSV 文件（`50etf_options.csv`），可以这样导入：

```bash
cd ccQuant
# 修改 import_50etf.py 底部的 filepath 为你的 CSV 实际路径
python import_50etf.py
```

也可以通过前端页面的「数据库」Tab 上传 CSV 文件，支持期权数据和标的数据两种类型。

### 5.3 已有数据（如果拿到的是带数据库的压缩包）

如果压缩包中包含 `ccquant.db` 文件，将其放到 `~/.ccquant/` 目录下即可：

- Windows: `C:\Users\<你的用户名>\.ccquant\ccquant.db`
- macOS/Linux: `~/.ccquant/ccquant.db`

后端启动时会自动检测已有表并执行增量迁移（添加新列），不会丢失数据。

---

## 6. 项目结构

```
ccQuant/
├── ccquant/                    # Python 后端
│   ├── ui/
│   │   └── server.py           # FastAPI 主服务（所有 API 路由都在这里）
│   ├── database.py             # 数据库模型 + DatabaseManager
│   ├── data_import.py          # CSV/Parquet 数据导入工具
│   ├── strategy/
│   │   ├── template.py         # 策略模板基类
│   │   └── strategies.py       # 内置示例策略
│   ├── backtest/
│   │   ├── engine.py           # 回测引擎
│   │   ├── matcher.py          # 撮合器
│   │   ├── recorder.py         # 记录器
│   │   └── result.py           # 回测结果
│   ├── option/
│   │   ├── chain.py            # 期权链
│   │   ├── greeks.py           # 希腊字母计算
│   │   ├── pricing.py          # 期权定价
│   │   ├── payoff.py           # 损益图
│   │   └── portfolio.py        # 组合管理
│   ├── core/
│   │   ├── constant.py         # 枚举常量
│   │   ├── object.py           # 数据对象
│   │   ├── database.py         # 核心数据库接口
│   │   ├── event.py            # 事件引擎
│   │   ├── gateway.py          # 网关接口
│   │   └── utility.py          # 工具函数
│   └── data/
│       └── csv_loader.py       # CSV 加载器
│
├── ccquant-web/                # React 前端
│   ├── src/
│   │   ├── App.tsx             # 路由入口（4个页面）
│   │   ├── api.ts              # 所有后端 API 调用封装
│   │   ├── types.ts            # TypeScript 类型定义
│   │   ├── pages/
│   │   │   ├── DatabasePage.tsx        # 数据库页面（已完成）
│   │   │   ├── VisualizationPage.tsx   # 可视化页面（已完成）
│   │   │   ├── StrategyEditorPage.tsx  # 策略编写页面（待开发）
│   │   │   └── BacktestPage.tsx        # 策略回测页面（待开发）
│   │   └── components/
│   │       ├── VolLeftPanel.tsx         # 可视化左侧面板
│   │       ├── Vol3DSurface.tsx         # 3D 波动率曲面
│   │       ├── GreeksChart.tsx          # Greeks 图表
│   │       ├── OptionChainViewer.tsx    # T型报价
│   │       ├── PayoffChart.tsx          # 损益图
│   │       ├── UnderlyingSelector.tsx   # 标的选择器
│   │       ├── BacktestDashboard.tsx    # 回测仪表盘
│   │       ├── StrategyBuilder.tsx      # 策略构建器
│   │       └── StrategyParamsForm.tsx   # 策略参数表单
│   ├── vite.config.ts          # Vite 配置（含 API 代理）
│   └── package.json
│
├── import_50etf.py             # 50ETF 数据导入脚本
├── requirements.txt            # Python 依赖
├── data_storage/               # 本地数据文件
│   └── contracts/
│       └── 510050.csv
├── tests/                      # 测试
└── examples/                   # 示例脚本
```

---

## 7. API 概览

所有 API 路由定义在 `ccquant/ui/server.py`，前端调用封装在 `ccquant-web/src/api.ts`。

### 数据库相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data/underlyings` | 获取标的列表 |
| GET | `/api/data/underlyings/{symbol}/expiries` | 获取到期日列表 |
| GET | `/api/data/underlyings/{symbol}/trade-dates` | 获取交易日列表 |
| GET | `/api/data/underlyings/{symbol}/contracts` | 获取合约列表 |
| GET | `/api/data/option-bars` | 期权K线分页查询 |
| GET | `/api/data/daily-bars` | 标的K线分页查询 |
| GET | `/api/data/merged-bars` | 合并K线（期权+标的）分页查询 |
| GET | `/api/data/stats` | 筛选后的统计数据 |
| POST | `/api/data/upload` | 上传 CSV 文件（multipart/form-data） |
| DELETE | `/api/data/option-bars` | 删除期权K线 |
| DELETE | `/api/data/daily-bars` | 删除标的K线 |

### 可视化相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/viz/market/{underlying}` | 行情概览（K线+IV+Greeks） |
| GET | `/api/viz/vol-smile/{underlying}` | 波动率微笑 2D |
| GET | `/api/viz/vol-surface/{underlying}` | 波动率曲面 3D |
| GET | `/api/viz/vol-surface-v2/{underlying}` | 波动率曲面 V2（含成交量柱） |
| GET | `/api/viz/contract/{symbol}` | 单合约数据 |
| GET | `/api/viz/option-chain/{underlying}` | T型报价 |

### 策略相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/strategies` | 获取策略列表 |
| GET | `/api/strategies/{filename}/code` | 获取策略源码 |
| POST | `/api/strategies/{filename}` | 保存策略 |
| POST | `/api/strategies/{filename}/open-ide` | 在 IDE 中打开 |

### 回测相关
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/backtest/run` | 运行回测 |
| GET | `/api/backtest/history` | 获取回测历史 |

---

## 8. 四大页面开发状态

| 页面 | 路由 | 状态 | 说明 |
|------|------|------|------|
| 数据库 | `/database` | ✅ 已完成 | CSV 上传、分页浏览、筛选、删除 |
| 可视化 | `/visualization` | ✅ 已完成 | 行情K线、波动率2D微笑、3D曲面、T型报价 |
| 策略编写 | `/strategy` | 🔧 待开发 | 基础框架已搭建，需完善 |
| 策略回测 | `/backtest` | 🔧 待开发 | 基础框架已搭建，需完善 |

---

## 9. 待开发功能详情

### 策略编写页面
- 展示已保存的策略列表（后端 API 已有）
- 选择策略查看代码（后端 API 已有）
- 点击跳转到外部 IDE 编辑（后端 API 已有）
- 基于模板创建新策略并命名保存
- 策略模板基类在 `ccquant/strategy/template.py`
- 内置示例策略在 `ccquant/strategy/strategies.py`（BuyCall、Straddle、IronCondor）

### 策略回测页面
- 标的池：弹窗界面构建并保存静态标的池
- 选择回测参数（日期范围、初始资金等）
- 选择回测策略
- 执行回测并展示结果（收益曲线、统计指标等）
- 回测引擎在 `ccquant/backtest/engine.py`

---

## 10. 已知问题 & 注意事项

1. `daily_bars` 表可能为空 — 如果只导入了期权数据，标的 ETF 本身的日K线需要单独导入。可视化页面的行情视图依赖这个表。
2. `requirements.txt` 缺少 `sqlalchemy` 和 `tqdm`，记得手动安装。
3. 分钟级别数据目前仅在 UI 层预留了选项，数据库模型尚未包含分钟K线表。
4. 后端启动后工作目录不会改变，数据库路径是绝对路径 `~/.ccquant/ccquant.db`。
5. 策略文件存放在 `ccquant/strategy/` 目录下，后端通过扫描该目录获取策略列表。

---

## 快速验证

启动前后端后，打开浏览器访问 `http://localhost:3000`，应该能看到顶部导航栏有「数据库」「可视化」「策略编写」「策略回测」四个 Tab。如果数据库中有数据，切换到「数据库」页面应该能看到数据表格。
