"""MCP & Skill 市场 - 浏览、激活、管理"""
import logging
from flask import Blueprint, request, jsonify, g
from app.utils.auth import login_required
from app.agent.mcp_registry import MCPRegistry
from app.agent.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)
marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/api/marketplace')

@marketplace_bp.route('/mcps', methods=['GET'])
@login_required
def list_mcps():
    """列出可用 MCP 服务器"""
    from app.utils.db import execute_query
    u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
    tier = "pro" if (u and u[0].get('is_subscribed')) else "free"
    activated = MCPRegistry.get_user_mcps(g.user_id, tier)
    mcps = MCPRegistry.list_available(tier)
    for m in mcps:
        m['activated'] = m['id'] in activated
    return jsonify({'code': 0, 'data': {'mcps': mcps, 'tier': tier, 'activated_count': len(activated)}})

@marketplace_bp.route('/mcps/<mcp_id>/activate', methods=['POST'])
@login_required
def activate_mcp(mcp_id):
    """激活一个 MCP"""
    from app.utils.db import execute_query
    u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
    tier = "pro" if (u and u[0].get('is_subscribed')) else "free"
    ok = MCPRegistry.activate(g.user_id, mcp_id, tier)
    return jsonify({'code': 0 if ok else 400, 'msg': '已激活' if ok else '激活失败（等级不足或不存在）'})

@marketplace_bp.route('/mcps/<mcp_id>/deactivate', methods=['POST'])
@login_required
def deactivate_mcp(mcp_id):
    """停用一个 MCP"""
    MCPRegistry.deactivate(g.user_id, mcp_id)
    return jsonify({'code': 0, 'msg': '已停用'})

@marketplace_bp.route('/skills', methods=['GET'])
@login_required
def list_skills():
    """列出可用 Skills"""
    from app.utils.db import execute_query
    u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
    tier = "pro" if (u and u[0].get('is_subscribed')) else "free"
    skills = SkillRegistry.list_available(tier)
    return jsonify({'code': 0, 'data': {'skills': skills, 'tier': tier}})

@marketplace_bp.route('/my-toolkit', methods=['GET'])
@login_required
def my_toolkit():
    """获取用户当前的工具包"""
    from app.utils.db import execute_query
    u = execute_query("SELECT is_subscribed FROM users WHERE id = %s", (g.user_id,))
    tier = "pro" if (u and u[0].get('is_subscribed')) else "free"
    mcps = MCPRegistry.list_available(tier)
    activated = MCPRegistry.get_user_mcps(g.user_id, tier)
    return jsonify({'code': 0, 'data': {
        'tier': tier,
        'mcps': [m for m in mcps if m['id'] in activated],
        'skills': SkillRegistry.list_available(tier),
        'upgrade_needed': len([m for m in mcps if not m['accessible']]) > 0
    }})
