"""Redis 缓存层 - 分析结果缓存 + K线数据缓存"""
import os, json, logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

try:
    import redis
    _redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'), decode_responses=True, socket_timeout=3)
    _redis_client.ping()
    HAS_REDIS = True
    logger.info("Redis 缓存已连接")
except Exception as e:
    _redis_client = None
    HAS_REDIS = False
    logger.warning(f"Redis 未连接，缓存已禁用: {e}")

def cache_get(key: str) -> Optional[str]:
    if not HAS_REDIS: return None
    try: return _redis_client.get(f"ss:{key}")
    except Exception: return None

def cache_set(key: str, value: str, ttl: int = 300) -> bool:
    if not HAS_REDIS: return False
    try:
        _redis_client.setex(f"ss:{key}", ttl, value)
        return True
    except Exception: return False

def cache_delete(key: str):
    if not HAS_REDIS: return
    try: _redis_client.delete(f"ss:{key}")
    except Exception: pass

# 分析结果缓存 (TTL 1小时)
def get_cached_analysis(market: str, symbol: str) -> Optional[dict]:
    raw = cache_get(f"analysis:{market}:{symbol}")
    if raw:
        try: return json.loads(raw)
        except: pass
    return None

def set_cached_analysis(market: str, symbol: str, data: dict):
    cache_set(f"analysis:{market}:{symbol}", json.dumps(data, ensure_ascii=False), ttl=3600)

# K线缓存 (TTL 5分钟)
def get_cached_kline(market: str, symbol: str, timeframe: str) -> Optional[str]:
    return cache_get(f"kline:{market}:{symbol}:{timeframe}")

def set_cached_kline(market: str, symbol: str, timeframe: str, data: str):
    cache_set(f"kline:{market}:{symbol}:{timeframe}", data, ttl=300)
