"""并发限流中间件 - 基于令牌桶算法的内存限流"""
import time, threading, logging
from collections import defaultdict
from functools import wraps
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

class TokenBucket:
    """令牌桶限流器"""
    def __init__(self, rate: int, burst: int):
        self.rate = rate         # 每秒补充令牌数
        self.burst = burst       # 桶容量
        self.tokens = burst      # 当前令牌数
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, n: int = 1) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False

class RateLimiter:
    """多维度限流器"""

    def __init__(self):
        self._buckets: dict = {}
        self._lock = threading.Lock()

    def _get_bucket(self, key: str, rate: int, burst: int) -> TokenBucket:
        if key not in self._buckets:
            with self._lock:
                if key not in self._buckets:
                    self._buckets[key] = TokenBucket(rate, burst)
        return self._buckets[key]

    def is_allowed(self, key: str, rate: int = 10, burst: int = 20) -> bool:
        """检查是否允许请求"""
        return self._get_bucket(key, rate, burst).consume(1)

    def cleanup(self, max_age: float = 3600):
        """清理过期桶"""
        now = time.monotonic()
        with self._lock:
            expired = [k for k, b in self._buckets.items() if now - b.last_refill > max_age]
            for k in expired:
                del self._buckets[k]

# 全局单例
limiter = RateLimiter()

def rate_limit(per_second: int = 10, per_minute: int = 60, burst: int = 20):
    """路由装饰器: 基于用户ID+IP的并发限流"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_id = getattr(g, 'user_id', None)
            ip = request.remote_addr or 'unknown'
            # 用户级限流 (精准)
            if user_id:
                user_key = f"user:{user_id}"
                if not limiter.is_allowed(user_key, per_second, burst):
                    return jsonify({'code': 429, 'msg': '请求过于频繁，请稍后重试', 'data': None}), 429
            # IP级限流 (兜底)
            ip_key = f"ip:{ip}"
            if not limiter.is_allowed(ip_key, per_second / 2, burst):
                return jsonify({'code': 429, 'msg': '请求过于频繁，请稍后重试', 'data': None}), 429
            # 全局限流 (保护后端)
            if not limiter.is_allowed("global:api", per_minute * 10, burst * 10):
                return jsonify({'code': 503, 'msg': '服务繁忙，请稍后重试', 'data': None}), 503
            return f(*args, **kwargs)
        return wrapped
    return decorator
