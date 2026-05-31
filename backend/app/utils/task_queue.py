"""Redis 消息队列 - 异步任务分发 + 后台 Worker
架构: Flask 请求 → 入队 → 立即返回 task_id → worker 消费 → 结果写 Redis
"""
import json, os, time, uuid, threading, logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    import redis as _redis
    _r = _redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
    _r.ping()
    _RAW = _redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=False)
    HAS_REDIS = True
except Exception:
    _r = None; _RAW = None; HAS_REDIS = False

# 队列配置
QUEUE_KEY = "ss:task:queue"         # 待处理任务列表
TASK_PREFIX = "ss:task:"            # 任务状态 key 前缀
RESULT_TTL = 3600                   # 结果保留 1 小时
MAX_QUEUE_SIZE = 500                # 队列最大长度
WORKER_COUNT = 2                    # 后台 worker 数量

def _task_key(task_id: str) -> str:
    return f"{TASK_PREFIX}{task_id}"

def enqueue(task_type: str, payload: dict) -> str:
    """入队一个异步任务，立即返回 task_id"""
    if not HAS_REDIS: raise RuntimeError("Redis 不可用")
    task_id = uuid.uuid4().hex[:12]
    task = {"id": task_id, "type": task_type, "payload": payload, "status": "pending", "created_at": time.time()}
    _r.setex(_task_key(task_id), RESULT_TTL, json.dumps(task, ensure_ascii=False))
    _r.lpush(QUEUE_KEY, task_id)
    # 限制队列长度，防止内存炸
    _r.ltrim(QUEUE_KEY, 0, MAX_QUEUE_SIZE - 1)
    logger.info(f"[Queue] enqueue {task_type}:{task_id}")
    return task_id

def get_task(task_id: str) -> Optional[dict]:
    """查询任务状态"""
    if not HAS_REDIS: return None
    raw = _r.get(_task_key(task_id))
    return json.loads(raw) if raw else None

def update_task(task_id: str, status: str, result: dict = None, error: str = None):
    """更新任务状态+结果"""
    if not HAS_REDIS: return
    task = get_task(task_id)
    if not task: return
    task["status"] = status
    task["updated_at"] = time.time()
    if result is not None: task["result"] = result
    if error is not None: task["error"] = error
    _r.setex(_task_key(task_id), RESULT_TTL, json.dumps(task, ensure_ascii=False))

# ---- Worker ----

_registry: dict[str, Callable] = {}

def register_task(name: str):
    """装饰器: 注册任务处理器"""
    def decorator(fn):
        _registry[name] = fn
        return fn
    return decorator

def _worker_loop(worker_id: int):
    """后台 worker 从队列拉任务执行"""
    logger.info(f"[Worker-{worker_id}] 启动")
    while True:
        try:
            result = _r.brpop(QUEUE_KEY, timeout=5) if HAS_REDIS else None
            if result is None: continue
            _, task_id = result
            task = get_task(task_id)
            if not task: continue
            logger.info(f"[Worker-{worker_id}] 处理 {task['type']}:{task_id}")
            update_task(task_id, "processing")
            handler = _registry.get(task["type"])
            if not handler:
                update_task(task_id, "failed", error=f"未知任务类型: {task['type']}")
                continue
            try:
                output = handler(task["payload"])
                update_task(task_id, "completed", result=output)
                logger.info(f"[Worker-{worker_id}] 完成 {task_id}")
            except Exception as e:
                logger.error(f"[Worker-{worker_id}] 失败 {task_id}: {e}")
                update_task(task_id, "failed", error=str(e))
        except Exception as e:
            logger.error(f"[Worker-{worker_id}] 异常: {e}")
            time.sleep(1)

def start_workers():
    """启动后台 worker 线程（Flask 启动时调用）"""
    if not HAS_REDIS:
        logger.warning("Redis 不可用，任务队列已禁用")
        return
    for i in range(WORKER_COUNT):
        t = threading.Thread(target=_worker_loop, args=(i,), daemon=True, name=f"task-worker-{i}")
        t.start()
    logger.info(f"{WORKER_COUNT} 个后台 Worker 已启动")
