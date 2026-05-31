"""统一工具注册中心 - 管理所有 Agent 可调用的工具
每个工具 = OpenAI function calling 格式的定义 + Python 执行函数
用户订阅等级决定可用工具列表
"""
import json, logging
from typing import Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict                          # JSON Schema
    handler: Callable                         # 实际执行函数
    tier: str = "free"                        # free | pro | admin
    category: str = "general"                 # data | analysis | backtest | news
    source: str = "builtin"                   # builtin | mcp:stock-sdk | mcp:quantdinger

class ToolRegistry:
    """工具注册中心 - 单例"""
    _tools: dict[str, ToolDef] = {}
    _categories: dict[str, list[str]] = {}

    @classmethod
    def register(cls, name: str, description: str, parameters: dict, handler: Callable,
                 tier: str = "free", category: str = "general", source: str = "builtin"):
        cls._tools[name] = ToolDef(name=name, description=description, parameters=parameters,
                                   handler=handler, tier=tier, category=category, source=source)
        cls._categories.setdefault(category, []).append(name)
        logger.info(f"[ToolRegistry] 注册工具: {name} ({tier}, {category})")

    @classmethod
    def get(cls, name: str) -> ToolDef | None:
        return cls._tools.get(name)

    @classmethod
    def list_for_tier(cls, tier: str = "free") -> list[dict]:
        """返回某订阅等级可用的工具列表 (OpenAI function calling 格式)"""
        tools = []
        for t in cls._tools.values():
            if cls._tier_allowed(t.tier, tier):
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters
                    }
                })
        return tools

    @classmethod
    def execute(cls, name: str, arguments: dict, tier: str = "free") -> str:
        """执行工具并返回结果字符串 (Agent循环用)"""
        t = cls._tools.get(name)
        if not t:
            return json.dumps({"error": f"未知工具: {name}"})
        if not cls._tier_allowed(t.tier, tier):
            return json.dumps({"error": f"工具 {name} 需要 {t.tier} 等级"})
        try:
            result = t.handler(**arguments)
            if isinstance(result, str): return result
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"工具执行失败 {name}: {e}")
            return json.dumps({"error": str(e)})

    @classmethod
    def _tier_allowed(cls, required: str, current: str) -> bool:
        order = {"free": 0, "pro": 1, "admin": 2}
        return order.get(current, 0) >= order.get(required, 0)

    @classmethod
    def get_categories(cls) -> dict:
        return dict(cls._categories)

# 装饰器语法糖
def tool(name: str, description: str, parameters: dict, tier: str = "free", category: str = "general", source: str = "builtin"):
    def decorator(fn):
        ToolRegistry.register(name, description, parameters, fn, tier, category, source)
        return fn
    return decorator
