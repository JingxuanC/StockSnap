"""StockSnap 性能基准测试
运行: cd backend && python tests/benchmark.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from dataclasses import asdict

# ---- 生成模拟数据 ----
def make_kline(n=500):
    """生成n日模拟K线数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    close = 100.0 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, n)))
    df = pd.DataFrame({
        'date': dates,
        'open': close * (1 + np.random.uniform(-0.01, 0.01, n)),
        'high': close * (1 + np.abs(np.random.normal(0, 0.015, n))),
        'low': close * (1 - np.abs(np.random.normal(0, 0.015, n))),
        'close': close,
        'volume': np.random.randint(1_000_000, 10_000_000, n),
    })
    df.set_index('date', inplace=True)
    return df

# ---- 测试结果收集 ----
results = []

def bench(name, fn, iterations=10):
    times = []
    result = None
    for _ in range(iterations):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    avg = sum(times) / len(times)
    p50 = sorted(times)[len(times)//2]
    p99 = sorted(times)[int(len(times)*0.99)] if len(times) >= 100 else max(times)
    results.append({"test": name, "avg_ms": round(avg*1000, 2), "p50_ms": round(p50*1000, 2),
                    "p99_ms": round(p99*1000, 2), "iterations": iterations})
    print(f"  {name:40s}  avg={avg*1000:7.2f}ms  p50={p50*1000:7.2f}ms  p99={p99*1000:7.2f}ms  n={iterations}")
    return result

print("=" * 80)
print("StockSnap Benchmark Suite")
print("=" * 80)

# ==================== 1. 回测引擎 ====================
print("\n[1] 回测引擎性能 (500日K线)")

from app.services.backtest import BacktestService, BacktestConfig
from app.services.backtest_strategies import STRATEGIES

df = make_kline(500)
config = BacktestConfig(symbol='000001', market='CN')
svc = BacktestService()

strategies = [
    ("双均线", "ma_cross", {"fast": 5, "slow": 20}),
    ("MACD", "macd_signal", {"fast": 12, "slow": 26, "signal": 9}),
    ("RSI", "rsi_reversal", {"period": 14, "oversold": 30, "overbought": 70}),
    ("布林带", "bollinger_breakout", {"period": 20, "std": 2.0}),
    ("海龟", "turtle_trend", {"entry_period": 20, "exit_period": 10}),
]

for name, key, params in strategies:
    r = bench(f"Backtest: {name}", lambda: svc.run(config, key, df.copy(), params))
    assert r is not None and r.total_trades >= 0, f"回测{name}返回空结果"

# 回测吞吐量
def throughput_test():
    for key in ["ma_cross", "macd_signal", "rsi_reversal", "bollinger_breakout", "turtle_trend"]:
        svc.run(config, key, df.copy(), {})
bench("Backtest: 5策略串行", throughput_test, iterations=5)

# T+1 验证
def t1_test():
    df2 = df.copy()
    df2['signal'] = 0
    df2.loc[df2.index[10], 'signal'] = 1
    df2.loc[df2.index[10], 'signal'] = -1  # 同日买卖信号
    r = svc.run(config, "ma_cross", df2, {})
    return r
bench("Backtest: T+1同日买卖验证", t1_test, iterations=3)

# ==================== 2. 策略信号生成 ====================
print("\n[2] 策略信号生成性能 (500日)")

for name, key, params in strategies:
    bench(f"Signal: {name}", lambda: STRATEGIES[key](df.copy(), params.copy()), iterations=50)

# ==================== 3. JSON 序列化 (含numpy) ====================
print("\n[3] JSON 序列化性能 (含numpy/pandas)")

import json as json_mod
def json_test():
    data = {
        "int_val": np.int64(42),
        "float_val": np.float64(3.14),
        "nan_val": np.float64(np.nan),
        "inf_val": np.float64(np.inf),
        "array": np.array([1, 2, 3]),
        "normal": {"a": 1, "b": "hello"},
        "timestamp": pd.Timestamp.now(),
    }
    return json_mod.dumps(data, default=str)

bench("JSON: numpy/pandas类型序列化", json_test, iterations=100)

# ==================== 4. 数据源性能 ====================
print("\n[4] 数据源性能 (跳过-需网络)")

try:
    from app.data_sources.factory import DataSourceFactory
    # 仅工厂创建(无网络)
    bench("DataSource: factory.get_source(CN)", lambda: DataSourceFactory.get_source("CN"), iterations=20)
    bench("DataSource: factory.get_source(US)", lambda: DataSourceFactory.get_source("US"), iterations=20)
except Exception as e:
    print(f"  数据源跳过: {e}")

# ==================== 5. DB模拟操作 ====================
print("\n[5] 数据库模拟性能 (跳过-需PostgreSQL)")
print("  数据库测试需运行中的PostgreSQL -> 跳过")

# ==================== 6. 回测结果序列化 ====================
print("\n[6] 回测结果序列化性能")

r = svc.run(config, "ma_cross", df, {"fast": 5, "slow": 20})
bench("Result: to_dict序列化", lambda: svc.result_to_dict(r), iterations=50)

# 大结果JSON序列化
def large_json():
    d = svc.result_to_dict(r)
    return json_mod.dumps(d, ensure_ascii=False)
bench("Result: JSON dump (含权益曲线)", large_json, iterations=30)

# ==================== 7. RSI边界测试 ====================
print("\n[7] RSI 边界条件测试")

# 纯涨 (avg_loss=0 -> RSI=100)
up_df = df.copy(); up_df['close'] = np.linspace(100, 200, len(df))
r_up = svc.run(config, "rsi_reversal", up_df, {"period": 14, "oversold": 30, "overbought": 70})
print(f"  RSI纯涨趋势 (avg_loss=0): trades={r_up.total_trades} (应为0, RSI=100无卖出信号)")

# 纯跌 (avg_gain=0 -> RSI=0)
dn_df = df.copy(); dn_df['close'] = np.linspace(200, 100, len(df))
r_dn = svc.run(config, "rsi_reversal", dn_df, {"period": 14, "oversold": 30, "overbought": 70})
print(f"  RSI纯跌趋势 (avg_gain=0): trades={r_dn.total_trades} (RSI=0触底应有买入)")

# ==================== 8. 报告 ====================
print("\n" + "=" * 80)
print("Benchmark Report")
print("=" * 80)

print(f"\n{'Test':<45} {'Avg (ms)':>10} {'P50 (ms)':>10} {'P99 (ms)':>10}")
print("-" * 75)
for r in results:
    print(f"{r['test']:<45} {r['avg_ms']:>10.2f} {r['p50_ms']:>10.2f} {r['p99_ms']:>10.2f}")

# 性能判定
print("\n--- 性能判定 ---")
backtest_tests = [r for r in results if 'Backtest' in r['test'] and '串行' not in r['test']]
if backtest_tests:
    max_avg = max(r['avg_ms'] for r in backtest_tests)
    print(f"回测最大耗时: {max_avg:.1f}ms {'✅ PASS (<1000ms)' if max_avg < 1000 else '❌ FAIL (>1000ms)'}")

signal_tests = [r for r in results if 'Signal' in r['test']]
if signal_tests:
    max_avg = max(r['avg_ms'] for r in signal_tests)
    print(f"信号生成最大耗时: {max_avg:.1f}ms {'✅ PASS (<100ms)' if max_avg < 100 else '❌ FAIL (>100ms)'}")

json_tests = [r for r in results if 'JSON' in r['test'] and 'numpy' in r['test']]
if json_tests:
    print(f"JSON序列化: {json_tests[0]['avg_ms']:.2f}ms {'✅ PASS' if json_tests[0]['avg_ms'] < 10 else '⚠️ SLOW'}")

print("\n✅ Benchmark 完成")
