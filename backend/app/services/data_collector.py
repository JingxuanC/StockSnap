"""市场数据采集服务 - 采集行情/基本面/K线数据并格式化为LLM友好的文本"""
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.data_sources.factory import DataSourceFactory

logger = logging.getLogger(__name__)

class MarketDataCollector:
    def __init__(self):
        self.factory = DataSourceFactory

    def collect_all(self, market: str, symbol: str) -> Dict[str, Any]:
        source = self.factory.get_source(market)
        data = {"market": market, "symbol": symbol, "collected_at": datetime.now().isoformat(),
                "info": None, "fundamentals": None, "kline_daily": None, "kline_weekly": None, "realtime": None, "_errors": {}}
        for key, method in [("info", "get_stock_info"), ("fundamentals", "get_fundamentals"),
                            ("kline_daily", lambda: source.get_kline(symbol, "1d", 250)),
                            ("kline_weekly", lambda: source.get_kline(symbol, "1w", 52)),
                            ("realtime", "get_realtime_price")]:
            try:
                data[key] = method() if callable(method) else getattr(source, method)(symbol)
            except Exception as e:
                data["_errors"][key] = str(e)
        return data

    def format_for_llm(self, data: Dict) -> str:
        lines = [f"## 标的: {data['symbol']} ({data['market']})", f"数据时间: {data.get('collected_at', 'N/A')}", ""]
        info = data.get("info")
        if info:
            lines.extend(["### 公司信息", f"  名称: {getattr(info, 'name', 'N/A')}",
                          f"  行业: {getattr(info, 'industry', 'N/A')}",
                          f"  市值: {self._fmt(getattr(info, 'market_cap', 0))}",
                          f"  PE: {getattr(info, 'pe_ratio', 'N/A')}  PB: {getattr(info, 'pb_ratio', 'N/A')}", ""])
        rt = data.get("realtime")
        if rt and isinstance(rt, dict) and rt.get("price"):
            lines.extend(["### 实时行情", f"  价格: {rt.get('price')}",
                          f"  涨跌: {rt.get('change_percent', 0)}%",
                          f"  最高: {rt.get('high')}  最低: {rt.get('low')}", ""])
        kd = data.get("kline_daily")
        if kd is not None and hasattr(kd, 'data') and not kd.data.empty:
            df = kd.data.tail(20)
            closes = df['close'].tolist() if 'close' in df.columns else []
            if closes:
                lines.append(f"### 日线数据 (近{len(closes)}日)")
                lines.append(f"  最近收盘价: {closes[-1]}")
                if len(closes) >= 20:
                    lines.append(f"  MA5: {sum(closes[-5:])/5:.2f}  MA10: {sum(closes[-10:])/10:.2f}  MA20: {sum(closes[-20:])/20:.2f}")
                if len(closes) >= 15:
                    rsi = self._calc_rsi(closes, 14)
                    lines.append(f"  RSI(14): {rsi:.1f}")
                lines.append("")
        fd = data.get("fundamentals")
        if fd:
            lines.extend(["### 基本面",
                          f"  营收增长: {getattr(fd, 'revenue_growth', 0)}%",
                          f"  利润增长: {getattr(fd, 'profit_growth', 0)}%",
                          f"  ROE: {getattr(fd, 'roe', 0)}%", ""])
        return "\n".join(lines)

    @staticmethod
    def _fmt(v): return f"{v/1e8:.0f}亿" if abs(v) >= 1e8 else (f"{v/1e4:.0f}万" if abs(v) >= 1e4 else str(v))

    @staticmethod
    def _calc_rsi(prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1: return 50.0
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains, losses = [max(d, 0) for d in deltas], [max(-d, 0) for d in deltas]
        avg_gain, avg_loss = sum(gains[-period:]) / period, sum(losses[-period:]) / period
        if avg_loss == 0: return 100.0
        return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
