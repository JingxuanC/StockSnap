"""订阅与额度管理 API"""
import logging
from datetime import date, datetime, timedelta
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.db import execute_query, execute_insert, execute_update, get_db

logger = logging.getLogger(__name__)
subscription_bp = Blueprint('subscription', __name__)

PLANS = {'monthly': {'name': '月度会员', 'price': 29, 'days': 30, 'analysis': 200, 'backtest': 200},
         'yearly': {'name': '年度会员', 'price': 199, 'days': 365, 'analysis': 200, 'backtest': 200}}
FREE_LIMIT = 20

def _get_user_limits(user_id):
    """获取用户当前额度上限（检查订阅过期）"""
    u = execute_query("SELECT is_subscribed, subscription_expires_at FROM users WHERE id = %s", (user_id,))
    if not u:
        return FREE_LIMIT, FREE_LIMIT
    user = u[0]
    if user.get('is_subscribed') and user.get('subscription_expires_at'):
        expires = user['subscription_expires_at']
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if expires.replace(tzinfo=None) > datetime.now():
            plan_name = user.get('subscription_plan', 'monthly') if hasattr(user, 'get') else 'monthly'
            return PLANS.get('monthly', {}).get('analysis', 200), PLANS.get('monthly', {}).get('backtest', 200)
    return FREE_LIMIT, FREE_LIMIT

@subscription_bp.route('/quota', methods=['GET'])
@login_required
def quota():
    period = date.today().replace(day=1)
    al, bl = _get_user_limits(g.user_id)
    q = execute_query("SELECT analysis_used, backtest_used FROM user_quota WHERE user_id = %s AND period_start = %s", (g.user_id, period))
    au, bu = (q[0]['analysis_used'], q[0]['backtest_used']) if q else (0, 0)
    u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
    sub = bool(u[0].get('is_subscribed')) if u else False
    return jsonify({'code': 0, 'data': {'analysis_used': au, 'analysis_limit': al, 'analysis_remaining': max(0, al - au),
        'backtest_used': bu, 'backtest_limit': bl, 'backtest_remaining': max(0, bl - bu), 'is_subscribed': sub}})

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
    now = datetime.now()
    # 续费叠加：从max(当前到期时间, now)开始计算
    u = execute_query("SELECT subscription_expires_at FROM users WHERE id = %s", (g.user_id,))
    current_expiry = u[0].get('subscription_expires_at') if u else None
    base = now
    if current_expiry:
        if isinstance(current_expiry, str):
            current_expiry = datetime.fromisoformat(current_expiry.replace('Z', '+00:00'))
        if current_expiry.replace(tzinfo=None) > now:
            base = current_expiry.replace(tzinfo=None)
    new_expiry = base + timedelta(days=plan['days'])
    oid = execute_insert("INSERT INTO subscription_orders (user_id, order_type, amount, status, paid_at, expires_at) VALUES (%s,%s,%s,'paid',NOW(),%s) RETURNING id",
                         (g.user_id, plan_id, plan['price'], new_expiry))
    execute_update("UPDATE users SET is_subscribed = TRUE, subscription_plan = %s, subscription_expires_at = %s WHERE id = %s",
                   (plan_id, new_expiry, g.user_id))
    # INSERT ON CONFLICT 防止付费用户切换月份时丢失额度
    period = date.today().replace(day=1)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO user_quota (user_id, period_start, analysis_limit, backtest_limit, analysis_used, backtest_used) "
                        "VALUES (%s,%s,%s,%s,0,0) ON CONFLICT (user_id, period_start) DO UPDATE SET "
                        "analysis_limit = EXCLUDED.analysis_limit, backtest_limit = EXCLUDED.backtest_limit",
                        (g.user_id, period, plan['analysis'], plan['backtest']))
    return jsonify({'code': 0, 'data': {'order_id': oid, 'plan': plan['name'], 'msg': '订阅已激活'}})
