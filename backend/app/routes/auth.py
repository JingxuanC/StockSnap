"""微信小程序登录 API"""
import os, logging, requests
from flask import Blueprint, request, jsonify, g
from app.utils.auth import generate_token, login_required
from app.utils.db import execute_query, execute_insert

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/wechat-login', methods=['POST'])
def wechat_login():
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'code': 400, 'msg': '缺少code参数', 'data': None}), 400
    # 向微信换取openid
    app_id = os.getenv('WECHAT_APP_ID', '')
    app_secret = os.getenv('WECHAT_APP_SECRET', '')
    try:
        resp = requests.get(f'https://api.weixin.qq.com/sns/jscode2session?appid={app_id}&secret={app_secret}&js_code={code}&grant_type=authorization_code', timeout=10)
        wx = resp.json()
    except Exception as e:
        logger.error(f"微信API请求失败: {e}")
        return jsonify({'code': 500, 'msg': '微信登录服务异常', 'data': None}), 500
    openid = wx.get('openid')
    if not openid:
        return jsonify({'code': 401, 'msg': f"微信登录失败: {wx.get('errmsg', '未知')}", 'data': None}), 401
    # 查找或创建用户
    users = execute_query("SELECT id, openid, nickname, avatar_url, is_subscribed, subscription_expires_at FROM users WHERE openid = %s", (openid,))
    if users:
        user = users[0]
    else:
        uid = execute_insert("INSERT INTO users (openid, nickname, avatar_url) VALUES (%s, %s, %s) RETURNING id",
                             (openid, data.get('nickname', ''), data.get('avatar_url', '')))
        user = {'id': uid, 'openid': openid, 'nickname': data.get('nickname', ''), 'avatar_url': data.get('avatar_url', ''), 'is_subscribed': False, 'subscription_expires_at': None}
    token = generate_token(user['id'], openid)
    return jsonify({'code': 0, 'data': {'token': token, 'user': {'id': user['id'], 'nickname': user.get('nickname', ''), 'avatar_url': user.get('avatar_url', ''), 'is_subscribed': bool(user.get('is_subscribed', False)), 'subscription_expires_at': str(user.get('subscription_expires_at')) if user.get('subscription_expires_at') else None}}})

@auth_bp.route('/user-info', methods=['GET'])
@login_required
def get_user_info():
    users = execute_query("SELECT id, openid, nickname, avatar_url, is_subscribed, subscription_expires_at FROM users WHERE id = %s", (g.user_id,))
    if not users:
        return jsonify({'code': 404, 'msg': '用户不存在', 'data': None}), 404
    u = users[0]
    return jsonify({'code': 0, 'data': {'id': u['id'], 'nickname': u.get('nickname', ''), 'avatar_url': u.get('avatar_url', ''), 'is_subscribed': bool(u.get('is_subscribed', False)), 'subscription_expires_at': str(u.get('subscription_expires_at')) if u.get('subscription_expires_at') else None}})
