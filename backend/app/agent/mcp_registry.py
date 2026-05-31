"""MCP 注册中心 - 管理可用的 MCP 服务器和用户激活状态"""
from __future__ import annotations
import json, logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class MCPServer:
    id: str
    name: str
    description: str
    tier: str          # free | pro
    tools: list[str]   # 提供的工具名列表
    install_cmd: str   # 安装命令
    icon: str = "🔌"

class MCPRegistry:
    """管理所有可用 MCP 服务器"""

    _servers: dict[str, MCPServer] = {}
    # 用户激活状态: {user_id: [mcp_ids]}
    _user_mcps: dict[int, list[str]] = {}

    @classmethod
    def register(cls, mcp: MCPServer):
        cls._servers[mcp.id] = mcp
        logger.info(f"[MCP] 注册: {mcp.id} ({mcp.tier})")

    @classmethod
    def list_available(cls, tier: str = "free") -> list[dict]:
        """列出某等级下可用的 MCP"""
        result = []
        for s in cls._servers.values():
            accessible = cls._tier_allowed(s.tier, tier)
            result.append({
                "id": s.id, "name": s.name, "description": s.description,
                "tier": s.tier, "tools": s.tools, "icon": s.icon,
                "accessible": accessible, "install_cmd": s.install_cmd if accessible else None
            })
        return result

    @classmethod
    def get_user_mcps(cls, user_id: int, tier: str = "free") -> list[str]:
        """获取用户已激活的 MCP 列表"""
        activated = cls._user_mcps.get(user_id, [])
        # 过滤掉等级不够的
        return [mid for mid in activated if cls._tier_allowed(cls._servers.get(mid, MCPServer(mid,"","","free",[],"")).tier, tier)]

    @classmethod
    def activate(cls, user_id: int, mcp_id: str, tier: str = "free") -> bool:
        """用户激活一个 MCP"""
        if mcp_id not in cls._servers:
            return False
        if not cls._tier_allowed(cls._servers[mcp_id].tier, tier):
            return False
        cls._user_mcps.setdefault(user_id, [])
        if mcp_id not in cls._user_mcps[user_id]:
            cls._user_mcps[user_id].append(mcp_id)
        return True

    @classmethod
    def deactivate(cls, user_id: int, mcp_id: str) -> bool:
        """用户停用一个 MCP"""
        if user_id in cls._user_mcps and mcp_id in cls._user_mcps[user_id]:
            cls._user_mcps[user_id].remove(mcp_id)
            return True
        return False

    @classmethod
    def _tier_allowed(cls, required: str, current: str) -> bool:
        order = {"free": 0, "pro": 1, "admin": 2}
        return order.get(current, 0) >= order.get(required, 0)

# ---- 预注册 MCP 服务器 ----

MCPRegistry.register(MCPServer(
    id="stock-sdk", name="A股/港股/美股实时行情",
    description="提供 40+ 字段实时行情、K线、10+ 技术指标、条件选股、板块数据、资金流向",
    tier="free", icon="📊",
    tools=["search_stock", "get_kline", "get_realtime", "get_stock_info", "technical_analyze"],
    install_cmd="npx -y stock-sdk-mcp"
))

MCPRegistry.register(MCPServer(
    id="quantdinger", name="量化回测 & 策略引擎",
    description="5 种经典策略回测(双均线/MACD/RSI/布林/海龟)、AI 参数优化、实验管道",
    tier="free", icon="⚡",
    tools=["run_backtest"],
    install_cmd="uvx quantdinger-mcp"
))

MCPRegistry.register(MCPServer(
    id="cn-financial", name="A股深度财务数据",
    description="42 个金融工具：财务三大报表、估值分析(PE/PB/PS)、宏观(GDP/CPI/PMI)、龙虎榜、北向资金",
    tier="pro", icon="🏦",
    tools=["sector_overview"],
    install_cmd="pip install cn-financial-mcp"
))

MCPRegistry.register(MCPServer(
    id="deep-research", name="AI 深度研究",
    description="DeepSeek 驱动的投资论点分析、行业研究、催化剂日历、财报拆解、风险评估",
    tier="free", icon="🧠",
    tools=["deep_analyze"],
    install_cmd="内置"
))

MCPRegistry.register(MCPServer(
    id="news-sentiment", name="新闻舆情 & 情绪分析",
    description="实时财经新闻聚合、情感分析、热点追踪、公告解读",
    tier="pro", icon="📰",
    tools=["search_news"],
    install_cmd="pip install finnhub-python"
))
