"""美股数据源 - yfinance"""
import time, logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

from app.data_sources.base import BaseDataSource, KlineData, StockInfo, FundamentalData

logger = logging.getLogger(__name__)

_INTERVAL_MAP = {"1d": "1d", "1D": "1d", "1w": "1wk", "1W": "1wk", "1m": "1mo", "1M": "1mo"}


class USStockDataSource(BaseDataSource):
    name = "USStock"

    def get_kline(self, symbol: str, timeframe: str = "1d", limit: int = 365) -> KlineData:
        sym = (symbol or "").strip().upper()
        tf = self._norm_tf(timeframe)
        try:
            import yfinance as yf
            interval = _INTERVAL_MAP.get(tf, "1d")
            days = max(limit + 30, 100)
            end = datetime.now()
            start = end - timedelta(days=days)
            ticker = yf.Ticker(sym)
            df = ticker.history(start=start.strftime("%Y-%m-%d"), end=(end + timedelta(days=1)).strftime("%Y-%m-%d"), interval=interval)
            if df is None or df.empty:
                return KlineData(symbol=sym, timeframe=tf)
            df = df.reset_index()
            time_col = "Date" if "Date" in df.columns else df.columns[0]
            df["date"] = df[time_col].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x))
            df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
            df = df[["date", "open", "high", "low", "close", "volume"]].tail(limit)
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            return KlineData(symbol=sym, timeframe=tf, data=df.reset_index(drop=True),
                             start_time=df["date"].iloc[0] if not df.empty else "",
                             end_time=df["date"].iloc[-1] if not df.empty else "")
        except ImportError:
            logger.error("[US] yfinance 未安装")
            return KlineData(symbol=sym, timeframe=tf)
        except Exception as e:
            logger.error("[US] K线失败 %s: %s", sym, e)
            return KlineData(symbol=sym, timeframe=tf)

    def _norm_tf(self, tf):
        m = {"1d": "1D", "daily": "1D", "1w": "1W", "weekly": "1W", "1m": "1M", "monthly": "1M"}
        return m.get(tf.lower(), tf.upper())

    def get_stock_info(self, symbol: str) -> StockInfo:
        sym = (symbol or "").strip().upper()
        info = StockInfo(symbol=sym, market="US")
        try:
            import yfinance as yf
            ticker = yf.Ticker(sym)
            raw = ticker.info
            if raw:
                info.name = str(raw.get("longName") or raw.get("shortName") or "")
                info.sector = str(raw.get("sector") or "")
                info.industry = str(raw.get("industry") or "")
                try: info.market_cap = float(raw.get("marketCap") or 0)
                except: pass
                try: info.pe_ratio = float(raw.get("trailingPE") or raw.get("forwardPE") or 0)
                except: pass
                try: info.pb_ratio = float(raw.get("priceToBook") or 0)
                except: pass
        except Exception as e:
            logger.debug("[US] 股票信息失败 %s: %s", sym, e)
        return info

    def get_fundamentals(self, symbol: str) -> FundamentalData:
        sym = (symbol or "").strip().upper()
        fd = FundamentalData(symbol=sym)
        try:
            import yfinance as yf
            ticker = yf.Ticker(sym)
            qf = ticker.quarterly_financials
            if qf is not None and not qf.empty:
                for col in qf.columns[:4]:
                    try:
                        fd.revenue.append(float(qf.loc["Total Revenue", col]) if "Total Revenue" in qf.index else 0)
                        fd.net_profit.append(float(qf.loc["Net Income", col]) if "Net Income" in qf.index else 0)
                    except: pass
                if len(fd.revenue) >= 2 and fd.revenue[-1] != 0:
                    fd.revenue_growth = round((fd.revenue[0] - fd.revenue[-1]) / abs(fd.revenue[-1]) * 100, 2)
                if len(fd.net_profit) >= 2 and fd.net_profit[-1] != 0:
                    fd.profit_growth = round((fd.net_profit[0] - fd.net_profit[-1]) / abs(fd.net_profit[-1]) * 100, 2)
            info = ticker.info
            if info and info.get("returnOnEquity"):
                try: fd.roe = round(float(info["returnOnEquity"]) * 100, 2)
                except: pass
        except Exception as e:
            logger.debug("[US] 基本面失败 %s: %s", sym, e)
        return fd

    def get_realtime_price(self, symbol: str) -> dict:
        sym = (symbol or "").strip().upper()
        try:
            import yfinance as yf
            ticker = yf.Ticker(sym)
            fi = ticker.fast_info
            price = getattr(fi, "lastPrice", 0) or 0
            prev = getattr(fi, "previousClose", price) or price
            return {"price": float(price), "change": round(price - prev, 4) if prev else 0,
                    "change_percent": round((price - prev) / prev * 100, 2) if prev else 0,
                    "high": float(getattr(fi, "dayHigh", price) or price),
                    "low": float(getattr(fi, "dayLow", price) or price),
                    "open": float(getattr(fi, "open", price) or price),
                    "volume": float(getattr(fi, "lastVolume", 0) or 0),
                    "symbol": sym}
        except Exception as e:
            logger.debug("[US] 实时行情失败 %s: %s", sym, e)
            return {"price": 0, "symbol": sym}

    def search_symbols(self, keyword: str) -> List[dict]:
        if not keyword:
            return []
        keyword = keyword.strip().upper()
        try:
            import yfinance as yf
            search = yf.Search(keyword, max_results=20)
            results = []
            for q in (getattr(search, "quotes", []) or []):
                if isinstance(q, dict):
                    results.append({"symbol": str(q.get("symbol", "")).upper(),
                                    "name": str(q.get("shortname", "")), "market": "US"})
            return results
        except:
            return []
