"""StockSnap 路由注册"""
from flask import Flask

def register_routes(app: Flask):
    from app.routes.auth import auth_bp
    from app.routes.analysis import analysis_bp
    from app.routes.backtest import backtest_bp
    from app.routes.subscription import subscription_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(backtest_bp, url_prefix='/api/backtest')
    app.register_blueprint(subscription_bp, url_prefix='/api/subscription')
