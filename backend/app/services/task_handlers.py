"""异步任务处理器 - 被 task_queue worker 调用"""
import logging
from app.utils.task_queue import register_task

logger = logging.getLogger(__name__)

@register_task("stock_analysis")
def handle_stock_analysis(payload: dict) -> dict:
    """处理股票分析任务"""
    market = payload.get("market", "CN")
    symbol = payload.get("symbol", "")
    language = payload.get("language", "zh-CN")
    from app.services.analysis import StockAnalysisService
    svc = StockAnalysisService()
    result = svc.analyze(market, symbol, language)
    # 结果存 DB
    try:
        from app.utils.db import execute_insert
        execute_insert(
            "INSERT INTO analysis_records (user_id, market, symbol, company_name, report_json, report_markdown, score, rating, model) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (payload.get("user_id", 0), market, symbol,
             (result.get("company") or {}).get("name", symbol),
             __import__("json").dumps(result, ensure_ascii=False),
             result.get("report_markdown", ""),
             result["scores"]["overall"],
             (result.get("rating") or {}).get("decision", "HOLD"),
             result.get("model", "deepseek")))
    except Exception as e:
        logger.error(f"保存分析结果失败: {e}")
    return result

@register_task("stock_backtest")
def handle_stock_backtest(payload: dict) -> dict:
    """处理回测任务"""
    market = payload.get("market", "CN")
    symbol = payload.get("symbol", "")
    strategy = payload.get("strategy", "ma_cross")
    start_date = payload.get("start_date", "")
    end_date = payload.get("end_date", "")
    initial_capital = float(payload.get("initial_capital", 100000))
    params = payload.get("params") or {}
    if isinstance(params, str):
        try: params = __import__("json").loads(params)
        except: params = {}
    from app.data_sources.factory import DataSourceFactory
    from app.services.backtest import BacktestService, BacktestConfig
    source = DataSourceFactory.get_source(market)
    kline = source.get_kline(symbol, "1d", 500)
    cfg = BacktestConfig(market=market, symbol=symbol, start_date=start_date, end_date=end_date, initial_capital=initial_capital)
    svc = BacktestService()
    result = svc.run(cfg, strategy, kline.data, params)
    result_dict = svc.result_to_dict(result)
    try:
        from app.utils.db import execute_insert
        execute_insert(
            "INSERT INTO backtest_records (user_id, market, symbol, strategy_name, params_json, result_json, equity_curve_json) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (payload.get("user_id", 0), market, symbol, strategy,
             __import__("json").dumps(params), __import__("json").dumps(result_dict, ensure_ascii=False),
             __import__("json").dumps(result.equity_curve)))
    except Exception as e:
        logger.error(f"保存回测结果失败: {e}")
    return result_dict
