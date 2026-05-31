"""Skill 注册中心 - 管理 AI 分析技能模板
每个 Skill = 自然语言分析任务 + 推荐的 MCP 工具组合
用户选择 Skill → Agent 使用对应的 system prompt + 工具集执行
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Skill:
    id: str
    name: str
    description: str
    tier: str                    # free | pro
    category: str                # analysis | screen | backtest | report
    prompt_instruction: str      # 注入到 Agent system prompt 的指令
    recommended_mcps: list[str]  # 推荐搭配的 MCP
    example_queries: list[str]   # 示例提问
    icon: str = "📝"

class SkillRegistry:
    """管理所有可用 Skill"""
    _skills: dict[str, Skill] = {}

    @classmethod
    def register(cls, skill: Skill):
        cls._skills[skill.id] = skill
        logger.info(f"[Skill] 注册: {skill.id} ({skill.tier})")

    @classmethod
    def list_available(cls, tier: str = "free") -> list[dict]:
        result = []
        for s in cls._skills.values():
            accessible = cls._tier_allowed(s.tier, tier)
            result.append({
                "id": s.id, "name": s.name, "description": s.description,
                "tier": s.tier, "category": s.category, "icon": s.icon,
                "accessible": accessible,
                "example_queries": s.example_queries if accessible else [],
                "recommended_mcps": s.recommended_mcps if accessible else []
            })
        return result

    @classmethod
    def get_prompt_for_skills(cls, skill_ids: list[str], tier: str = "free") -> str:
        """根据选中的 Skills 生成 Agent system prompt 补充指令"""
        instructions = []
        for sid in skill_ids:
            s = cls._skills.get(sid)
            if s and cls._tier_allowed(s.tier, tier):
                instructions.append(s.prompt_instruction)
        return "\n\n".join(instructions) if instructions else ""

    @classmethod
    def _tier_allowed(cls, required: str, current: str) -> bool:
        order = {"free": 0, "pro": 1, "admin": 2}
        return order.get(current, 0) >= order.get(required, 0)

# ---- 预注册 Skills ----

SkillRegistry.register(Skill(
    id="stock-analysis", name="个股深度分析",
    description="全方位分析一只股票：基本面+技术面+回测，输出完整投资建议",
    tier="free", category="analysis", icon="🔬",
    prompt_instruction="""当用户要求分析某只股票时:
1. 先用 search_stock 找到准确代码
2. 用 get_kline + get_stock_info 获取数据
3. 用 technical_analyze 做技术分析
4. 用 deep_analyze 做基本面深度研究
5. 用 run_backtest 跑双均线和MACD两个策略回测
6. 综合所有结果，给出 BUY/HOLD/SELL 评级和置信度""",
    recommended_mcps=["stock-sdk", "deep-research", "quantdinger"],
    example_queries=["分析茅台", "茅台现在能买吗", "600519怎么样"]
))

SkillRegistry.register(Skill(
    id="quick-technical", name="快速技术扫描",
    description="只看技术面：RSI/MACD/均线/布林带，30秒出结果",
    tier="free", category="analysis", icon="📈",
    prompt_instruction="""用户要做快速技术分析:
1. 用 search_stock 找代码
2. 用 get_kline 获取120日K线
3. 用 technical_analyze 分析
4. 直接给出买卖信号和关键支撑/压力位""",
    recommended_mcps=["stock-sdk"],
    example_queries=["茅台技术面怎么样", "MACD金叉了吗", "RSI超买超卖"]
))

SkillRegistry.register(Skill(
    id="smart-screen", name="智能选股",
    description="设定条件（估值/增长/技术指标），AI 帮你筛选标的",
    tier="pro", category="screen", icon="🔍",
    prompt_instruction="""用户要筛选股票:
1. 理解筛选条件（估值区间、行业、市值、技术指标等）
2. 用 search_stock 在目标板块搜索
3. 对候选标的逐一用 get_kline + get_stock_info 获取数据
4. 按条件过滤排序
5. 对前5名做 deep_analyze 深度评估
6. 输出排序榜单""",
    recommended_mcps=["stock-sdk", "deep-research", "cn-financial"],
    example_queries=["找PE低于20的科技股", "MACD金叉的蓝筹股", "筛选高ROE低负债标的"]
))

SkillRegistry.register(Skill(
    id="backtest-battle", name="策略回测对比",
    description="同时跑 5 种策略回测，直观对比收益/回撤/夏普",
    tier="free", category="backtest", icon="⚔️",
    prompt_instruction="""用户要回测对比:
1. 获取该股票的K线数据
2. 用 run_backtest 依次跑 5 种策略: ma_cross, macd_signal, rsi_reversal, bollinger_breakout, turtle_trend
3. 对比各项指标（收益率/夏普/最大回撤/胜率）
4. 推荐最佳策略并给出参数优化建议""",
    recommended_mcps=["quantdinger", "stock-sdk"],
    example_queries=["茅台哪种策略最好", "回测对比所有策略", "帮茅台找最佳交易策略"]
))

SkillRegistry.register(Skill(
    id="daily-briefing", name="每日盘前简报",
    description="开盘前自动生成：隔夜美股/政策/公告/技术面综合简报",
    tier="pro", category="report", icon="🌅",
    prompt_instruction="""生成今日盘前简报:
1. 获取主要指数数据(上证/深证/科创50)
2. 获取关注列表股票的最新行情
3. 用 search_news 找重要新闻
4. 用 technical_analyze 快速扫描关注标的
5. 汇总为 300 字盘前简报""",
    recommended_mcps=["stock-sdk", "news-sentiment"],
    example_queries=["今日盘前简报", "今天有什么重要消息", "开盘前应该关注什么"]
))

SkillRegistry.register(Skill(
    id="catalyst-tracker", name="催化剂追踪",
    description="追踪股票即将发生的催化剂事件：财报/产品发布/政策窗口",
    tier="pro", category="report", icon="📅",
    prompt_instruction="""追踪催化剂:
1. 用 search_news 搜索最新公告和新闻
2. 用 get_stock_info 了解公司基本面
3. 列出近期(1-3个月)和长期(6-12个月)的催化剂事件
4. 评估每个催化剂对股价的潜在影响(正面/负面/中性)
5. 给出关键日期和操作建议""",
    recommended_mcps=["stock-sdk", "news-sentiment", "deep-research"],
    example_queries=["茅台近期有什么催化剂", "追踪AAPL催化剂事件", "哪些股票最近有财报"]
))
