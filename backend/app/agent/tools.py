"""内置工具集 - Agent 可直接调用的股票分析工具"""
import json, logging
from app.agent.tool_registry import ToolRegistry, tool

logger = logging.getLogger(__name__)

# ==================== 数据类工具 ====================

@tool("search_stock", "搜索股票代码或名称，返回匹配的股票列表",
      {"type": "object", "properties": {"keyword": {"type": "string", "description": "搜索关键词，如茅台、AAPL、000001"},
       "market": {"type": "string", "enum": ["CN", "US"], "description": "市场，CN=A股 US=美股", "default": "CN"}},
       "required": ["keyword"]},
      tier="free", category="data")
def search_stock(keyword: str, market: str = "CN"):
    from app.data_sources.factory import DataSourceFactory
    source = DataSourceFactory.get_source(market)
    results = source.search_symbols(keyword)[:10]
    return {"found": len(results), "stocks": results}

@tool("get_kline", "获取股票K线数据，返回最近N日OHLCV",
      {"type": "object", "properties": {"symbol": {"type": "string", "description": "股票代码"},
       "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"},
       "timeframe": {"type": "string", "enum": ["1d", "1w", "1m"], "default": "1d"},
       "limit": {"type": "integer", "default": 60, "description": "返回K线数量"}},
       "required": ["symbol"]},
      tier="free", category="data")
def get_kline(symbol: str, market: str = "CN", timeframe: str = "1d", limit: int = 60):
    from app.data_sources.factory import DataSourceFactory
    source = DataSourceFactory.get_source(market)
    kline = source.get_kline(symbol, timeframe, limit)
    if kline is None or kline.data.empty:
        return {"error": "无数据"}
    df = kline.data.tail(min(limit, 20))
    closes = df['close'].tolist() if 'close' in df.columns else []
    return {"symbol": symbol, "timeframe": timeframe,
            "latest_close": closes[-1] if closes else 0,
            "recent_closes": [round(c, 2) for c in closes[-5:]] if len(closes) >= 5 else closes,
            "data_points": len(df)}

@tool("get_realtime", "获取股票实时行情",
      {"type": "object", "properties": {"symbol": {"type": "string"}, "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"}},
       "required": ["symbol"]},
      tier="free", category="data")
def get_realtime(symbol: str, market: str = "CN"):
    from app.data_sources.factory import DataSourceFactory
    source = DataSourceFactory.get_source(market)
    return source.get_realtime_price(symbol)

@tool("get_stock_info", "获取股票基本信息：公司名、行业、市值、PE、PB",
      {"type": "object", "properties": {"symbol": {"type": "string"}, "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"}},
       "required": ["symbol"]},
      tier="free", category="data")
def get_stock_info(symbol: str, market: str = "CN"):
    from app.data_sources.factory import DataSourceFactory
    source = DataSourceFactory.get_source(market)
    info = source.get_stock_info(symbol)
    return {"name": info.name, "sector": info.sector, "industry": info.industry,
            "market_cap": info.market_cap, "pe": info.pe_ratio, "pb": info.pb_ratio}

# ==================== 分析类工具 ====================

@tool("deep_analyze", "使用AI对股票进行深度基本面分析，返回投资论点/行业/催化剂/财报/估值/风险完整报告",
      {"type": "object", "properties": {"symbol": {"type": "string"}, "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"}},
       "required": ["symbol"]},
      tier="free", category="analysis")
def deep_analyze(symbol: str, market: str = "CN"):
    from app.services.analysis import StockAnalysisService
    svc = StockAnalysisService()
    result = svc.analyze(market, symbol)
    rating = result.get("rating", {})
    scores = result.get("scores", {})
    return {"symbol": symbol, "rating": rating.get("decision"), "confidence": rating.get("confidence"),
            "overall_score": scores.get("overall"), "summary": rating.get("summary", ""),
            "key_reasons": rating.get("key_reasons", []),
            "risks": [r.get("risk") if isinstance(r, dict) else r for r in result.get("risks", [])[:3]]}

@tool("technical_analyze", "快速技术分析：计算RSI/MACD/均线，评估趋势和买卖信号",
      {"type": "object", "properties": {"symbol": {"type": "string"}, "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"}},
       "required": ["symbol"]},
      tier="free", category="analysis")
