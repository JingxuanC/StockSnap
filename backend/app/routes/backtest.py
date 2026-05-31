"""回测 API - 调用 BacktestService"""
import json, logging
from datetime import date, datetime, timedelta
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.db import execute_query, execute_insert, get_db
from app.utils.rate_limiter import rate_limit
from app.config.settings import settings
from app.data_sources.factory import DataSourceFactory
from app.services.backtest import BacktestService, BacktestConfig

logger = logging.getLogger(__name__)
backtest_bp = Blueprint('backtest', __name__)

@backtest_bp.route('/run', methods=['POST'])
@login_required
@rate_limit(per_second=2, burst=5)  # 用户: 2次/秒, 突发5次
def run_backtest():
    data = request.get_json() or {}
    market = data.get('market', 'CN').strip()
    symbol = data.get('symbol', '').strip()
    strategy = data.get('strategy', 'ma_cross')
    if not symbol:
        return jsonify({'code': 400, 'msg': '请输入股票代码', 'data': None}), 400
    period = date.today().replace(day=1)
    # INSERT ON CONFLICT 防止并发竞态
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_quota (user_id, period_start, analysis_limit, analysis_used, backtest_limit, backtest_used) "
                        "VALUES (%s,%s,%s,0,%s,0) ON CONFLICT (user_id, period_start) DO NOTHING",
                        (g.user_id, period, settings.FREE_MONTHLY_QUOTA, settings.FREE_MONTHLY_QUOTA))
    quotas = execute_query("SELECT backtest_used, backtest_limit FROM user_quota WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    if not quotas:
        return jsonify({'code': 500, 'msg': '额度初始化失败', 'data': None}), 500
    if quotas[0]['backtest_used'] >= quotas[0]['backtest_limit']:
        return jsonify({'code': 429, 'msg': '本月回测次数已用完', 'data': None}), 429
    # 获取K线
    source = DataSourceFactory.get_source(market)
    kline = source.get_kline(symbol, "1d", 500)
    if kline is None or (hasattr(kline, 'data') and kline.data is not None and kline.data.empty):
        return jsonify({'code': 400, 'msg': '获取K线数据失败', 'data': None}), 400
    cfg = BacktestConfig(
        market=market, symbol=symbol,
        start_date=data.get('start_date', (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')),
        end_date=data.get('end_date', datetime.now().strftime('%Y-%m-%d')),
        initial_capital=float(data.get('initial_capital', 100000)))
    try:
        params = json.loads(data.get('params', '{}')) if isinstance(data.get('params'), str) else (data.get('params') or {})
    except (json.JSONDecodeError, TypeError):
        params = {}
    svc = BacktestService()
    result = svc.run(cfg, strategy, kline.data, params)
    result_dict = svc.result_to_dict(result)
    # 保存
    record_id = execute_insert(
        "INSERT INTO backtest_records (user_id, market, symbol, strategy_name, params_json, result_json, equity_curve_json) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (g.user_id, market, symbol, strategy, json.dumps(params), json.dumps(result_dict, ensure_ascii=False), json.dumps(result.equity_curve)))
    execute_query("UPDATE user_quota SET backtest_used = backtest_used + 1 WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    result_dict['record_id'] = record_id
    return jsonify({'code': 0, 'data': result_dict})

@backtest_bp.route('/records', methods=['GET'])
@login_required
def history():
    page = max(1, request.args.get('page', 1, type=int))
    size = min(100, max(1, request.args.get('page_size', 20, type=int)))
    records = execute_query("SELECT id, market, symbol, strategy_name, created_at FROM backtest_records WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s", (g.user_id, size, (page - 1) * size))
    total = execute_query("SELECT COUNT(*) as cnt FROM backtest_records WHERE user_id = %s", (g.user_id,))
    return jsonify({'code': 0, 'data': {'records': records, 'total': total[0]['cnt'] if total else 0, 'page': page, 'page_size': size}})

@backtest_bp.route('/strategies', methods=['GET'])
def strategies():
    return jsonify({'code': 0, 'data': [{'key': k, 'name': v} for k, v in BacktestService.STRATEGY_NAMES.items()]})
