"""AI Agent 引擎 - ReAct 循环: LLM自主决策→调用工具→观察结果→继续决策→输出
模式: User Query → LLM(tools) → [tool_calls...] → observe → LLM → ... → final answer
"""
import json, time, logging
from typing import Callable
from openai import OpenAI
from app.config.settings import settings
from app.agent.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 StockSnap AI 股票分析助手，运行在微信小程序中。你可以自主调用工具来分析股票。

## 核心能力
- 搜索股票（A股/美股）
- 获取实时行情、K线数据
- 深度AI基本面分析（投资论点/行业/催化剂/财报/估值/风险）
- 技术分析（RSI/MACD/均线/趋势判断）
- 策略回测（双均线/MACD/RSI/布林带/海龟）

## 工作原则
1. 用户输入股票名称或代码时，先用 search_stock 找到准确代码
2. 获取数据后再做分析，不要凭空猜测
3. 技术分析和基本面分析结合，给出综合判断
4. 用户问"能不能买"时，运行 deep_analyze + technical_analyze + run_backtest 三项，综合输出
5. 回答简洁专业，用中文，关键数据突出显示
6. 用工具返回的真实数据，不要编造
7. 如果工具返回错误，如实告知用户

## 搜索策略
- search_stock 支持模糊搜索，直接搜名称或代码即可
- 搜到结果后直接用代码(symbol)调用后续工具
- 不要反复搜索同一个标的

## 分析策略
- deep_analyze 返回原始数据，agent需自行解读
- 结合 technical_analyze + run_backtest 形成综合判断
- 数据驱动，不编造信息

## 输出格式
最终回答使用 Markdown，务必包含: 公司概况、估值分析、技术面判断、回测结果、综合评级
评级: 🟢买入 / 🟡持有 / 🔴卖出
回答必须具体，不能空白。"""

MAX_TOOL_ROUNDS = 5   # 最多5轮（减少无意义重试）
MAX_TOTAL_TIME = 240  # 4分钟

class AgentEngine:
    """ReAct Agent: Think → Act → Observe → Think → ... → Answer"""

    def __init__(self, user_tier: str = "free"):
        self.client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL, timeout=120)
        self.model = settings.DEEPSEEK_MODEL
        self.user_tier = user_tier
        self.tools = ToolRegistry.list_for_tier(user_tier)
        self.messages = []

    def run(self, user_query: str, context: dict = None, skills: list[str] = None) -> dict:
        """执行 Agent 循环，返回最终结果
        Args:
            user_query: 用户自然语言问题
            context: 上下文 {focus_symbol, focus_market}
            skills: 用户选择的 Skill ID 列表 (注入对应的 system prompt)
        """
        start = time.time()
        # 构建 system prompt，注入选中的 Skill 指令
        prompt = SYSTEM_PROMPT
        if skills:
            from app.agent.skill_registry import SkillRegistry
            skill_prompt = SkillRegistry.get_prompt_for_skills(skills, self.user_tier)
            if skill_prompt:
                prompt += "\n\n## 用户选择的技能\n" + skill_prompt
        self.messages = [{"role": "system", "content": prompt}]
        if context and context.get("focus_symbol"):
            self.messages.append({"role": "system", "content": f"用户当前关注的股票: {context['focus_symbol']} ({context.get('focus_market', 'CN')})"})
        self.messages.append({"role": "user", "content": user_query})

        tool_rounds = 0
        final_text = ""

        while tool_rounds < MAX_TOOL_ROUNDS and (time.time() - start) < MAX_TOTAL_TIME:
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=self.messages, tools=self.tools or None,
                    tool_choice="auto" if self.tools else None, temperature=0.3, max_tokens=4096)
            except Exception as e:
                logger.error(f"Agent LLM调用失败: {e}")
                return {"error": f"AI服务异常: {e}", "rounds": tool_rounds, "time": time.time() - start}

            msg = response.choices[0].message

            # 有工具调用 → 执行
            if msg.tool_calls:
                self.messages.append(msg)
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}
                    logger.info(f"[Agent] 调用工具: {fn_name}({fn_args})")
                    result_str = ToolRegistry.execute(fn_name, fn_args, self.user_tier)
                    self.messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": result_str[:4000]  # 截断过长结果
                    })
                tool_rounds += 1
                continue

            # 无工具调用 → 最终回答
            final_text = msg.content or ""
            break

        elapsed = time.time() - start
        logger.info(f"[Agent] 完成: {tool_rounds}轮, {elapsed:.1f}s")

        return {
            "answer": final_text or "分析完成，但未能生成文本回复",
            "rounds": tool_rounds,
            "time_seconds": round(elapsed, 1),
            "tier": self.user_tier,
            "model": self.model
        }
