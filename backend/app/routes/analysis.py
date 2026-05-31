"""股票分析 API - 调用 StockAnalysisService"""
import json, logging
from datetime import date
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.db import execute_query, execute_insert, get_db
from app.utils.rate_limiter import rate_limit
from app.config.settings import settings
from app.services.analysis import StockAnalysisService

logger = logging.getLogger(__name__)
analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/analyze', methods=['POST'])
@login_required
@rate_limit(per_second=1, burst=3)  # 用户: 1次/秒, 突发3次
def analyze():
    data = request.get_json() or {}
    market = data.get('market', 'CN').strip()
    symbol = data.get('symbol', '').strip()
    if not symbol:
        return jsonify({'code': 400, 'msg': '请输入股票代码', 'data': None}), 400
    period = date.today().replace(day=1)
    # INSERT ON CONFLICT 防止并发竞态
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_quota (user_id, period_start, analysis_limit, analysis_used, backtest_limit, backtest_used) "
                        "VALUES (%s,%s,%s,0,%s,0) ON CONFLICT (user_id, period_start) DO NOTHING",
                        (g.user_id, period, settings.FREE_MONTHLY_QUOTA, settings.FREE_MONTHLY_QUOTA))
    quotas = execute_query("SELECT analysis_used, analysis_limit FROM user_quota WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    if not quotas:
        return jsonify({'code': 500, 'msg': '额度初始化失败', 'data': None}), 500
    if quotas[0]['analysis_used'] >= quotas[0]['analysis_limit']:
        return jsonify({'code': 429, 'msg': '本月分析次数已用完', 'data': None}), 429
    # 执行分析
    try:
        svc = StockAnalysisService()
        result = svc.analyze(market, symbol, language='zh-CN')
    except Exception as e:
        logger.error(f"分析失败 {symbol}: {e}")
        return jsonify({'code': 500, 'msg': '分析服务暂时不可用，请稍后重试', 'data': None}), 500
    # 保存记录
    company_name = (result.get('company') or {}).get('name', symbol) if isinstance(result.get('company'), dict) else symbol
    rating = (result.get('rating') or {})
    record_id = execute_insert(
        "INSERT INTO analysis_records (user_id, market, symbol, company_name, report_json, report_markdown, score, rating, model) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (g.user_id, market, symbol, company_name, json.dumps(result, ensure_ascii=False),
         result.get('report_markdown', ''), result['scores']['overall'], rating.get('decision', 'HOLD'), result.get('model', 'deepseek')))
    # 扣额度
    execute_query("UPDATE user_quota SET analysis_used = analysis_used + 1 WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    result['record_id'] = record_id
    return jsonify({'code': 0, 'data': result})

@analysis_bp.route('/history', methods=['GET'])
@login_required
def history():
    page = max(1, request.args.get('page', 1, type=int))
    size = min(100, max(1, request.args.get('page_size', 20, type=int)))
    records = execute_query(
        "SELECT id, market, symbol, company_name, score, rating, created_at FROM analysis_records WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (g.user_id, size, (page - 1) * size))
    total = execute_query("SELECT COUNT(*) as cnt FROM analysis_records WHERE user_id = %s", (g.user_id,))
    return jsonify({'code': 0, 'data': {'records': records, 'total': total[0]['cnt'] if total else 0, 'page': page, 'page_size': size}})

@analysis_bp.route('/<int:record_id>', methods=['GET'])
@login_required
def detail(record_id):
    records = execute_query("SELECT * FROM analysis_records WHERE id = %s AND user_id = %s", (record_id, g.user_id))
    if not records:
        return jsonify({'code': 404, 'msg': '记录不存在', 'data': None}), 404
    return jsonify({'code': 0, 'data': records[0]})

# ---- 异步分析（消息队列）----

@analysis_bp.route('/analyze-async', methods=['POST'])
@login_required
@rate_limit(per_second=2, burst=5)
def analyze_async():
    """提交异步分析任务，立即返回 task_id"""
    data = request.get_json() or {}
    market = data.get('market', 'CN').strip()
    symbol = data.get('symbol', '').strip()
    if not symbol:
        return jsonify({'code': 400, 'msg': '请输入股票代码', 'data': None}), 400
    # 额度检查
    period = date.today().replace(day=1)
    quotas = execute_query("SELECT analysis_used, analysis_limit FROM user_quota WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    if quotas and quotas[0]['analysis_used'] >= quotas[0]['analysis_limit']:
        return jsonify({'code': 429, 'msg': '本月分析次数已用完', 'data': None}), 429
    if not quotas:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO user_quota (user_id, period_start, analysis_limit, analysis_used, backtest_limit, backtest_used) "
                            "VALUES (%s,%s,%s,0,%s,0) ON CONFLICT (user_id, period_start) DO NOTHING",
                            (g.user_id, period, settings.FREE_MONTHLY_QUOTA, settings.FREE_MONTHLY_QUOTA))
    # 扣额度(预扣)
    execute_query("UPDATE user_quota SET analysis_used = analysis_used + 1 WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    # 入队
    from app.utils.task_queue import enqueue
    task_id = enqueue("stock_analysis", {"market": market, "symbol": symbol, "user_id": g.user_id, "language": "zh-CN"})
    return jsonify({'code': 0, 'data': {'task_id': task_id, 'status': 'pending', 'msg': '任务已提交，请轮询 /api/analysis/task/<task_id>'}})

@analysis_bp.route('/task/<task_id>', methods=['GET'])
@login_required
def task_status(task_id):
    """查询异步任务状态"""
    from app.utils.task_queue import get_task
    task = get_task(task_id)
    if not task:
        return jsonify({'code': 404, 'msg': '任务不存在或已过期', 'data': None}), 404
    return jsonify({'code': 0, 'data': task})
