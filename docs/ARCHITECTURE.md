# StockSnap AI Agent 架构

> 基于 Anthropic "Building Effective Agents" + 2025 生产级 AI Agent 最佳实践设计

## 核心哲学

> "Every agent = Environment + Tools + System Prompt, called in a loop. Radical simplicity." — Anthropic

```
Agent = LLM + Harness
Harness = Memory + Tools + Observability + Evaluation + Governance
```

## 四层生产架构

```
┌──────────────────────────────────────────────────────────┐
│                    Interaction & Orchestration            │
│  ReAct Loop · Tool Dispatch · Skill Injection · Routing  │
├──────────────────────────────────────────────────────────┤
│                    Memory & RAG                           │
│  Short-Term (Session) → Mid-Term (Summaries) →          │
│  Long-Term (Vector Store) · Hybrid Retrieval             │
├──────────────────────────────────────────────────────────┤
│                    Compute & Execution                    │
│  DeepSeek API · Tool Sandbox · Parallel Calls · Cache    │
├──────────────────────────────────────────────────────────┤
│                    Observability & Governance             │
│  Token Tracking · Audit Trail · Cost Attribution ·       │
│  Evals (Faithfulness/Hallucination) · Guardrails         │
└──────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. Agent Engine
- **ReAct 循环**: Think → Act → Observe → (loop)
- **并行工具调用**: DeepSeek 支持 parallel function calling
- **降级策略**: 工具失败 → 明确告知用户，不编造
- **迭代上限**: 最多 5 轮工具调用，防止死循环

### 2. Memory & RAG
- **短期记忆**: 当前会话的对话历史（最近 20 轮）
- **中期记忆**: 会话摘要（LLM 自动生成，每 10 轮触发）
- **长期记忆**: ChromaDB 向量库
  - 历史分析报告 → 嵌入 → 下次直接检索
  - 公司档案/行业数据 → 预计算后存储
  - 用户偏好 → 个性化
- **混合检索**: Dense (余弦相似度) + Sparse (BM25 关键词) + Recency Boost

### 3. Tool Registry
- 工具按能力分类：data / analysis / backtest / news
- 工具按等级分配：free / pro
- 工具描述符合 OpenAI function calling 规范

### 4. Observability
- **Token 追踪**: input/output/total tokens per call
- **成本归因**: tokens × pricing → cost_usd
- **审计日志**: 每次 LLM 调用 + 工具调用全程记录
- **延迟监控**: P50/P95/P99 延迟
- **质量评估**: Faithfulness / Hallucination / Relevance

### 5. Conversation Manager
- 多轮对话支持
- 对话历史持久化
- 上下文窗口管理（接近上限时自动压缩）
- 用户身份绑定

## 数据流

```
用户: "茅台值得买吗"
       │
       ▼
[1] RAG 检索 (<100ms)
    ├─ 向量库: "茅台 投资分析" → 找到 3 天前的报告
    ├─ 预计算: PE=35, ROE=25%, 技术面多头
    └─ 上下文: 上次分析评级 BUY, 置信度 78
       │
       ▼
[2] Agent 推理 (已有上下文)
    ├─ LLM 判断: "RAG数据是3天前的，需要刷新实时行情"
    ├─ 并行调用: get_realtime + get_kline (2个工具同时调)
    │             → 价格+1.2%, 成交量放大
    ├─ 汇总: "基本面没变(PEG0.8合理)，技术面改善(放量突破MA20)"
    ├─ 评级: 🟡持有 (上次是🟢买入，但价格已涨8%接近目标价)
    │
    ▼
[3] 审计记录
    ├─ 写入: {user, query, tokens, cost, latency, tools, eval}
    ├─ 更新向量库: 本次分析报告 → 嵌入 → 存储
    └─ 更新对话历史
```

## 与现有代码的映射

| 架构层 | 现有模块 | 需新增 |
|--------|----------|--------|
| Agent Engine | `agent/engine.py` (ReAct) | 并行调用、降级策略 |
| Tool Registry | `agent/tool_registry.py` | ✅ |
| MCP 管理 | `agent/mcp_registry.py` | ✅ |
| Skill 管理 | `agent/skill_registry.py` | ✅ |
| RAG / 向量库 | ❌ 不存在 | **ChromaDB 嵌入存储** |
| 对话记忆 | ❌ 不存在 | **ConversationManager** |
| Token 追踪 | ❌ 不存在 | **TokenTracker** |
| 审计日志 | ❌ 不存在 | **AuditLogger** |
| 质量评估 | ❌ 不存在 | **EvalJudge** |
| 预计算层 | ❌ 不存在 | **PrecomputeWorker** |

## 实施优先级

| 优先级 | 模块 | 理由 | 工作量 |
|--------|------|------|--------|
| P0 | TokenTracker + AuditLogger | 没有观测就无法优化 | 2h |
| P0 | 工具并行调用 | 速度从 5轮串行→1轮并行, 5x提升 | 1h |
| P1 | ChromaDB 向量存储 | 历史分析不再浪费 | 3h |
| P1 | ConversationManager | 多轮对话能力 | 2h |
| P2 | EvalJudge | 幻觉检测 | 3h |
| P2 | PrecomputeWorker | 离线预计算 | 2h |
