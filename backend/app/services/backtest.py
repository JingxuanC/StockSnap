"""A股日线回测引擎 - 简化自QuantDinger，适配T+1"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
from app.services.backtest_strategies import STRATEGIES

@dataclass
class BacktestConfig:
    market: str = "CN"; symbol: str = ""; start_date: str = ""; end_date: str = ""
    initial_capital: float = 100000; commission: float = 0.0003
    stamp_duty: float = 0.0005; min_commission: float = 5; slippage: float = 0.001
@dataclass
class Trade:
    entry_date: str; entry_price: float; exit_date: str; exit_price: float
    shares: int; profit: float; profit_pct: float; commission_paid: float; exit_reason: str = "signal"
@dataclass
class BacktestResult:
    config: BacktestConfig; total_return_pct: float = 0; annualized_return: float = 0
    sharpe_ratio: float = 0; max_drawdown_pct: float = 0; win_rate: float = 0
    total_trades: int = 0; profit_factor: float = 0
    trades: List[Trade] = field(default_factory=list)
    equity_curve: list = field(default_factory=list); benchmark_curve: list = field(default_factory=list)

class BacktestService:
    STRATEGY_NAMES = {"ma_cross": "双均线", "macd_signal": "MACD", "rsi_reversal": "RSI",
                      "bollinger_breakout": "布林带", "turtle_trend": "海龟"}

    def run(self, config: BacktestConfig, strategy_name: str, kline_df: pd.DataFrame, params: dict = None) -> BacktestResult:
        df = kline_df.copy()
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']); df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        if config.start_date: df = df[df.index >= pd.Timestamp(config.start_date)]
        if config.end_date: df = df[df.index <= pd.Timestamp(config.end_date)]
        if len(df) < 30: return BacktestResult(config=config)

        fn = STRATEGIES.get(strategy_name)
        if not fn: raise ValueError(f"未知策略: {strategy_name}")
        df = fn(df, params or {})

        eq_curve, trades, total_comm = self._simulate(df, config)
        if not trades: return BacktestResult(config=config)
        metrics = self._calc_metrics(eq_curve, trades, config)
        benchmark = self._benchmark(df, config)

        trade_objs = [Trade(**t) for t in trades]
        return BacktestResult(config=config,
            total_return_pct=metrics['total_return_pct'], annualized_return=metrics['annualized_return'],
            sharpe_ratio=metrics['sharpe_ratio'], max_drawdown_pct=metrics['max_drawdown_pct'],
            win_rate=metrics['win_rate'], total_trades=metrics['total_trades'], profit_factor=metrics['profit_factor'],
            trades=trade_objs, equity_curve=eq_curve, benchmark_curve=benchmark)

    def _simulate(self, df, config):
        capital = config.initial_capital; position = 0; entry_price = 0.0; entry_date = None
        comm_total = 0.0; eq_curve = []; trades = []
        dates = df.index; closes = df['close'].values; signals = df['signal'].values if 'signal' in df.columns else np.zeros(len(df))

        for i in range(len(df)):
            ds = dates[i].strftime('%Y-%m-%d') if hasattr(dates[i], 'strftime') else str(dates[i])
            c = closes[i]
            # Sell
            if position > 0 and signals[i] == -1 and entry_date != ds:
                sp = c * (1 - config.slippage)
                gp = position * sp
                sc = max(gp * config.commission, config.min_commission) + gp * config.stamp_duty
                net = gp - sc; cb = position * entry_price
                profit = net - cb; profit_pct = (profit / cb) * 100 if cb > 0 else 0
                trades.append({"entry_date": entry_date, "entry_price": entry_price, "exit_date": ds,
                    "exit_price": sp, "shares": position, "profit": round(profit, 2),
                    "profit_pct": round(profit_pct, 2), "commission_paid": round(sc, 2)})
                comm_total += sc; capital += net; position = 0; entry_price = 0.0; entry_date = None
            # Buy
            if position == 0 and signals[i] == 1 and c > 0:
                bp = c * (1 + config.slippage)
                shares = int((capital * 0.98) / bp // 100 * 100)
                if shares >= 100:
                    gc = shares * bp; bc = max(gc * config.commission, config.min_commission)
                    tc = gc + bc
                    if tc <= capital:
                        comm_total += bc; capital -= tc; position = shares; entry_price = bp; entry_date = ds
            # Record equity
            eq = capital + (position * c if position > 0 else 0)
            eq_curve.append({"date": ds, "equity": round(eq, 2)})
        # Force close
        if position > 0:
            ds = dates[-1].strftime('%Y-%m-%d'); c = closes[-1]
            sp = c * (1 - config.slippage); gp = position * sp
            sc = max(gp * config.commission, config.min_commission) + gp * config.stamp_duty
            net = gp - sc; cb = position * entry_price
            profit = net - cb; profit_pct = (profit / cb) * 100 if cb > 0 else 0
            trades.append({"entry_date": entry_date, "entry_price": entry_price, "exit_date": ds,
                "exit_price": sp, "shares": position, "profit": round(profit, 2),
                "profit_pct": round(profit_pct, 2), "commission_paid": round(sc, 2), "exit_reason": "end"})
            capital += net
        return eq_curve, trades, comm_total

    def _calc_metrics(self, eq_curve, trades, config):
        if not eq_curve or not trades: return {"total_return_pct": 0, "annualized_return": 0, "sharpe_ratio": 0, "max_drawdown_pct": 0, "win_rate": 0, "total_trades": 0, "profit_factor": 0}
        final = eq_curve[-1]['equity']; total_pct = (final - config.initial_capital) / config.initial_capital * 100
        vals = [e['equity'] for e in eq_curve]; peak = vals[0]; max_dd = 0
        for v in vals:
            if v > peak: peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            if dd > max_dd: max_dd = dd
        # Sharpe
        rets = pd.Series(vals).pct_change().dropna(); rets = rets[np.isfinite(rets)]
        sharpe = (rets.mean() * 252 - 0.02) / (rets.std() * np.sqrt(252)) if len(rets) > 1 and rets.std() > 0 else 0
        # Win rate
        closing = [t for t in trades if t['profit'] != 0]; total = len(closing)
        wins = len([t for t in closing if t['profit'] > 0])
        wr = wins / total * 100 if total > 0 else 0
        tw = sum(t['profit'] for t in closing if t['profit'] > 0)
        tl = abs(sum(t['profit'] for t in closing if t['profit'] < 0))
        pf = tw / tl if tl > 0 else (tw if tw > 0 else 0)
        # Annualized
        try:
            start = datetime.strptime(eq_curve[0]['date'], '%Y-%m-%d')
            end = datetime.strptime(eq_curve[-1]['date'], '%Y-%m-%d')
            yrs = (end - start).days / 365
            ann = total_pct / yrs if yrs > 0 else 0
        except: ann = 0
        return {"total_return_pct": round(total_pct, 2), "annualized_return": round(ann, 2),
                "sharpe_ratio": round(max(sharpe, 0), 2), "max_drawdown_pct": round(max_dd, 2),
                "win_rate": round(wr, 2), "total_trades": total, "profit_factor": round(pf, 2)}

    def _benchmark(self, df, config):
        first_c = df['close'].iloc[0]; shares = int(config.initial_capital * 0.98 / first_c // 100 * 100) if first_c > 0 else 0
        curve = [{"date": (df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i])),
                   "equity": round(config.initial_capital - shares * first_c + shares * df['close'].iloc[i], 2)} for i in range(len(df))]
        return curve

    def result_to_dict(self, result: BacktestResult) -> dict:
        return {"symbol": result.config.symbol, "market": result.config.market,
                "startDate": result.config.start_date, "endDate": result.config.end_date,
                "totalReturnPct": result.total_return_pct, "annualizedReturn": result.annualized_return,
                "sharpeRatio": result.sharpe_ratio, "maxDrawdownPct": result.max_drawdown_pct,
                "winRate": result.win_rate, "totalTrades": result.total_trades, "profitFactor": result.profit_factor,
                "trades": [{"entryDate": t.entry_date, "entryPrice": t.entry_price, "exitDate": t.exit_date,
                            "exitPrice": t.exit_price, "shares": t.shares, "profit": t.profit,
                            "profitPct": t.profit_pct} for t in result.trades],
                "equityCurve": result.equity_curve, "benchmarkCurve": result.benchmark_curve}
