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
    @staticmethod
    def _sanitize(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj): return None
            return obj
        if isinstance(obj, datetime): return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        if isinstance(obj, date): return obj.isoformat()
        try:
            import numpy as np
            if isinstance(obj, np.integer): return int(obj)
            if isinstance(obj, np.floating): return float(obj) if not np.isnan(obj) and not np.isinf(obj) else None
            if isinstance(obj, np.ndarray): return obj.tolist()
        except ImportError: pass
        try:
            import pandas as pd
            if isinstance(obj, pd.Timestamp): return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ImportError: pass
        if isinstance(obj, dict): return {k: SafeJSONProvider._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)): return [SafeJSONProvider._sanitize(v) for v in obj]
        return obj

    def dumps(self, obj, **kwargs):
        import json
        kwargs.setdefault('default', str)
        return json.dumps(self._sanitize(obj), **kwargs)

def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.config['SECRET_KEY'] = settings.SECRET_KEY
    flask_app.config['JSON_AS_ASCII'] = False
    flask_app.json_provider_class = SafeJSONProvider
    flask_app.json = SafeJSONProvider(flask_app)

    origins = settings.CORS_ORIGINS
    if origins == ['*']:
        logger.warning("CORS origins 为 '*' — 生产环境请设置 CORS_ORIGINS 为具体域名")
    CORS(flask_app, origins=origins, supports_credentials=(origins != ['*']))
    logger.info(f'CORS origins: {origins}')

    # 数据库可选
    try:
        from app.utils.db import init_database
        init_database()
        logger.info('数据库连接池初始化完成')
    except Exception as e:
        logger.warning(f'数据库不可用，运行在无DB模式: {e}')

    from app.routes import register_routes
    register_routes(flask_app)
    logger.info('所有路由注册完成')

    # 后台 Worker
    try:
        from app.utils.task_queue import start_workers
        import app.services.task_handlers
        start_workers()
        logger.info('后台任务 Worker 已启动')
    except Exception as e:
        logger.warning(f'Worker 启动失败: {e}')

    # Agent 工具
    try:
        from app.agent.tools import init_tools as _init_tools
        _init_tools()
        logger.info('Agent 工具已注册')
    except Exception as e:
        logger.warning(f'Agent 工具注册失败: {e}')

    @flask_app.route('/')
    def index():
        return {'name': 'StockSnap API', 'version': '0.2.0', 'status': 'running'}

    @flask_app.route('/health')
    def health_check():
        return {'status': 'healthy', 'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}

    return flask_app
