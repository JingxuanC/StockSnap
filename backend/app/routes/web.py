"""Web 页面路由 - 自托管前端"""
from flask import Blueprint, render_template

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def index():
    return render_template('index.html')
