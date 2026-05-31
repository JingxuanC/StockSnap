"""A股数据源 - akshare主 + 东方财富HTTP降级"""
import os, re, time, logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import pandas as pd
import requests

from app.data_sources.base import BaseDataSource, KlineData, StockInfo, FundamentalData

logger = logging.getLogger(__name__)
_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")

@contextmanager
def _bypass_proxy():
    saved = {}
    for key in _PROXY_KEYS:
        val = os.environ.pop(key, None)
        if val is not None:
            saved[key] = val
    try:
        yield
    finally:
        for key, val in saved.items():
            os.environ[key] = val

def _normalize_a_code(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    s = re.sub(r'\.(SH|SZ|SS)$', '', s)
    s = re.sub(r'^(SH|SZ)', '', s)
    if s.isdigit() and len(s) == 6:
        return s
    return s.zfill(6) if s.isdigit() and len(s) < 6 else s

def _build_secid(symbol_6: str) -> str:
    flag = "1" if symbol_6.startswith("6") else "0"
    return f"{flag}.{symbol_6}"


class CNStockDataSource(BaseDataSource):
    name = "CNStock"

    def __init__(self):
        self._ak_ok = None

    def _has_akshare(self):
        if self._ak_ok is None:
            try:
                import akshare  # noqa
                self._ak_ok = True
            except ImportError:
                self._ak_ok = False
        return self._ak_ok

    # ---------- K线 ----------
    def get_kline(self, symbol: str, timeframe: str = "1d", limit: int = 365) -> KlineData:
        code = _normalize_a_code(symbol)
        tf = self._norm_tf(timeframe)
        if self._has_akshare():
            kd = self._ak_kline(code, tf, limit)
            if kd and not kd.data.empty:
                return kd
        return self._em_kline(code, tf, limit)

    def _norm_tf(self, tf):
        m = {"1d": "1D", "daily": "1D", "1w": "1W", "weekly": "1W", "1m": "1M", "monthly": "1M"}
        return m.get(tf.lower(), tf.upper())

    def _ak_kline(self, code, tf, limit):
        try:
            import akshare as ak
            period = {"1D": "daily", "1W": "weekly", "1M": "monthly"}.get(tf, "daily")
            with _bypass_proxy():
                df = ak.stock_zh_a_hist(symbol=code, period=period, start_date="19000101", end_date="20500101", adjust="qfq")
            if df is None or df.empty:
                return None
            df = df.rename(columns={"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
            df = df[["date", "open", "high", "low", "close", "volume"]].tail(limit)
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            return KlineData(symbol=code, timeframe=tf, data=df.reset_index(drop=True),
                             start_time=str(df["date"].iloc[0]), end_time=str(df["date"].iloc[-1]))
        except Exception as e:
            logger.debug("[CN] akshare K线失败 %s: %s", code, e)
            return None

    def _em_kline(self, code, tf, limit):
        try:
            secid = _build_secid(code)
            klt = {"1D": "101", "1W": "102", "1M": "103"}.get(tf, "101")
            resp = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get", params={
                "secid": secid, "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": klt, "fqt": "1", "end": "20500101", "lmt": limit,
            }, timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
            d = resp.json().get("data")
            if not d or not d.get("klines"):
                return KlineData(symbol=code, timeframe=tf)
            rows = []
            for line in d["klines"]:
                parts = str(line).split(",")
                if len(parts) >= 6:
                    rows.append({"date": parts[0], "open": float(parts[1]), "close": float(parts[2]),
                                 "high": float(parts[3]), "low": float(parts[4]), "volume": float(parts[5])})
            df = pd.DataFrame(rows)
            return KlineData(symbol=code, timeframe=tf, data=df,
                             start_time=rows[0]["date"] if rows else "", end_time=rows[-1]["date"] if rows else "")
        except Exception as e:
            logger.debug("[CN] 东方财富K线失败 %s: %s", code, e)
            return KlineData(symbol=code, timeframe=tf)

    # ---------- 股票信息 ----------
    def get_stock_info(self, symbol: str) -> StockInfo:
        code = _normalize_a_code(symbol)
        info = StockInfo(symbol=code, market="CN")
        if self._has_akshare():
            try:
                import akshare as ak
                with _bypass_proxy():
                    df = ak.stock_individual_info_em(symbol=code)
                if df is not None and not df.empty:
                    d = {}
                    for _, row in df.iterrows():
                        d[str(row.iloc[0]).strip()] = row.iloc[1]
                    info.name = str(d.get("股票名称", ""))
                    info.industry = str(d.get("行业", ""))
                    try: info.market_cap = float(d.get("总市值", 0) or 0)
                    except: pass
                    try: info.pe_ratio = float(d.get("市盈率-动态", ""))
                    except: pass
                    try: info.pb_ratio = float(d.get("市净率", ""))
                    except: pass
                    return info
            except Exception as e:
                logger.debug("[CN] akshare股票信息失败 %s: %s", code, e)
        return info

    # ---------- 基本面 ----------
    def get_fundamentals(self, symbol: str) -> FundamentalData:
        return FundamentalData(symbol=_normalize_a_code(symbol))

    # ---------- 实时行情 ----------
    def get_realtime_price(self, symbol: str) -> dict:
        code = _normalize_a_code(symbol)
        if self._has_akshare():
            try:
                import akshare as ak
                with _bypass_proxy():
                    df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    match = df[df["代码"].astype(str).str.zfill(6) == code]
                    if not match.empty:
                        r = match.iloc[0]
                        return {"price": float(r["最新价"]), "change": float(r.get("涨跌额", 0)),
                                "change_percent": float(r.get("涨跌幅", 0)), "high": float(r.get("最高", 0)),
                                "low": float(r.get("最低", 0)), "open": float(r.get("今开", 0)),
                                "volume": float(r.get("成交量", 0)), "name": str(r.get("名称", "")),
                                "symbol": code}
            except Exception as e:
                logger.debug("[CN] akshare实时行情失败 %s: %s", code, e)
        return {"price": 0, "symbol": code}

    # ---------- 搜索 ----------
    def search_symbols(self, keyword: str) -> List[dict]:
        if not keyword:
            return []
        if self._has_akshare():
            try:
                import akshare as ak
                with _bypass_proxy():
                    df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    kw = keyword.upper()
                    results = []
                    for _, row in df.iterrows():
                        code = str(row.get("代码", "")).strip().zfill(6)
                        name = str(row.get("名称", "")).strip()
                        if kw in code or kw in name.upper():
                            results.append({"symbol": code, "name": name, "market": "CN"})
                            if len(results) >= 20:
                                break
                    return results
            except Exception as e:
                logger.debug("[CN] 搜索失败: %s", e)
        return []
