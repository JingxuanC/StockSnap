"""认证工具 - API Key 模式 (个人自托管)"""
import os, hashlib, secrets, logging
from functools import wraps
from datetime import datetime, timedelta
import jwt
from flask import request, jsonify, g
from app.config.settings import settings

logger = logging.getLogger(__name__)

def generate_token(user_id: int = 1) -> str:
    """生成 JWT (个人使用，user_id固定为1)"""
    payload = {'user_id': user_id, 'exp': datetime.utcnow() + timedelta(days=30), 'iat': datetime.utcnow()}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except Exception:
        return None

def get_user_from_token() -> dict:
    """从 Authorization header 或 token cookie 提取用户"""
    # Bearer token 优先
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        payload = verify_token(auth[7:])
        if payload: return {'user_id': payload.get('user_id', 1)}
    # Cookie fallback
    token = request.cookies.get('token', '')
    if token:
        payload = verify_token(token)
        if payload: return {'user_id': payload.get('user_id', 1)}
    return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_user_from_token()
        if not user:
            return jsonify({'code': 401, 'message': '请先登录', 'data': None}), 401
        g.user_id = user.get('user_id', 1)
        return f(*args, **kwargs)
    return decorated
