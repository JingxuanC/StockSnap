"""AI Agent API - 自然语言驱动的股票分析"""
import logging
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.utils.rate_limiter import rate_limit
from app.agent.engine import AgentEngine
from app.agent.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)
agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

@agent_bp.route('/chat', methods=['POST'])
@login_required
@rate_limit(per_second=1, burst=3)
def chat():
    """Agent 对话接口 - 用户自然语言→Agent自主调工具→返回结果"""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'code': 400, 'msg': '请输入你想了解的问题', 'data': None}), 400
    # 确定用户等级
    from app.utils.db import execute_query
    u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
    tier = "pro" if (u and u[0].get('is_subscribed')) else "free"
    # 上下文
    context = {}
    if data.get('symbol'):
        context['focus_symbol'] = data['symbol']
        context['focus_market'] = data.get('market', 'CN')

    agent = AgentEngine(user_tier=tier)
    skill_ids = data.get('skills', [])  # 用户选择的Skill
    result = agent.run(query, context, skills=skill_ids)
    return jsonify({'code': 0, 'data': result})

@agent_bp.route('/tools', methods=['GET'])
def list_tools():
    """列出当前用户可用的工具"""
    return jsonify({'code': 0, 'data': {
        'tools': ToolRegistry.list_for_tier("free"),
        'categories': ToolRegistry.get_categories(),
        'total': len(ToolRegistry._tools)
    }})
