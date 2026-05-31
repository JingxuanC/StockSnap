"""JWT 认证工具"""
from functools import wraps
from datetime import datetime, timedelta
import jwt
from flask import request, jsonify, g
from app.config.settings import settings

JWT_EXPIRATION_DAYS = 7

def generate_token(user_id: int, openid: str) -> str:
    payload = {
        'exp': datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS),
        'iat': datetime.utcnow(),
        'user_id': user_id,
        'openid': openid,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def get_user_from_token() -> dict:
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return None
    return {'user_id': payload.get('user_id'), 'openid': payload.get('openid')}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_user_from_token()
        if not user:
            return jsonify({'code': 401, 'message': '未登录或登录已过期', 'data': None}), 401
        g.user_id = user['user_id']
        g.openid = user['openid']
        return f(*args, **kwargs)
    return decorated
