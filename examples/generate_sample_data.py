"""
生成示例期权数据用于测试 ccQuant 平台。
生成符合 DATA_GUIDE.md 规范的 CSV 文件。
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np


def generate_contracts(underlying: str = "510050", output_dir: str = "data_storage/contracts") -> None:
    """生成合约定义文件。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成 2 个到期月份，每个到期月 5 个行权价
    strikes = [2.4, 2.5, 2.6, 2.7, 2.8]
    expiries = ["2024-01-24", "2024-02-28"]

    contracts = []
    for expiry in expiries:
        for strike in strikes:
            # Call
            contracts.append({
                "symbol": f"{underlying}C{expiry.replace('-', '')[4:]}M{int(strike*1000):05d}",
                "exchange": "SSE",
                "option_type": "CALL",
                "strike": strike,
                "expiry": expiry,
                "underlying": underlying,
                "size": 10000,
                "pricetick": 0.0001,
            })
            # Put
            contracts.append({
                "symbol": f"{underlying}P{expiry.replace('-', '')[4:]}M{int(strike*1000):05d}",
                "exchange": "SSE",
                "option_type": "PUT",
                "strike": strike,
                "expiry": expiry,
                "underlying": underlying,
                "size": 10000,
                "pricetick": 0.0001,
            })

    df = pd.DataFrame(contracts)
    output_file = output_path / f"{underlying}.csv"
    df.to_csv(output_file, index=False)
    print(f"已生成合约定义: {output_file} ({len(df)} 个合约)")
    return df


def generate_bars(contracts_df: pd.DataFrame, underlying: str = "510050",
                  start_date: str = "2024-01-02", days: int = 40,
                  output_dir: str = "data_storage/bars/2024") -> None:
    """生成行情数据文件。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    dates = [start + timedelta(days=i) for i in range(days)]
    # 过滤周末
    dates = [d for d in dates if d.weekday() < 5]

    all_bars = []

    # 模拟标的走势（50ETF 约 2.5 元）
    underlying_price = 2.5

    for date in dates:
        # 标的每日小幅波动
        underlying_price *= (1 + random.gauss(0, 0.008))

        for _, contract in contracts_df.iterrows():
            strike = contract["strike"]
            opt_type = contract["option_type"]
            days_to_expiry = (datetime.strptime(contract["expiry"], "%Y-%m-%d") - date).days

            # 简化的 B-S 启发式定价（不考虑利率和股息）
            moneyness = underlying_price / strike
            if opt_type == "CALL":
                intrinsic = max(0, underlying_price - strike)
                # OTM 期权价格低，ITM 价格高
                base_price = intrinsic + 0.05 * max(0, 1 - moneyness) + random.gauss(0, 0.005)
            else:
                intrinsic = max(0, strike - underlying_price)
                base_price = intrinsic + 0.05 * max(0, moneyness - 1) + random.gauss(0, 0.005)

            base_price = max(0.001, base_price)  # 最小价格保护

            # 生成 OHLC
            open_p = base_price * (1 + random.gauss(0, 0.01))
            close_p = base_price * (1 + random.gauss(0, 0.01))
            high_p = max(open_p, close_p) * (1 + abs(random.gauss(0, 0.005)))
            low_p = min(open_p, close_p) * (1 - abs(random.gauss(0, 0.005)))

            # 隐含波动率随到期日临近而波动
            base_iv = 0.18 + random.gauss(0, 0.02)
            if days_to_expiry < 7:
                base_iv += 0.05  # 到期前波动率上升

            all_bars.append({
                "symbol": contract["symbol"],
                "datetime": date.strftime("%Y-%m-%dT09:30:00"),
                "open": round(open_p, 4),
                "high": round(high_p, 4),
                "low": round(low_p, 4),
                "close": round(close_p, 4),
                "volume": int(random.gauss(15000, 5000)),
                "open_interest": int(random.gauss(80000, 20000)),
                "implied_vol": round(max(0.05, base_iv), 4),
            })

    df = pd.DataFrame(all_bars)
    output_file = output_path / f"{underlying}_202401.csv"
    df.to_csv(output_file, index=False)
    print(f"已生成行情数据: {output_file} ({len(df)} 条记录, {len(dates)} 个交易日)")


def main():
    """主入口。"""
    print("=" * 60)
    print("ccQuant 示例数据生成器")
    print("=" * 60)

    # 生成 510050 (50ETF) 的示例数据
    contracts = generate_contracts("510050")
    generate_bars(contracts, "510050", "2024-01-02", 40)

    # 可选：生成更多标的
    # contracts = generate_contracts("000300")  # 300ETF
    # generate_bars(contracts, "000300", "2024-01-02", 40)

    print("=" * 60)
    print("示例数据生成完成！")
    print("现在可以启动服务端并选择真实数据进行回测。")
    print("=" * 60)


if __name__ == "__main__":
    main()
