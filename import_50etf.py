#!/usr/bin/env python3
"""
导入50ETF期权数据到ccQuant数据库
支持从wind/同花顺等导出的标准格式
"""

import sys
sys.path.insert(0, 'D:\\vnpy-4.3.0')

import pandas as pd
from datetime import datetime, date
from tqdm import tqdm
from ccquant.database import db

def parse_contract_code(security_id: str, symbol: str) -> dict:
    """
    解析合约代码
    示例: 10000001.SH -> 提取到期月和行权价信息
    从symbol解析: 华夏上证50ETF期权1503认购2.20
    """
    try:
        # 从symbol提取信息
        # 格式: 华夏上证50ETF期权[年份][月份][认购/认沽][行权价]
        if '认购' in symbol:
            option_type = 'C'
        elif '认沽' in symbol:
            option_type = 'P'
        else:
            option_type = 'C'

        # 提取行权价 (在最后一个数字部分)
        import re
        numbers = re.findall(r'\d+\.?\d*', symbol)
        if len(numbers) >= 2:
            # 最后一个是行权价
            strike = float(numbers[-1])
            # 倒数第二个包含到期月 (如1503)
            expiry_code = numbers[-2]
            if len(expiry_code) >= 4:
                year = 2000 + int(expiry_code[:2])
                month = int(expiry_code[2:4])
            else:
                year = 2024
                month = 12
        else:
            strike = 2.5
            year, month = 2024, 12

        return {
            'option_type': option_type,
            'strike': strike,
            'year': year,
            'month': month
        }
    except Exception as e:
        print(f"解析合约失败 {security_id}: {e}")
        return {'option_type': 'C', 'strike': 2.5, 'year': 2024, 'month': 12}

def import_50etf_options(filepath: str):
    """导入50ETF期权数据"""
    print(f"📥 导入50ETF期权数据: {filepath}")
    print("=" * 60)

    try:
        # 读取CSV
        print("读取CSV文件...")
        df = pd.read_csv(filepath)
        print(f"✅ 读取成功: {len(df)} 行数据")
        print(f"\n列名: {list(df.columns)}")
        print(f"\n前3行预览:")
        print(df.head(3))

        # 检查必要列
        required_cols = ['security_id', 'symbol', 'trade_date', 'call_put',
                        'open', 'high', 'low', 'close', 'exercise_price', 'last_edate']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            print(f"\n⚠️ 缺少列: {missing}")
            print(f"可用列: {list(df.columns)}")
            return

        # 处理日期
        print("\n📅 处理日期格式...")
        df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        df['expiry_date'] = pd.to_datetime(df['last_edate'], format='%Y%m%d')

        print(f"数据时间范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
        print(f"合约数量: {df['security_id'].nunique()}")
        print(f"交易日数量: {df['trade_date'].nunique()}")

        # 添加标的
        print("\n📊 添加510050标的定义...")
        db.add_underlying(
            symbol="510050",
            name="50ETF",
            underlying_type="ETF",
            exchange="SSE",
            lot_size=10000
        )

        # 解析合约信息
        print("\n🔧 解析合约信息...")
        unique_contracts = df[['security_id', 'symbol', 'exercise_price', 'call_put', 'expiry_date']].drop_duplicates()
        print(f"发现 {len(unique_contracts)} 个不同合约")

        # 添加合约定义
        print("添加合约定义到数据库...")
        for _, row in tqdm(unique_contracts.iterrows(), total=len(unique_contracts)):
            db.add_option_contract(
                symbol=row['security_id'],
                underlying_symbol="510050",
                option_type=row['call_put'],  # C/P
                strike=float(row['exercise_price']),
                expiry_date=row['expiry_date'].date()
            )

        # 导入行情数据
        print("\n💾 导入行情数据到数据库...")

        # 重命名列以匹配数据库模型
        column_map = {
            'open': 'open_price',
            'high': 'high_price',
            'low': 'low_price',
            'close': 'close_price',
            'settle_price': 'settle_price',
            'volume': 'volume',
            'amount': 'amount',
            'open_interest': 'open_interest',
            'implc_volatlty': 'iv',
            'delta': 'delta',
            'gamma': 'gamma',
            'theta': 'theta',
            'vega': 'vega',
            'rho': 'rho'
        }

        total_count = 0
        grouped = df.groupby('security_id')

        for symbol, group in tqdm(grouped, desc="导入合约"):
            # 准备数据
            symbol_df = group.copy()
            symbol_df['trade_date'] = symbol_df['trade_date'].dt.date

            # 标准化列名
            for old_col, new_col in column_map.items():
                if old_col in symbol_df.columns:
                    symbol_df[new_col] = symbol_df[old_col]

            # 导入数据库
            try:
                count = db.import_option_bars(symbol_df, symbol)
                total_count += count
            except Exception as e:
                print(f"\n导入 {symbol} 失败: {e}")

        print(f"\n✅ 导入完成!")
        print(f"   总合约数: {len(unique_contracts)}")
        print(f"   总记录数: {total_count}")

        # 验证导入
        print("\n📋 数据库验证:")
        contracts = db.get_option_contracts("510050")
        print(f"   数据库中510050的合约数: {len(contracts)}")

        if contracts:
            print(f"   到期日列表 (前10个):")
            expiries = db.get_expiry_dates("510050")
            for exp in sorted(expiries)[:10]:
                print(f"     - {exp}")

            # 显示一个合约的数据示例
            sample_contract = contracts[0]
            from datetime import date
            sample_df = db.get_option_bars(
                sample_contract.symbol,
                date(2015, 1, 1),
                date(2025, 12, 31)
            )
            if not sample_df.empty:
                print(f"\n   合约 {sample_contract.symbol} 数据示例:")
                print(f"   记录数: {len(sample_df)}")
                print(f"   日期范围: {sample_df['trade_date'].min()} ~ {sample_df['trade_date'].max()}")

    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    filepath = r"D:\vnpy-4.3.0\50etf_options.csv"
    import_50etf_options(filepath)
