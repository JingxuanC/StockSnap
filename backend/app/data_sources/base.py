"""数据源基类 - 统一接口和数据结构"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd


@dataclass
class KlineData:
    symbol: str
    timeframe: str
    data: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    start_time: str = ""
    end_time: str = ""


@dataclass
class StockInfo:
    symbol: str
    name: str
    market: str
    sector: str = ""
    industry: str = ""
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None


@dataclass
class FundamentalData:
    symbol: str
    revenue: List[float] = field(default_factory=list)
    net_profit: List[float] = field(default_factory=list)
    roe: float = 0.0
    debt_ratio: float = 0.0
    revenue_growth: float = 0.0
    profit_growth: float = 0.0


class BaseDataSource(ABC):
    name: str = "base"

    @abstractmethod
    def get_kline(self, symbol: str, timeframe: str = "1d", limit: int = 365) -> KlineData:
        ...

    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockInfo:
        ...

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> FundamentalData:
        ...

    @abstractmethod
    def get_realtime_price(self, symbol: str) -> dict:
        ...

    @abstractmethod
    def search_symbols(self, keyword: str) -> List[dict]:
        ...

    def normalize_symbol_code(self, symbol: str) -> str:
        return (symbol or "").strip().upper()
