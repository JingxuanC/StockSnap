"""经典回测策略 — 每函数接收DataFrame+params，返回带signal列的DataFrame"""
import pandas as pd
import numpy as np

def _ema(s: pd.Series, n: int) -> pd.Series: return s.ewm(span=n, adjust=False).mean()

def ma_cross_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """双均线交叉: fast/slow 默认5/20"""
    fast, slow = int(params.get("fast", 5)), int(params.get("slow", 20))
    df = df.copy()
    df['ma_f'] = df['close'].rolling(fast).mean()
    df['ma_s'] = df['close'].rolling(slow).mean()
    buy = (df['ma_f'] > df['ma_s']) & (df['ma_f'].shift(1) <= df['ma_s'].shift(1))
    sell = (df['ma_f'] < df['ma_s']) & (df['ma_f'].shift(1) >= df['ma_s'].shift(1))
    df['signal'] = 0; df.loc[buy, 'signal'] = 1; df.loc[sell, 'signal'] = -1
    return df.drop(columns=['ma_f', 'ma_s'])

def macd_signal_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """MACD: fast/slow/signal 默认12/26/9"""
    f, s, sig = int(params.get("fast", 12)), int(params.get("slow", 26)), int(params.get("signal", 9))
    df = df.copy()
    macd = _ema(df['close'], f) - _ema(df['close'], s)
    sl = macd.ewm(span=sig, adjust=False).mean()
    buy = (macd > sl) & (macd.shift(1) <= sl.shift(1))
    sell = (macd < sl) & (macd.shift(1) >= sl.shift(1))
    df['signal'] = 0; df.loc[buy, 'signal'] = 1; df.loc[sell, 'signal'] = -1
    return df

def rsi_reversal_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """RSI超买超卖: period/oversold/overbought 默认14/30/70"""
    p, os, ob = int(params.get("period", 14)), int(params.get("oversold", 30)), int(params.get("overbought", 70))
    df = df.copy(); close = df['close']
    delta = close.diff(); gain = delta.where(delta > 0, 0.0).rolling(p).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(p).mean()
    rs = gain / loss.replace(0, np.nan); rsi = 100 - (100 / (1 + rs))
    buy = (rsi > os) & (rsi.shift(1) <= os)
    sell = (rsi < ob) & (rsi.shift(1) >= ob)
    df['signal'] = 0; df.loc[buy, 'signal'] = 1; df.loc[sell, 'signal'] = -1
    return df

def bollinger_breakout_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """布林带突破: period/std 默认20/2.0"""
    p, std = int(params.get("period", 20)), float(params.get("std", 2.0))
    df = df.copy(); close = df['close']
    mid = close.rolling(p).mean(); stdv = close.rolling(p).std(ddof=0)
    upper, lower = mid + std * stdv, mid - std * stdv
    buy = (close >= lower) & (close.shift(1) < lower.shift(1))
    sell = (close <= upper) & (close.shift(1) > upper.shift(1))
    df['signal'] = 0; df.loc[buy, 'signal'] = 1; df.loc[sell, 'signal'] = -1
    return df

def turtle_trend_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """海龟趋势-唐奇安通道: entry_period/exit_period 默认20/10"""
    ep, xp = int(params.get("entry_period", 20)), int(params.get("exit_period", 10))
    df = df.copy()
    entry_h = df['high'].rolling(ep).max()
    exit_l = df['low'].rolling(xp).min()
    buy = df['close'] > entry_h.shift(1)
    sell = df['close'] < exit_l.shift(1)
    df['signal'] = 0; df.loc[buy, 'signal'] = 1; df.loc[sell, 'signal'] = -1
    return df

STRATEGIES = {"ma_cross": ma_cross_signals, "macd_signal": macd_signal_signals,
              "rsi_reversal": rsi_reversal_signals, "bollinger_breakout": bollinger_breakout_signals,
              "turtle_trend": turtle_trend_signals}