def technical_analyze(symbol: str, market: str = "CN"):
    from app.data_sources.factory import DataSourceFactory
    source = DataSourceFactory.get_source(market)
    kline = source.get_kline(symbol, "1d", 120)
    if kline is None or kline.data.empty: return {"error": "无数据"}
    df = kline.data
    closes = df['close'].tolist()
    ma5 = sum(closes[-5:]) / 5; ma20 = sum(closes[-20:]) / 20; ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else ma20
    trend = "多头排列" if ma5 > ma20 > ma60 else ("空头排列" if ma5 < ma20 < ma60 else "震荡")
    # RSI
    rsi = 50; deltas = [closes[i]-closes[i-1] for i in range(1, len(closes))]
    gains = [max(d,0) for d in deltas[-14:]]; losses = [max(-d,0) for d in deltas[-14:]]
    avg_g = sum(gains)/14; avg_l = sum(losses)/14
    rsi = 100-(100/(1+avg_g/avg_l)) if avg_l > 0 else 100
    signal = "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性")
    return {"symbol": symbol, "latest": closes[-1], "ma5": round(ma5,2), "ma20": round(ma20,2),
            "trend": trend, "rsi_14": round(rsi,1), "rsi_signal": signal,
            "price_change_20d": f"{(closes[-1]/closes[-20]-1)*100:.1f}%" if len(closes) >= 20 else "N/A"}

# ==================== 回测类工具 (Pro) ====================

@tool("run_backtest", "运行策略回测，支持双均线/MACD/RSI/布林带/海龟五种策略",
      {"type": "object", "properties": {
          "symbol": {"type": "string"}, "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"},
          "strategy": {"type": "string", "enum": ["ma_cross", "macd_signal", "rsi_reversal", "bollinger_breakout", "turtle_trend"], "default": "ma_cross"},
          "days": {"type": "integer", "default": 250, "description": "回测天数"}},
       "required": ["symbol"]},
      tier="free", category="backtest")
def run_backtest(symbol: str, market: str = "CN", strategy: str = "ma_cross", days: int = 250):
    from datetime import datetime, timedelta
    from app.data_sources.factory import DataSourceFactory
    from app.services.backtest import BacktestService, BacktestConfig
    source = DataSourceFactory.get_source(market)
    kline = source.get_kline(symbol, "1d", days + 50)
    if kline is None or kline.data.empty: return {"error": "无K线数据"}
    cfg = BacktestConfig(market=market, symbol=symbol,
                         start_date=(datetime.now()-timedelta(days=days)).strftime('%Y-%m-%d'),
                         end_date=datetime.now().strftime('%Y-%m-%d'))
    svc = BacktestService()
    result = svc.run(cfg, strategy, kline.data)
    return {"symbol": symbol, "strategy": strategy,
            "total_return_pct": result.total_return_pct, "sharpe": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown_pct, "win_rate": result.win_rate,
            "total_trades": result.total_trades, "profit_factor": result.profit_factor}

# ==================== 新闻/舆情 (Pro) ====================

@tool("search_news", "搜索股票相关的最新新闻和公告",
      {"type": "object", "properties": {"symbol": {"type": "string"}, "market": {"type": "string", "enum": ["CN", "US"], "default": "CN"}},
       "required": ["symbol"]},
      tier="pro", category="news")
def search_news(symbol: str, market: str = "CN"):
    # 当前用WebSearch替代，后续接专业新闻API
    return {"message": f"新闻搜索功能开发中，请使用WebSearch获取{symbol}最新消息",
            "symbol": symbol, "status": "coming_soon"}

@tool("sector_overview", "获取行业板块概况，了解资金流向和板块热度",
      {"type": "object", "properties": {"market": {"type": "string", "enum": ["CN", "US"], "default": "CN"}},
       "required": []},
      tier="pro", category="news")
def sector_overview(market: str = "CN"):
    # A股板块数据，后续接stock-sdk-mcp的板块API
    return {"message": "板块概览功能开发中", "market": market, "status": "coming_soon"}

# 预注册，确保import时自动注册
def init_tools():
    """确保所有工具已注册（通过@tool装饰器自动完成）"""
    logger.info(f"已注册 {len(ToolRegistry._tools)} 个Agent工具: {list(ToolRegistry._tools.keys())}")
