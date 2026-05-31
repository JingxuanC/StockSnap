"""StockSnap Flask 应用工厂"""
import os, math, logging
from datetime import date, datetime, timezone

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

class SafeJSONProvider(DefaultJSONProvider):
    """安全 JSON 序列化：NaN/Inf -> null, datetime -> ISO8601, numpy/pandas -> Python原生"""

    @staticmethod
    def _sanitize(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        if isinstance(obj, date):
            return obj.isoformat()
        # 处理 numpy/pandas 类型
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj) if not np.isnan(obj) and not np.isinf(obj) else None
            if isinstance(obj, np.ndarray): return obj.tolist()
        except ImportError: pass
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp): return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
            if isinstance(obj, pd.Period): return str(obj)
        except ImportError: pass
        if isinstance(obj, dict):
            return {k: SafeJSONProvider._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [SafeJSONProvider._sanitize(v) for v in obj]
        return obj

    def dumps(self, obj, **kwargs):
        import json
        kwargs.setdefault('default', str)
        return json.dumps(self._sanitize(obj), **kwargs)

def create_app() -> Flask:
    """Flask 应用工厂"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = settings.SECRET_KEY
    app.config['JSON_AS_ASCII'] = False
    app.json_provider_class = SafeJSONProvider
    app.json = SafeJSONProvider(app)

    # CORS: 生产环境不应用通配符 + credentials
    origins = settings.CORS_ORIGINS
    if origins == ['*']:
        logger.warning("CORS origins 为 '*' — 生产环境请设置 CORS_ORIGINS 为具体域名")
    CORS(app, origins=origins, supports_credentials=(origins != ['*']))
    logger.info(f'CORS origins: {origins}')

    # 数据库初始化
    try:
        from app.utils.db import init_database
        init_database()
        logger.info('数据库连接池初始化完成')
    except Exception as e:
        logger.error(f'数据库初始化失败，应用无法启动: {e}')
        raise RuntimeError(f"数据库初始化失败: {e}") from e

    from app.routes import register_routes
    register_routes(app)
    logger.info('所有路由注册完成')

    @app.route('/')
    def index():
        return {'name': 'StockSnap API', 'version': '0.1.1', 'status': 'running'}

    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}

    return app
