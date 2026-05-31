"""StockSnap 应用配置 - 从环境变量读取所有配置项"""
import os


class Settings:
    @property
    def FLASK_ENV(self) -> str:
        return os.getenv('FLASK_ENV', 'development')

    @property
    def DEBUG(self) -> bool:
        return self.FLASK_ENV == 'development'

    @property
    def HOST(self) -> str:
        return os.getenv('HOST', '0.0.0.0')

    @property
    def PORT(self) -> int:
        return int(os.getenv('PORT', '5000'))

    @property
    def SECRET_KEY(self) -> str:
        return os.getenv('SECRET_KEY', 'stocksnap-default-dev-key')

    @property
    def DATABASE_URL(self) -> str:
        return os.getenv('DATABASE_URL', 'postgresql://stocksnap:stocksnap123@localhost:5432/stocksnap')

    @property
    def DB_POOL_MIN(self) -> int:
        return int(os.getenv('DB_POOL_MIN', '2'))

    @property
    def DB_POOL_MAX(self) -> int:
        return int(os.getenv('DB_POOL_MAX', '10'))

    @property
    def REDIS_URL(self) -> str:
        return os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    @property
    def DEEPSEEK_API_KEY(self) -> str:
        return os.getenv('DEEPSEEK_API_KEY', '')

    @property
    def DEEPSEEK_BASE_URL(self) -> str:
        return os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')

    @property
    def DEEPSEEK_MODEL(self) -> str:
        return os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

    @property
    def WECHAT_APP_ID(self) -> str:
        return os.getenv('WECHAT_APP_ID', '')

    @property
    def WECHAT_APP_SECRET(self) -> str:
        return os.getenv('WECHAT_APP_SECRET', '')

    @property
    def FREE_MONTHLY_QUOTA(self) -> int:
        return int(os.getenv('FREE_MONTHLY_QUOTA', '20'))

    @property
    def CORS_ORIGINS(self) -> list:
        origins = os.getenv('CORS_ORIGINS', '*')
        if origins == '*':
            return ['*']
        return [o.strip() for o in origins.split(',') if o.strip()]


settings = Settings()
