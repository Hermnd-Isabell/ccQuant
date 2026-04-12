#!/usr/bin/env python3
"""
测试50ETF数据导入
"""

import sys
sys.path.insert(0, 'D:\\vnpy-4.3.0')

from ccquant.data_import import DataImporter
from ccquant.database import db

def import_50etf_data(filepath: str):
    """导入50ETF期权数据"""
    importer = DataImporter()

    print(f"导入文件: {filepath}")
    print("=" * 50)

    try:
        # 导入标的数据
        count = importer.import_underlying_from_csv(
            filepath=filepath,
            symbol="510050",
            date_col="date",  # 假设列名是date
        )
        print(f"✅ 成功导入 {count} 条记录")

        # 验证导入
        from datetime import date
        df = db.get_underlying_bars("510050", date(2020, 1, 1), date(2025, 12, 31))
        print(f"\n数据库验证: 共 {len(df)} 条记录")
        if not df.empty:
            print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
            print(f"\n前5条记录:")
            print(df.head())

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 请修改为你的文件路径
    filepath = input("请输入50ETF数据文件路径: ").strip()
    if filepath:
        import_50etf_data(filepath)
    else:
        print("未提供文件路径")
