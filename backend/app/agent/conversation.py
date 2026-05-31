"""对话管理器 - 多轮会话 + 记忆系统
三层记忆: Short-term(会话) → Mid-term(摘要) → Long-term(向量库)
"""
from __future__ import annotations
import json, time, logging, hashlib
from datetime import datetime, timezone
from typing import Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)

class ConversationManager:
    """管理用户对话历史和上下文窗口"""

    def __init__(self, max_turns: int = 20, summary_interval: int = 10):
        self.max_turns = max_turns          # 最多保留轮次
        self.summary_interval = summary_interval  # 每N轮触发摘要
        self._sessions: dict[int, OrderedDict] = {}  # {user_id: OrderedDict}
        self._summaries: dict[int, str] = {}          # {user_id: summary}

    def add_turn(self, user_id: int, role: str, content: str):
        if user_id not in self._sessions:
            self._sessions[user_id] = OrderedDict()
        turn_id = f"{int(time.time())}_{len(self._sessions[user_id])}"
        self._sessions[user_id][turn_id] = {
            "role": role, "content": content[:4000],  # 截断长内容
            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        # 保持窗口大小
        while len(self._sessions[user_id]) > self.max_turns:
            self._sessions[user_id].popitem(last=False)
        # 触发摘要
        if len(self._sessions[user_id]) % self.summary_interval == 0:
            self._maybe_summarize(user_id)

    def get_history(self, user_id: int, limit: int = None) -> list[dict]:
        """获取格式化的对话历史 (OpenAI messages 格式)"""
        session = self._sessions.get(user_id, OrderedDict())
        turns = list(session.values())[-(limit or self.max_turns):]
        # 如果有摘要，前置注入
        result = []
        if user_id in self._summaries:
            result.append({"role": "system", "content": f"[对话摘要]: {self._summaries[user_id]}"})
        for t in turns:
            result.append({"role": t["role"], "content": t["content"]})
        return result

    def _maybe_summarize(self, user_id: int):
        """标记需要摘要（实际摘要由LLM在下次对话时生成）"""
        session = self._sessions.get(user_id)
        if session and len(session) >= self.summary_interval:
            logger.info(f"[Conv] 用户{user_id}对话达到{len(session)}轮，标记需摘要")

    def set_summary(self, user_id: int, summary: str):
        self._summaries[user_id] = summary[:500]
        # 清理旧轮次，只保留最近5轮
        if user_id in self._sessions:
            old = list(self._sessions[user_id].items())
            self._sessions[user_id] = OrderedDict(old[-5:])

    def clear_user(self, user_id: int):
        self._sessions.pop(user_id, None)
        self._summaries.pop(user_id, None)

# 全局单例
conversations = ConversationManager()
