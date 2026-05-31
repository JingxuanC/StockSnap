"""Agent 可观测性层 - Token追踪、审计日志、延迟监控、成本归因

设计原则 (来自 Anthropic + OpenTelemetry):
- 每次 LLM 调用: 记录 tokens/cost/latency
- 每次工具调用: 记录工具名/参数/耗时/结果摘要
- 每个 Agent 会话: trace_id 贯穿全链路
- 不可变审计日志: 写入后不可修改
"""
from __future__ import annotations
import json, time, uuid, logging, threading
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# ---- 成本模型 (RMB) ----
DEEPSEEK_PRICING = {
    "deepseek-chat":    {"input": 0.001,  "output": 0.002},   # per 1K tokens
    "deepseek-v3":      {"input": 0.001,  "output": 0.002},
}

@dataclass
class LLMCallRecord:
    """单次 LLM 调用记录"""
    call_id: str
    timestamp: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_rmb: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error: str = ""
    prompt_hash: str = ""

@dataclass
class ToolCallRecord:
    """单次工具调用记录"""
    tool_name: str
    timestamp: str
    arguments: dict = field(default_factory=dict)
    duration_ms: int = 0
    success: bool = True
    error: str = ""
    result_summary: str = ""    # 前200字符

@dataclass
class AgentSession:
    """一次 Agent 对话的完整审计记录"""
    session_id: str
    user_id: int
    query: str
    tier: str
    start_time: str
    end_time: str = ""
    total_tokens: int = 0
    total_cost_rmb: float = 0.0
    total_latency_ms: int = 0
    llm_calls: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    evals: dict = field(default_factory=dict)
    status: str = "running"  # running | completed | failed

# ---- 全局指标收集 ----
class AgentMetrics:
    """Agent 全局运行指标 (内存中，可定期刷到DB)"""
    def __init__(self):
        self.lock = threading.Lock()
        self.total_sessions = 0
        self.total_llm_calls = 0
        self.total_tool_calls = 0
        self.total_tokens = 0
        self.total_cost_rmb = 0.0
        self.errors = defaultdict(int)
        # 延迟分位 (简化版)
        self.latencies_ms: list = []

    def record_session(self, session: AgentSession):
        with self.lock:
            self.total_sessions += 1
            self.total_llm_calls += len(session.llm_calls)
            self.total_tool_calls += len(session.tool_calls)
            self.total_tokens += session.total_tokens
            self.total_cost_rmb += session.total_cost_rmb
            self.latencies_ms.append(session.total_latency_ms)
            if len(self.latencies_ms) > 1000:
                self.latencies_ms = self.latencies_ms[-500:]

    def snapshot(self) -> dict:
        with self.lock:
            lats = sorted(self.latencies_ms) if self.latencies_ms else [0]
            return {
                "sessions": self.total_sessions,
                "llm_calls": self.total_llm_calls,
                "tool_calls": self.total_tool_calls,
                "total_tokens": self.total_tokens,
                "total_cost_rmb": round(self.total_cost_rmb, 6),
                "errors": dict(self.errors),
                "latency_p50_ms": lats[len(lats)//2] if lats else 0,
                "latency_p95_ms": lats[int(len(lats)*0.95)] if len(lats) >= 20 else lats[-1] if lats else 0,
                "latency_p99_ms": lats[int(len(lats)*0.99)] if len(lats) >= 100 else lats[-1] if lats else 0,
            }

# 全局单例
metrics = AgentMetrics()

# ---- 工具函数 ----
def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """估算单次 LLM 调用成本"""
    pricing = DEEPSEEK_PRICING.get(model, DEEPSEEK_PRICING["deepseek-chat"])
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000

def new_session(user_id: int, query: str, tier: str) -> AgentSession:
    return AgentSession(
        session_id=uuid.uuid4().hex[:12],
        user_id=user_id,
        query=query[:500],
        tier=tier,
        start_time=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    )

def log_llm_call(session: AgentSession, model: str, input_tokens: int,
                 output_tokens: int, latency_ms: int, success: bool, error: str = "",
                 prompt_text: str = "") -> LLMCallRecord:
    import hashlib
    rec = LLMCallRecord(
        call_id=uuid.uuid4().hex[:8],
        timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        model=model,
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        cost_rmb=round(estimate_cost(model, input_tokens or 0, output_tokens or 0), 6),
        latency_ms=latency_ms,
        success=success,
        error=error[:200],
        prompt_hash=hashlib.md5(prompt_text.encode()).hexdigest()[:12] if prompt_text else "",
    )
    session.llm_calls.append(rec)
    session.total_tokens += (input_tokens or 0) + (output_tokens or 0)
    session.total_cost_rmb += rec.cost_rmb
    logger.info(f"[Audit:LLM] {model} | {input_tokens}+{output_tokens} tokens | ¥{rec.cost_rmb:.6f} | {latency_ms}ms")
    return rec

def log_tool_call(session: AgentSession, tool_name: str, arguments: dict,
                  duration_ms: int, success: bool, error: str = "",
                  result: str = "") -> ToolCallRecord:
    rec = ToolCallRecord(
        tool_name=tool_name,
        timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        arguments=arguments,
        duration_ms=duration_ms,
        success=success,
        error=error[:200],
        result_summary=result[:200] if result else "",
    )
    session.tool_calls.append(rec)
    logger.info(f"[Audit:Tool] {tool_name}({json.dumps(arguments,ensure_ascii=False)}) | {duration_ms}ms | {'OK' if success else 'FAIL'}")
    if not success:
        metrics.errors[tool_name] += 1
    return rec

def finalize_session(session: AgentSession, status: str = "completed"):
    session.end_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    session.status = status
    # 计算总延迟
    try:
        start = datetime.fromisoformat(session.start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(session.end_time.replace('Z', '+00:00'))
        session.total_latency_ms = int((end - start).total_seconds() * 1000)
    except Exception:
        pass
    metrics.record_session(session)
    logger.info(f"[Audit:Session] {session.session_id} | {session.total_tokens}tok | "
                f"¥{session.total_cost_rmb:.6f} | {session.total_latency_ms}ms | "
                f"{len(session.llm_calls)}LLM+{len(session.tool_calls)}tools | {status}")
