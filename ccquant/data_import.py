"""
ccQuant 数据导入工具
支持从CSV/Parquet文件导入历史行情数据
"""

import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Callable
import json

import pandas as pd
from tqdm import tqdm

from ccquant.database import db, Underlying, OptionContract


class DataImporter:
    """数据导入器"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ========== 标的数据导入 ==========

    def _parse_date(self, date_val) -> datetime:
        """解析各种日期格式"""
        if isinstance(date_val, datetime):
            return date_val

        date_str = str(date_val).strip()

        # 尝试不同格式
        formats = [
            '%Y-%m-%d',      # 2020-05-22
            '%Y/%m/%d',      # 2020/05/22
            '%Y%m%d',        # 20200522
            '%y%m%d',        # 200522
            '%d/%m/%Y',      # 22/05/2020
            '%m/%d/%Y',      # 05/22/2020
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # 如果都失败，使用pandas自动解析
        return pd.to_datetime(date_val)

    def import_underlying_from_csv(self,
                                   filepath: str,
                                   symbol: str,
                                   date_col: str = 'date',
                                   columns_map: Optional[dict] = None) -> int:
        """
        从CSV导入标的历史数据

        Args:
            filepath: CSV文件路径
            symbol: 标的代码
            date_col: 日期列名
            columns_map: 列名映射 {'open': '开盘价', 'high': '最高价', ...}

        Returns:
            导入的记录数
        """
        print(f"📥 导入标的 {symbol} 数据 from {filepath}")

        # 读取CSV
        df = pd.read_csv(filepath)
        print(f"   读取 {len(df)} 行数据")

        # 标准化列名
        if columns_map:
            df = df.rename(columns=columns_map)

        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必要列: {col}")

        # 处理日期列 - 支持多种格式
        print(f"   解析日期列: {date_col}")
        sample_date = df[date_col].iloc[0]
        print(f"   日期示例: {sample_date} (类型: {type(sample_date)})")

        df['trade_date'] = df[date_col].apply(self._parse_date)

        # 导入数据库
        count = db.import_underlying_bars(df, symbol)

        # 更新标的定义
        db.add_underlying(
            symbol=symbol,
            name=symbol,
            underlying_type='ETF',
            exchange='SSE'
        )

        print(f"✅ 成功导入 {count} 条记录")
        return count

    def import_underlying_from_parquet(self,
                                       filepath: str,
                                       symbol: str) -> int:
        """从Parquet导入标的数据"""
        print(f"📥 导入标的 {symbol} 数据 from {filepath}")

        df = pd.read_parquet(filepath)

        # 标准化列名
        column_mapping = {
            'trade_date': 'trade_date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount'
        }

        # 自动识别列名
        for std_col in column_mapping.keys():
            if std_col not in df.columns:
                # 尝试常见变体
                variants = [
                    std_col.capitalize(),
                    std_col.upper(),
                    std_col.lower(),
                    f"{std_col}_price",
                    f"{std_col}Price"
                ]
                for variant in variants:
                    if variant in df.columns:
                        df = df.rename(columns={variant: std_col})
                        break

        # 确保日期列
        if 'trade_date' not in df.columns and 'date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['date'])
        else:
            df['trade_date'] = pd.to_datetime(df['trade_date'])

        count = db.import_underlying_bars(df, symbol)

        db.add_underlying(
            symbol=symbol,
            name=symbol,
            underlying_type='ETF',
            exchange='SSE'
        )

        print(f"✅ 成功导入 {count} 条记录")
        return count

    # ========== 期权数据导入 ==========

    def import_option_chain_csv(self,
                                filepath: str,
                                underlying: str,
                                expiry_date: str,
                                parse_contract: bool = True) -> int:
        """
        导入期权链数据（包含希腊字母）

        CSV格式示例:
        symbol,trade_date,open,high,low,close,settle,volume,amount,oi,iv,delta,gamma,theta,vega
        510050_C_2400_202412,2024-01-02,0.15,0.16,0.14,0.15,0.15,1000,15000,5000,0.25,0.55,0.001,-0.5,0.3
        """
        print(f"📥 导入期权链数据: {underlying} {expiry_date}")

        df = pd.read_csv(filepath)

        # 解析合约代码
        if parse_contract and 'symbol' in df.columns:
            contracts = []
            for symbol in df['symbol'].unique():
                contract_info = self._parse_option_symbol(symbol, underlying)
                if contract_info:
                    # 添加合约定义
                    db.add_option_contract(
                        symbol=symbol,
                        underlying_symbol=underlying,
                        option_type=contract_info['option_type'],
                        strike=contract_info['strike'],
                        expiry_date=contract_info['expiry_date']
                    )
                    contracts.append(symbol)

            print(f"   发现 {len(contracts)} 个合约")

        # 导入行情数据
        count = 0
        for symbol in tqdm(df['symbol'].unique(), desc="导入合约"):
            symbol_df = df[df['symbol'] == symbol].copy()
            count += db.import_option_bars(symbol_df, symbol)

        print(f"✅ 成功导入 {count} 条记录")
        return count

    def _parse_option_symbol(self, symbol: str, underlying: str) -> Optional[dict]:
        """
        解析期权合约代码
        支持格式:
        - 510050_C_2400_20241227 (标的_类型_行权价_到期日)
        - 510050C2400M02412 (SSE ETF期权标准格式)
        """
        try:
            # 格式1: 510050_C_2400_20241227
            if '_' in symbol:
                parts = symbol.split('_')
                if len(parts) >= 4:
                    option_type = parts[1].upper()
                    strike = float(parts[2])
                    expiry_str = parts[3]
                    expiry_date = datetime.strptime(expiry_str[:8], '%Y%m%d').date()
                    return {
                        'option_type': option_type,
                        'strike': strike,
                        'expiry_date': expiry_date
                    }

            # 格式2: 510050C2400M02412 (SSE标准格式)
            # 标的(6位) + 类型(C/P) + 行权价(4位) + M + 年月(4位)
            if len(symbol) >= 13:
                option_type = symbol[6].upper()
                strike = float(symbol[7:11])
                year = 2000 + int(symbol[12:14])
                month = int(symbol[14:16])
                # 到期日通常是该月第四个周三，简化处理取月末
                from calendar import monthrange
                _, last_day = monthrange(year, month)
                expiry_date = date(year, month, min(28, last_day))

                return {
                    'option_type': option_type,
                    'strike': strike,
                    'expiry_date': expiry_date
                }

        except Exception as e:
            print(f"   解析合约代码失败: {symbol}, {e}")

        return None

    # ========== 批量导入 ==========

    def batch_import_underlying(self,
                                data_dir: str,
                                pattern: str = "*.csv",
                                symbol_extractor: Optional[Callable] = None) -> dict:
        """
        批量导入标的目录下的所有数据文件

        Args:
            data_dir: 数据目录
            pattern: 文件匹配模式
            symbol_extractor: 从文件名提取标的代码的函数

        Returns:
            导入统计 {symbol: count}
        """
        data_path = Path(data_dir)
        if not data_path.exists():
            print(f"❌ 目录不存在: {data_dir}")
            return {}

        files = list(data_path.glob(pattern))
        print(f"📁 发现 {len(files)} 个数据文件")

        results = {}
        for filepath in files:
            # 默认从文件名提取标的代码
            if symbol_extractor:
                symbol = symbol_extractor(filepath.name)
            else:
                symbol = filepath.stem.split('_')[0]

            try:
                if filepath.suffix == '.csv':
                    count = self.import_underlying_from_csv(str(filepath), symbol)
                elif filepath.suffix == '.parquet':
                    count = self.import_underlying_from_parquet(str(filepath), symbol)
                else:
                    continue

                results[symbol] = count
            except Exception as e:
                print(f"❌ 导入失败 {filepath}: {e}")
                results[symbol] = 0

        return results

    def batch_import_options(self,
                            data_dir: str,
                            pattern: str = "*.csv") -> dict:
        """
        批量导入期权数据
        目录结构示例:
        data/options/
          ├── 510050/
          │   ├── 2024-12/
          │   │   └── chain_2024-12-27.csv
          │   └── 2025-01/
          │       └── chain_2025-01-22.csv
          └── 510300/
              └── ...
        """
        data_path = Path(data_dir)
        results = {}

        # 遍历标的目录
        for underlying_dir in data_path.iterdir():
            if not underlying_dir.is_dir():
                continue

            underlying = underlying_dir.name
            print(f"\n📂 处理标的: {underlying}")

            # 遍历到期月目录
            for month_dir in underlying_dir.iterdir():
                if not month_dir.is_dir():
                    continue

                # 查找数据文件
                for filepath in month_dir.glob(pattern):
                    try:
                        # 从目录名提取到期日
                        expiry_match = re.search(r'(\d{4}-\d{2})', month_dir.name)
                        if expiry_match:
                            expiry_str = expiry_match.group(1)
                            # 默认取该月第四个周三作为到期日
                            expiry_date = self._get_expiry_date(expiry_str)
                        else:
                            expiry_date = None

                        count = self.import_option_chain_csv(
                            str(filepath),
                            underlying,
                            str(expiry_date) if expiry_date else None
                        )

                        results[f"{underlying}_{expiry_str}"] = count

                    except Exception as e:
                        print(f"❌ 导入失败 {filepath}: {e}")

        return results

    def _get_expiry_date(self, year_month: str) -> date:
        """获取ETF期权的到期日（每月第四个周三）"""
        from calendar import monthcalendar, WEDNESDAY

        year, month = int(year_month[:4]), int(year_month[5:7])
        cal = monthcalendar(year, month)

        # 找第四个周三
        wednesdays = [week[WEDNESDAY] for week in cal if week[WEDNESDAY] != 0]
        if len(wednesdays) >= 4:
            return date(year, month, wednesdays[3])
        else:
            # 回退到月末
            from calendar import monthrange
            _, last_day = monthrange(year, month)
            return date(year, month, last_day)

    # ========== 数据导出 ==========

    def export_to_csv(self,
                     symbol: str,
                     start_date: str,
                     end_date: str,
                     output_path: str,
                     data_type: str = 'underlying'):
        """导出数据到CSV"""
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        if data_type == 'underlying':
            df = db.get_underlying_bars(symbol, start, end)
        else:
            df = db.get_option_bars(symbol, start, end)

        if df.empty:
            print(f"⚠️ 无数据可导出: {symbol}")
            return

        df.to_csv(output_path, index=False)
        print(f"✅ 导出完成: {output_path} ({len(df)} 条)")


# 便捷函数
def init_sample_data():
    """初始化示例数据（用于测试）"""
    importer = DataImporter()

    # 生成示例标的数据
    print("📝 生成示例数据...")

    dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')  # 工作日
    data = {
        'trade_date': dates,
        'open': [2.5 + i * 0.001 + (i % 5) * 0.01 for i in range(len(dates))],
        'high': [2.52 + i * 0.001 + (i % 5) * 0.01 for i in range(len(dates))],
        'low': [2.48 + i * 0.001 + (i % 5) * 0.01 for i in range(len(dates))],
        'close': [2.51 + i * 0.001 + (i % 5) * 0.01 for i in range(len(dates))],
        'volume': [1000000 + i * 1000 for i in range(len(dates))],
    }
    df = pd.DataFrame(data)

    # 保存并导入
    sample_dir = Path("./data/samples")
    sample_dir.mkdir(parents=True, exist_ok=True)

    csv_path = sample_dir / "510050_daily.csv"
    df.to_csv(csv_path, index=False)

    importer.import_underlying_from_csv(str(csv_path), "510050")

    print("✅ 示例数据初始化完成")


if __name__ == "__main__":
    # 测试
    init_sample_data()
