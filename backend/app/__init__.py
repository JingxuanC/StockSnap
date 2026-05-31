"""StockSnap Flask 应用工厂"""
import os
import math
import logging
from datetime import date, datetime

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class SafeJSONProvider(DefaultJSONProvider):
    """安全 JSON 序列化：NaN/Inf->null, datetime->ISO8601"""

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
        if isinstance(obj, dict):
            return {k: SafeJSONProvider._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [SafeJSONProvider._sanitize(v) for v in obj]
        return obj

    def dumps(self, obj, **kwargs):
        import json
        kwargs.setdefault('default', self.default)
        return json.dumps(self._sanitize(obj), **kwargs)


def create_app() -> Flask:
    """Flask 应用工厂"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = settings.SECRET_KEY
    app.config['JSON_AS_ASCII'] = False
    app.json_provider_class = SafeJSONProvider
    app.json = SafeJSONProvider(app)

    CORS(app, origins=settings.CORS_ORIGINS, supports_credentials=True)
    logger.info(f'CORS 允许的来源: {settings.CORS_ORIGINS}')

    try:
        from app.utils.db import init_database
        init_database()
        logger.info('数据库连接池初始化完成')
    except Exception as e:
        logger.warning(f'数据库初始化警告: {e}')

    from app.routes import register_routes
    register_routes(app)
    logger.info('所有路由注册完成')

    @app.route('/')
    def index():
        return {'name': 'StockSnap API', 'version': '0.1.0', 'status': 'running'}

    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}

    return app
