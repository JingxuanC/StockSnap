"""AI Agent 引擎 v2 - RAG增强 + 并行工具调用 + 全链路可观测
模式: RAG检索 → 系统提示词注入 → LLM(并行工具调用) → 观测记录 → 存入知识库
参考: Anthropic Building Effective Agents + 2025 生产最佳实践
"""
from __future__ import annotations
import json, time, logging, concurrent.futures
from openai import OpenAI
from app.config.settings import settings
from app.agent.tool_registry import ToolRegistry
from app.agent.observability import (
    AgentSession, new_session, log_llm_call, log_tool_call, finalize_session, metrics
)
from app.agent.rag import search, store_analysis
from app.agent.conversation import conversations

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 StockSnap AI 股票分析助手。你可以自主调用工具来分析股票。

## 核心能力
- 搜索股票（A股/美股）、获取实时行情、K线数据
- 基本面分析（估值/财务/行业）、技术分析（RSI/MACD/均线）
- 策略回测（双均线/MACD/RSI/布林带/海龟）

## 工作原则
1. 数据驱动，不编造信息。工具失败时如实告知。
2. search_stock 支持模糊搜索名/代码，搜到后直接用代码调后续工具
3. 可以同时调用多个工具（如 get_kline + get_stock_info 并行）
4. 综合基本面、技术面、回测结果后给出 🟢买入/🟡持有/🔴卖出 评级
5. 简洁专业，关键数据突出。中文回答。
6. 如果已有的知识库数据和实时数据趋势一致，直接引用。如果不一致，以实时数据为准。

## 输出格式
Markdown 格式: 公司概况 → 估值分析 → 技术面 → 回测表现 → 风险提示 → 综合评级"""

MAX_TOOL_ROUNDS = 5
MAX_TOTAL_TIME = 240
MAX_PARALLEL_TOOLS = 4  # 单轮最多并行调用工具数

class AgentEngine:
    """ReAct Agent: Think → Act(并行) → Observe → Think → ... → Answer"""

    def __init__(self, user_id: int = 0, user_tier: str = "free"):
        self.client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL, timeout=120)
        self.model = settings.DEEPSEEK_MODEL
        self.user_id = user_id
        self.user_tier = user_tier
        self.tools = ToolRegistry.list_for_tier(user_tier)
        self.session: AgentSession = None
        self.messages = []
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_TOOLS)

    def run(self, user_query: str, context: dict = None, skills: list[str] = None) -> dict:
        """执行 Agent 循环"""
        self.session = new_session(self.user_id, user_query, self.user_tier)
        start = time.time()

        # 1. RAG 检索相关上下文
        rag_context = ""
        if context and context.get("focus_symbol"):
            rag_docs = search(context["focus_symbol"], n_results=3)
            if rag_docs:
                rag_context = "\n\n## 知识库参考 (历史分析)\n" + "\n---\n".join(rag_docs[:2])
                logger.info(f"[RAG] 检索到 {len(rag_docs)} 条相关记录")

        # 2. 构建消息
        prompt = SYSTEM_PROMPT + rag_context
        if skills:
            from app.agent.skill_registry import SkillRegistry
            sp = SkillRegistry.get_prompt_for_skills(skills, self.user_tier)
            if sp: prompt += "\n\n## 用户选择的技能\n" + sp
        self.messages = [{"role": "system", "content": prompt}]
        if context and context.get("focus_symbol"):
            self.messages.append({"role": "system", "content": f"用户当前关注的股票: {context['focus_symbol']} ({context.get('focus_market', 'CN')})"})

        # 3. 注入历史对话
        history = conversations.get_history(self.user_id, limit=8)
        if history: self.messages.extend(history)

        self.messages.append({"role": "user", "content": user_query})

        # 4. Agent 循环
        tool_rounds = 0; final_text = ""
        while tool_rounds < MAX_TOOL_ROUNDS and (time.time() - start) < MAX_TOTAL_TIME:
            llm_start = time.time()
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=self.messages, tools=self.tools or None,
                    tool_choice="auto" if self.tools else None, temperature=0.3, max_tokens=4096,
                    parallel_tool_calls=(len(self.tools) > 1))
            except Exception as e:
                logger.error(f"LLM 调用失败: {e}")
                log_llm_call(self.session, self.model, 0, 0, int((time.time()-llm_start)*1000), False, str(e))
                return self._finish(f"AI服务暂时不可用: {e}", start, "failed")

            msg = response.choices[0].message
            usage = response.usage
            log_llm_call(self.session, self.model,
                         usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0,
                         int((time.time()-llm_start)*1000), True)

            # 工具调用 → 并行执行
            if msg.tool_calls:
                self.messages.append(msg)
                tool_count = min(len(msg.tool_calls), MAX_PARALLEL_TOOLS)
                logger.info(f"[Agent] 并行调用 {tool_count} 个工具")
                futures = {}
                for tc in msg.tool_calls[:tool_count]:
                    futures[tc.id] = self.executor.submit(self._exec_tool, tc)
                # 等待全部完成
                for tc_id, future in futures.items():
                    tc = next(t for t in msg.tool_calls if t.id == tc_id)
                    try: result_str = future.result(timeout=60)
                    except Exception as e: result_str = json.dumps({"error": str(e)})
                    self.messages.append({"role": "tool", "tool_call_id": tc_id, "content": result_str[:4000]})
                tool_rounds += 1
                continue

            # 最终回答
            final_text = msg.content or ""
            break

        status = "completed" if final_text else "incomplete"
        return self._finish(final_text or "分析完成，但未能生成文本回复", start, status)

    def _exec_tool(self, tc) -> str:
        """执行单个工具并记录审计"""
        fn_name = tc.function.name
        try: fn_args = json.loads(tc.function.arguments)
        except: fn_args = {}
        t0 = time.time()
        try:
            result = ToolRegistry.execute(fn_name, fn_args, self.user_tier)
            log_tool_call(self.session, fn_name, fn_args, int((time.time()-t0)*1000), True, result=str(result)[:200])
            return result
        except Exception as e:
            log_tool_call(self.session, fn_name, fn_args, int((time.time()-t0)*1000), False, str(e))
            return json.dumps({"error": str(e)})

    def _finish(self, answer: str, start: float, status: str) -> dict:
        elapsed = time.time() - start
        finalize_session(self.session, status)
        # 存入 RAG 知识库
        if self.session.user_id > 0 and status == "completed":
            conversations.add_turn(self.session.user_id, "user", self.session.query)
            conversations.add_turn(self.session.user_id, "assistant", answer[:2000])
        # 存储分析到向量库 (如果包含股票分析)
        try:
            # 尝试从工具调用中提取symbol
            for tc in self.session.tool_calls:
                if tc.tool_name == "deep_analyze" and tc.success:
                    symbol = tc.arguments.get("symbol", "")
                    if symbol:
                        store_analysis(symbol, tc.arguments.get("market", "CN"), {}, answer[:3000])
        except Exception as e: logger.debug(f"RAG存储跳过: {e}")

        return {"answer": answer, "rounds": len(self.session.llm_calls),
                "tool_calls": len(self.session.tool_calls),
                "tokens": self.session.total_tokens, "cost_rmb": round(self.session.total_cost_rmb, 6),
                "time_seconds": round(elapsed, 1), "status": status,
                "session_id": self.session.session_id}
