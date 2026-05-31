"""股票分析 API - 调用 StockAnalysisService"""
import logging
from datetime import date
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.db import execute_query, execute_insert, execute_update
from app.config.settings import settings

logger = logging.getLogger(__name__)
analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    data = request.get_json() or {}
    market = data.get('market', 'CN').strip()
    symbol = data.get('symbol', '').strip()
    if not symbol:
        return jsonify({'code': 400, 'msg': '请输入股票代码', 'data': None}), 400
    # 检查额度
    period = date.today().replace(day=1)
    quotas = execute_query("SELECT analysis_used, analysis_limit FROM user_quota WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    if quotas and quotas[0]['analysis_used'] >= quotas[0]['analysis_limit']:
        return jsonify({'code': 429, 'msg': '本月分析次数已用完', 'data': None}), 429
    # 执行分析
    try:
        from app.services.analysis import StockAnalysisService
        svc = StockAnalysisService()
        result = svc.analyze(market, symbol, language='zh-CN')
    except Exception as e:
        logger.error(f"分析失败 {symbol}: {e}")
        return jsonify({'code': 500, 'msg': f'分析失败: {e}', 'data': None}), 500
    # 保存记录
    record_id = execute_insert(
        "INSERT INTO analysis_records (user_id, market, symbol, company_name, report_json, report_markdown, score, rating, model) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (g.user_id, market, symbol, result.get('company', {}).get('name', symbol), __import__('json').dumps(result, ensure_ascii=False), result.get('report_markdown', ''), result['scores']['overall'], result['rating']['decision'], result.get('model', 'deepseek')))
    # 扣额度
    if not quotas:
        execute_insert("INSERT INTO user_quota (user_id, period_start, analysis_limit, analysis_used) VALUES (%s,%s,%s,1)", (g.user_id, period, settings.FREE_MONTHLY_QUOTA))
    else:
        execute_update("UPDATE user_quota SET analysis_used = analysis_used + 1 WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    result['record_id'] = record_id
    return jsonify({'code': 0, 'data': result})

@analysis_bp.route('/history', methods=['GET'])
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    size = request.args.get('page_size', 20, type=int)
    records = execute_query(
        "SELECT id, market, symbol, company_name, score, rating, created_at FROM analysis_records WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (g.user_id, size, (page - 1) * size))
    total = execute_query("SELECT COUNT(*) as cnt FROM analysis_records WHERE user_id = %s", (g.user_id,))
    return jsonify({'code': 0, 'data': {'records': records, 'total': total[0]['cnt'], 'page': page}})

@analysis_bp.route('/<int:record_id>', methods=['GET'])
@login_required
def detail(record_id):
    records = execute_query("SELECT * FROM analysis_records WHERE id = %s AND user_id = %s", (record_id, g.user_id))
    if not records:
        return jsonify({'code': 404, 'msg': '记录不存在', 'data': None}), 404
    return jsonify({'code': 0, 'data': records[0]})
