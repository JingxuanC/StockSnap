"""订阅与额度管理 API"""
import logging
from datetime import date
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.db import execute_query, execute_insert, execute_update

logger = logging.getLogger(__name__)
subscription_bp = Blueprint('subscription', __name__)

PLANS = {'monthly': {'name': '月度会员', 'price': 29, 'days': 30, 'analysis': 200, 'backtest': 200},
         'yearly': {'name': '年度会员', 'price': 199, 'days': 365, 'analysis': 200, 'backtest': 200}}
FREE_LIMIT = 20

@subscription_bp.route('/quota', methods=['GET'])
@login_required
def quota():
    period = date.today().replace(day=1)
    q = execute_query("SELECT analysis_used, analysis_limit, backtest_used, backtest_limit FROM user_quota WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    u = execute_query("SELECT is_subscribed, subscription_expires_at FROM users WHERE id = %s", (g.user_id,))
    sub = bool(u[0].get('is_subscribed')) if u else False
    if q:
        d = q[0]
        return jsonify({'code': 0, 'data': {'analysis_used': d['analysis_used'], 'analysis_limit': d['analysis_limit'], 'analysis_remaining': max(0, d['analysis_limit'] - d['analysis_used']), 'backtest_used': d['backtest_used'], 'backtest_limit': d['backtest_limit'], 'backtest_remaining': max(0, d['backtest_limit'] - d['backtest_used']), 'is_subscribed': sub}})
    return jsonify({'code': 0, 'data': {'analysis_used': 0, 'analysis_limit': FREE_LIMIT, 'analysis_remaining': FREE_LIMIT, 'backtest_used': 0, 'backtest_limit': FREE_LIMIT, 'backtest_remaining': FREE_LIMIT, 'is_subscribed': sub}})

@subscription_bp.route('/plans', methods=['GET'])
def plans():
    pl = [{'id': k, **v} for k, v in PLANS.items()]
    return jsonify({'code': 0, 'data': {'plans': pl, 'free_limit': FREE_LIMIT}})

@subscription_bp.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json() or {}
    plan_id = data.get('plan_id', 'monthly').strip()
    if plan_id not in PLANS:
        return jsonify({'code': 400, 'msg': '无效套餐', 'data': None}), 400
    plan = PLANS[plan_id]
    from datetime import datetime, timedelta
    oid = execute_insert("INSERT INTO subscription_orders (user_id, order_type, amount, status, paid_at, expires_at) VALUES (%s,%s,%s,'paid',NOW(),%s) RETURNING id",
                         (g.user_id, plan_id, plan['price'], datetime.now() + timedelta(days=plan['days'])))
    execute_update("UPDATE users SET is_subscribed = TRUE, subscription_expires_at = %s WHERE id = %s",
                   (datetime.now() + timedelta(days=plan['days']), g.user_id))
    execute_update("UPDATE user_quota SET analysis_limit = %s, backtest_limit = %s WHERE user_id = %s AND period_start = %s",
                   (plan['analysis'], plan['backtest'], g.user_id, date.today().replace(day=1)))
    return jsonify({'code': 0, 'data': {'order_id': oid, 'plan': plan['name'], 'msg': '订阅已激活'}})
