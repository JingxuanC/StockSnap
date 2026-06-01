"""AI Agent API v2 - RAG增强 + 全链路观测"""
import logging
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.rate_limiter import rate_limit
from app.agent.engine import AgentEngine
from app.agent.tool_registry import ToolRegistry
from app.agent.observability import metrics
from app.agent.rag import get_knowledge_stats

logger = logging.getLogger(__name__)
agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

@agent_bp.route('/chat', methods=['POST'])
@login_required
@rate_limit(per_second=1, burst=3)
def chat():
    """Agent 对话 - RAG增强版"""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'code': 400, 'msg': '请输入你想了解的问题', 'data': None}), 400
    tier = "free"  # 个人自托管无需订阅等级
    try:
        from app.utils.db import execute_query
        u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
        tier = "pro" if (u and u[0].get('is_subscribed')) else "free"
    except Exception: pass
    context = {}
    if data.get('symbol'):
        context['focus_symbol'] = data['symbol']
        context['focus_market'] = data.get('market', 'CN')
    agent = AgentEngine(user_id=g.user_id, user_tier=tier)
    result = agent.run(query, context, skills=data.get('skills', []))
    return jsonify({'code': 0, 'data': result})

@agent_bp.route('/tools', methods=['GET'])
def list_tools():
    return jsonify({'code': 0, 'data': {'tools': ToolRegistry.list_for_tier("free"),
        'categories': ToolRegistry.get_categories(), 'total': len(ToolRegistry._tools)}})

@agent_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Agent 运行指标"""
    return jsonify({'code': 0, 'data': {
        'agent_metrics': metrics.snapshot(),
        'knowledge_base': get_knowledge_stats()
    }})
