"""认证 - 简单密码登录 (个人自托管)"""
import os, logging
from flask import Blueprint, request, jsonify, make_response
from app.utils.auth import generate_token
from app.config.settings import settings

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """密码登录 - 返回 JWT token"""
    data = request.get_json() or {}
    password = data.get('password', '')
    correct = os.getenv('APP_PASSWORD', 'stocksnap')
    if password != correct:
        return jsonify({'code': 401, 'msg': '密码错误', 'data': None}), 401
    token = generate_token()
    resp = make_response(jsonify({'code': 0, 'data': {'token': token}}))
    resp.set_cookie('token', token, max_age=30*86400, httponly=True, samesite='Lax')
    return resp

@auth_bp.route('/status', methods=['GET'])
def status():
    """检查登录状态"""
    from app.utils.auth import get_user_from_token
    user = get_user_from_token()
    return jsonify({'code': 0, 'data': {'logged_in': user is not None}})
