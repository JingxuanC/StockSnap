"""熔断器 - 防止雪崩效应"""
import time, threading, logging
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

class State(Enum):
    CLOSED = "closed"         # 正常
    OPEN = "open"            # 熔断
    HALF_OPEN = "half_open"  # 半开探测

class CircuitBreaker:
    """熔断器: 失败N次→熔断→等待→半开探测→恢复或继续熔断"""

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max: int = 2):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.state = State.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_attempts = 0
        self.lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        """执行函数，熔断器包裹"""
        with self.lock:
            if self.state == State.OPEN:
                if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                    self.state = State.HALF_OPEN
                    self.half_open_attempts = 0
                    logger.info(f"[熔断器:{self.name}] OPEN→HALF_OPEN, 探测中")
                else:
                    raise CircuitBreakerOpenError(f"[{self.name}] 熔断中, {self.recovery_timeout - (time.monotonic() - self.last_failure_time):.0f}s后重试")
            if self.state == State.HALF_OPEN and self.half_open_attempts >= self.half_open_max:
                raise CircuitBreakerOpenError(f"[{self.name}] 半开探测已达上限, 等待下次窗口")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        with self.lock:
            if self.state == State.HALF_OPEN:
                self.state = State.CLOSED
                self.failure_count = 0
                logger.info(f"[熔断器:{self.name}] HALF_OPEN→CLOSED, 已恢复")
            self.failure_count = 0

    def _on_failure(self, error):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.state == State.HALF_OPEN:
                self.half_open_attempts += 1
                if self.half_open_attempts >= self.half_open_max:
                    self.state = State.OPEN
                    logger.warning(f"[熔断器:{self.name}] HALF_OPEN→OPEN, 探测失败: {error}")
            elif self.state == State.CLOSED and self.failure_count >= self.failure_threshold:
                self.state = State.OPEN
                logger.error(f"[熔断器:{self.name}] CLOSED→OPEN, 连续{self.failure_count}次失败: {error}")

class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""
    pass

# 全局熔断器实例
deepseek_cb = CircuitBreaker("deepseek", failure_threshold=3, recovery_timeout=60)
akshare_cb = CircuitBreaker("akshare", failure_threshold=5, recovery_timeout=120)
yfinance_cb = CircuitBreaker("yfinance", failure_threshold=5, recovery_timeout=120)
