"""数据源工厂 - 根据市场类型返回数据源实例"""
from typing import Dict
from app.data_sources.base import BaseDataSource
from app.data_sources.errors import UnsupportedMarketError
import logging

logger = logging.getLogger(__name__)


class DataSourceFactory:
    _MARKET_ALIASES: Dict[str, str] = {
        "cn": "CN", "a": "CN", "ashare": "CN", "china": "CN",
        "us": "US", "usa": "US", "nyse": "US", "nasdaq": "US",
    }
    _SUPPORTED_MARKETS = ("CN", "US")
    _instances: Dict[str, BaseDataSource] = {}

    @classmethod
    def normalize_market(cls, market: str) -> str:
        raw = str(market).strip()
        if raw in cls._SUPPORTED_MARKETS:
            return raw
        alias = cls._MARKET_ALIASES.get(raw.lower().replace(" ", ""), None)
        if alias:
            return alias
        raise UnsupportedMarketError(raw)

    @classmethod
    def get_source(cls, market: str) -> BaseDataSource:
        key = cls.normalize_market(market)
        if key not in cls._instances:
            if key == "CN":
                from app.data_sources.cn_stock import CNStockDataSource
                cls._instances[key] = CNStockDataSource()
            elif key == "US":
                from app.data_sources.us_stock import USStockDataSource
                cls._instances[key] = USStockDataSource()
            logger.info("[DataSourceFactory] 创建 %s 数据源", key)
        return cls._instances[key]

    @classmethod
    def get_kline(cls, market, symbol, timeframe="1d", limit=365):
        return cls.get_source(market).get_kline(symbol, timeframe, limit)

    @classmethod
    def get_stock_info(cls, market, symbol):
        return cls.get_source(market).get_stock_info(symbol)

    @classmethod
    def get_fundamentals(cls, market, symbol):
        return cls.get_source(market).get_fundamentals(symbol)

    @classmethod
    def get_realtime_price(cls, market, symbol):
        return cls.get_source(market).get_realtime_price(symbol)

    @classmethod
    def search_symbols(cls, market, keyword):
        return cls.get_source(market).search_symbols(keyword)
