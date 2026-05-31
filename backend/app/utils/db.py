"""数据库连接池管理"""
import os
import logging
import threading
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger(__name__)
_connection_pool = None
_pool_lock = threading.Lock()

def _parse_database_url(url: str) -> dict:
    for prefix in ('postgresql://', 'postgres://'):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    result = {}
    if '@' in url:
        auth, hostpart = url.rsplit('@', 1)
        result['user'], result['password'] = auth.split(':', 1) if ':' in auth else (auth, '')
    else:
        hostpart = url
    if '/' in hostpart:
        hostport, result['dbname'] = hostpart.split('/', 1)
    else:
        hostport = hostpart
    result['host'] = hostport.split(':')[0] if ':' in hostport else hostport
    result['port'] = int(hostport.split(':')[1]) if ':' in hostport else 5432
    return result

def _get_connection_pool():
    global _connection_pool
    if _connection_pool is not None:
        return _connection_pool
    with _pool_lock:
        if _connection_pool is not None:
            return _connection_pool
        if not HAS_PSYCOPG2:
            raise RuntimeError('psycopg2 未安装')
        db_url = os.getenv('DATABASE_URL', '')
        params = _parse_database_url(db_url)
        # 高并发: 4 workers × 4 threads × 2 conn/req = 32 peak, 用50上限+超时防死锁
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=int(os.getenv('DB_POOL_MIN', '4')),
            maxconn=int(os.getenv('DB_POOL_MAX', '50')),
            host=params.get('host', 'localhost'),
            port=params.get('port', 5432),
            user=params.get('user', 'stocksnap'),
            password=params.get('password', ''),
            dbname=params.get('dbname', 'stocksnap'),
            connect_timeout=10,
            options='-c timezone=UTC -c statement_timeout=30000',
        )
    return _connection_pool

@contextmanager
def get_db():
    """获取DB连接，超时5秒防死锁"""
    pg_pool = _get_connection_pool()
    conn = None
    broken = False
    try:
        conn = pg_pool.getconn()
        # 设置语句超时
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '30s'")
        yield conn
        conn.commit()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
            broken = True
        raise
    finally:
        if conn is not None:
            pg_pool.putconn(conn, close=broken)

def execute_query(sql: str, params: tuple = None) -> list:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def execute_insert(sql: str, params: tuple = None) -> int:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row.get('id') if row and cur.rowcount > 0 else None

def execute_update(sql: str, params: tuple = None) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

def init_database():
    if not HAS_PSYCOPG2:
        raise RuntimeError('psycopg2 未安装')
    _get_connection_pool()
    _apply_init_sql()

def _apply_init_sql():
    from pathlib import Path
    init_path = Path(__file__).resolve().parent.parent.parent / 'migrations' / 'init.sql'
    if not init_path.exists():
        logger.warning(f'init.sql 不存在: {init_path}')
        return
    sql_text = init_path.read_text(encoding='utf-8')
    if not sql_text.strip():
        return
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_text)
            conn.commit()
        logger.info('数据库初始化完成')
    except Exception as e:
        logger.warning(f'自动迁移执行失败（表可能已存在）: {e}')
