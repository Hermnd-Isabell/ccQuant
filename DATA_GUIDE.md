# ccQuant 数据接入指南

本指南说明如何准备和接入真实期权历史数据用于回测。

---

## 数据目录结构

在 `ccQuant/` 目录下创建 `data_storage/` 文件夹：

```
ccQuant/
├── data_storage/
│   ├── contracts/           # 合约定义文件
│   │   └── 510050.csv      # 标的代码命名的合约文件
│   └── bars/               # 行情数据文件
│       └── 2024/           # 按年份组织
│           └── 510050_202401.csv
```

---

## 1. 合约定义文件格式

文件路径：`data_storage/contracts/{underlying_symbol}.csv`

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| symbol | string | 合约代码 | 510050C2401M02500 |
| exchange | string | 交易所代码 | SSE / SZSE / CFFEX |
| option_type | string | 期权类型 | CALL / PUT |
| strike | float | 行权价 | 2.5 |
| expiry | string | 到期日 | 2024-01-24 |
| underlying | string | 标的代码 | 510050 |
| size | int | 合约乘数 | 10000 |
| pricetick | float | 最小变动价位 | 0.0001 |

**示例文件内容：**
```csv
symbol,exchange,option_type,strike,expiry,underlying,size,pricetick
510050C2401M02500,SSE,CALL,2.5,2024-01-24,510050,10000,0.0001
510050P2401M02500,SSE,PUT,2.5,2024-01-24,510050,10000,0.0001
510050C2401M02600,SSE,CALL,2.6,2024-01-24,510050,10000,0.0001
510050P2401M02600,SSE,PUT,2.6,2024-01-24,510050,10000,0.0001
```

---

## 2. 行情数据文件格式

文件路径：`data_storage/bars/{year}/{symbol}_{yyyymm}.csv`

每行是一个合约在某日的行情：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| symbol | string | 合约代码 |
| datetime | string | 时间戳 (ISO8601) |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | float | 成交量 |
| open_interest | float | 持仓量（可选） |
| implied_vol | float | 隐含波动率（可选，用于 Greeks 计算） |

**示例文件内容：**
```csv
symbol,datetime,open,high,low,close,volume,open_interest,implied_vol
510050C2401M02500,2024-01-02T09:30:00,0.125,0.128,0.122,0.126,15000,85000,0.185
510050C2401M02500,2024-01-03T09:30:00,0.126,0.130,0.124,0.128,18200,86000,0.182
510050P2401M02500,2024-01-02T09:30:00,0.085,0.088,0.082,0.086,12000,62000,0.195
```

---

## 3. 快速生成示例数据

运行以下脚本生成示例数据用于测试：

```bash
cd ccQuant
python examples/generate_sample_data.py
```

---

## 4. 数据源推荐

| 数据源 | 获取方式 | 说明 |
|--------|----------|------|
| 聚宽 (JoinQuant) | jqdata API | 国内期权日线数据完整 |
| 米筐 (RiceQuant) | rqalpha/rqdata | 分钟级数据支持好 |
| Tushare | tushare pro API | 需要积分，日线数据免费 |
| 本地券商数据 | 终端导出 | 通常支持 CSV/Excel 导出 |

---

## 5. 数据质量检查清单

- [ ] 合约 symbol 格式统一（建议 `{标的}C/P{到期年月}M{行权价*1000}`）
- [ ] 时间戳按升序排列
- [ ] 无缺失的 OHLC 字段
- [ ] 期权类型与行权价对应正确（CALL/PUT）
- [ ] 到期日格式统一为 `YYYY-MM-DD`

---

## 6. 数据加载流程

服务端启动时会自动检测 `data_storage/` 目录：

1. 如果存在 `data_storage/contracts/*.csv`，加载真实合约定义
2. 如果存在 `data_storage/bars/`，加载真实行情数据
3. 否则使用内置的 Demo 数据

你可以在回测配置面板中选择具体使用的标的代码。
