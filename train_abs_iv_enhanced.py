# -*- coding: utf-8 -*-
"""
用 Diffusion 增强数据集重新训练端到端绝对 IV 模型（model_abs_iv.pkl）。

逻辑：
  1. 加载 IV_Predict/data/enhanced_dataset_v2.pkl（真实 + Diffusion 合成样本）
  2. 目标变量：next_implc_volatlty（T+1 绝对 IV）
  3. 特征：26 维 FEATURE_COLS（与策略 A 完全一致）
  4. 训练 XGBoost，使用 sample_weight（真实=1.0，合成=0.3）
  5. 时间划分：Train(<=20240630) / Val(20240701~20241231) / Test(>=20250101)
  6. 覆盖保存到 strategy/data/output/baseline_xgb/model_abs_iv.pkl
"""

from __future__ import annotations

import os
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb

# ------------------------------------------------------------------
# 常量
# ------------------------------------------------------------------

# 必须与 data_loader.py 完全一致
FEATURE_COLS = [
    'moneyness', 'moneyness_squared', 'remaining_time', 'call_put_flag',
    'exercise_price', 'moneyness_remaining_time',
    'fund_return', 'fund_volume', 'fund_high_low_ratio', 'fund_amount',
    'iv_t', 'iv_t_1', 'iv_t_2', 'iv_t_3', 'iv_t_4',
    'iv_ma5', 'iv_std5', 'iv_trend5', 'days_gap',
    'atm_iv_call_lag1', 'iv_mean_all_lag1', 'iv_std_all_lag1',
    'iv_max_all_lag1', 'iv_min_all_lag1', 'iv_vs_atm_lag1',
    'ten_year',
]

TRAIN_END = 20240630
VAL_END = 20241231

ENHANCED_PATH = os.path.join('IV_Predict', 'data', 'enhanced_dataset_v2.pkl')
OUTPUT_DIR = os.path.join('strategy', 'data', 'output', 'baseline_xgb')
OUTPUT_MODEL = os.path.join(OUTPUT_DIR, 'model_abs_iv.pkl')


def load_enhanced_data(path: str) -> pd.DataFrame:
    """加载增强数据集。"""
    print(f"[Load] 加载增强数据集: {path}")
    with open(path, 'rb') as f:
        data = pickle.load(f)
    df = data['df']
    print(f"  - 总样本: {len(df)}, 真实: {(df['is_synthetic']==False).sum()}, "
          f"合成: {(df['is_synthetic']==True).sum()}")
    return df


def temporal_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """按时间划分训练/验证/测试集。"""
    train_df = df[df['trade_date'] <= TRAIN_END].copy()
    val_df = df[(df['trade_date'] > TRAIN_END) & (df['trade_date'] <= VAL_END)].copy()
    test_df = df[df['trade_date'] > VAL_END].copy()
    return train_df, val_df, test_df


def extract_xy(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """提取特征 X、目标 y、权重 w。"""
    X = df[FEATURE_COLS].values.astype(np.float64)
    y = df['next_implc_volatlty'].values.astype(np.float64)
    w = df['sample_weight'].values.astype(np.float64)
    return X, y, w


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    w_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> xgb.XGBRegressor:
    """训练 XGBoost 模型（带早停）。"""
    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:squarederror',
        eval_metric='rmse',
        random_state=42,
        n_jobs=-1,
        callbacks=[xgb.callback.EarlyStopping(rounds=50, save_best=True)],
    )

    model.fit(
        X_train, y_train,
        sample_weight=w_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    return model


def evaluate(
    model: xgb.XGBRegressor,
    X: np.ndarray,
    y: np.ndarray,
    iv_t: np.ndarray,
    label: str = "",
) -> dict:
    """评估模型。"""
    pred = model.predict(X)

    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    mae = float(mean_absolute_error(y, pred))
    r2 = float(r2_score(y, pred))
    direction_acc = float(np.mean(np.sign(pred - iv_t) == np.sign(y - iv_t)))

    print(f"  [{label}] RMSE={rmse:.6f} MAE={mae:.6f} R2={r2:.4f} DirAcc={direction_acc:.4f}")

    return {
        'rmse': rmse,
        'mae': mae,
        'r2': r2,
        'direction_acc': direction_acc,
    }


def main() -> None:
    print("=" * 60)
    print("[Train Abs IV with Diffusion Enhanced Data]")
    print("=" * 60)

    # 1. 加载数据
    df = load_enhanced_data(ENHANCED_PATH)

    # 2. 过滤掉目标变量缺失的行
    df = df.dropna(subset=['next_implc_volatlty'] + FEATURE_COLS).copy()
    print(f"[Filter] 有效样本: {len(df)}")

    # 3. 时间划分
    train_df, val_df, test_df = temporal_split(df)
    print(f"[Split] Train={len(train_df)} Val={len(val_df)} Test={len(test_df)}")

    # 4. 提取特征
    X_train, y_train, w_train = extract_xy(train_df)
    X_val, y_val, w_val = extract_xy(val_df)
    X_test, y_test, w_test = extract_xy(test_df)

    print(f"[Features] dim={len(FEATURE_COLS)}")
    print(f"[Target] next_implc_volatlty: mean={y_train.mean():.6f} std={y_train.std():.6f}")

    # 5. 训练
    print("\n[Train] 开始训练 XGBoost...")
    model = train_model(X_train, y_train, w_train, X_val, y_val)
    print(f"[Train] 最优迭代轮数: {model.best_iteration}")

    # 6. 评估
    print("\n[Evaluate]")
    metrics_train = evaluate(model, X_train, y_train, train_df['implc_volatlty'].values, "Train")
    metrics_val = evaluate(model, X_val, y_val, val_df['implc_volatlty'].values, "Val")
    metrics_test = evaluate(model, X_test, y_test, test_df['implc_volatlty'].values, "Test")

    # 7. 特征重要性
    fi = pd.DataFrame({
        'feature': FEATURE_COLS,
        'importance': model.feature_importances_,
    }).sort_values('importance', ascending=False).reset_index(drop=True)
    print(f"\n[Feature Importance] Top 5: {fi['feature'].head(5).tolist()}")

    # 8. 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_MODEL, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n[Save] 模型已保存: {OUTPUT_MODEL}")

    # 保存特征重要性
    fi_path = os.path.join(OUTPUT_DIR, 'feature_importance_abs_iv_enhanced.csv')
    fi.to_csv(fi_path, index=False)
    print(f"[Save] 特征重要性已保存: {fi_path}")

    # 保存指标
    metrics = {
        'train': metrics_train,
        'val': metrics_val,
        'test': metrics_test,
        'feature_importance_top5': fi.head(5).to_dict(orient='records'),
        'model_info': {
            'best_iteration': int(model.best_iteration),
            'n_features': len(FEATURE_COLS),
            'n_train': len(train_df),
            'n_synthetic_train': int((train_df['is_synthetic']==True).sum()),
            'target': 'next_implc_volatlty',
        }
    }
    metrics_path = os.path.join(OUTPUT_DIR, 'metrics_abs_iv_enhanced.json')
    import json
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"[Save] 指标已保存: {metrics_path}")

    print("\n" + "=" * 60)
    print("[Done] 增强数据模型训练完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
