"""数据源异常定义"""

class DataSourceError(Exception):
    """数据源异常基类"""

class UnsupportedMarketError(DataSourceError):
    def __init__(self, market: str):
        super().__init__(f"不支持的市场类型: {market}")

class DataFetchError(DataSourceError):
    def __init__(self, source: str, symbol: str, detail: str = ""):
        detail_msg = f" ({detail})" if detail else ""
        super().__init__(f"[{source}] 获取 {symbol} 数据失败{detail_msg}")
