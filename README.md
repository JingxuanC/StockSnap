# StockSnap 📊

> AI 驱动的股票分析 Agent — DeepSeek 自主调用工具，生成深度研报 + 策略回测。自托管，个人使用。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-green.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0+-black.svg)](https://flask.palletsprojects.com/)
[![WeChat](https://img.shields.io/badge/wechat-mini%20program-07C160.svg)](https://developers.weixin.qq.com/miniprogram/dev/)

<p align="center">
  <img src="https://img.shields.io/badge/A%E8%82%A1-%E6%94%AF%E6%8C%81-red" alt="A股支持" />
  <img src="https://img.shields.io/badge/%E7%BE%8E%E8%82%A1-%E6%94%AF%E6%8C%81-blue" alt="美股支持" />
  <img src="https://img.shields.io/badge/LLM-DeepSeek-purple" alt="DeepSeek" />
</p>

---

## ✨ 功能

### 🤖 一键 AI 分析
输入股票代码，DeepSeek 自动生成机构级研究报告，覆盖七大维度：

| 维度 | 内容 |
|------|------|
| 📌 概览 | 综合评分 + 买入/持有/卖出建议 |
| 💡 投资论点 | 看多/看空逻辑、竞争优势、护城河 |
| 🏭 行业分析 | 赛道前景、竞争格局、同行对比 |
| ⚡ 催化剂 | 短期/长期事件驱动时间线 |
| 📊 财报分析 | 收入趋势、利润率、盈利质量 |
| 💰 估值分析 | 相对历史/同行估值水平 |
| ⚠️ 风险 | 业务/监管/竞争/宏观 风险清单 |

### 📈 策略回测
内置 5 种经典量化策略，A 股 T+1 规则适配：

| 策略 | 原理 |
|------|------|
| 双均线交叉 | 快线上穿慢线 → 买入，下穿 → 卖出 |
| MACD 金叉死叉 | MACD 与信号线交叉 |
| RSI 超买超卖 | RSI < 30 超卖买入，> 70 超买卖出 |
| 布林带突破 | 突破下轨买入，突破上轨卖出 |
| 海龟趋势 | 唐奇安通道突破 |

### 🎯 数据源
- **A 股**：akshare 主 + 东方财富 HTTP 降级（代理环境自适应）
- **美股**：yfinance 多级降级（fast_info → info → history）

---

## 🏗️ 架构

```
微信小程序 (WeChat Mini Program)
        │
        ▼
┌───────────────────┐
│   Flask REST API   │  ← Python 3.12 + gunicorn
│   /api/auth/*      │     JWT 认证（微信登录）
│   /api/analysis/*  │     AI 分析 + 额度管理
│   /api/backtest/*  │     回测引擎
│   /api/subscription│     订阅 / 额度
└───────┬───────────┘
        │
   ┌────┼────┐
   ▼    ▼    ▼
┌─────┐ ┌─────┐ ┌──────────┐
│ PG  │ │Redis│ │ DeepSeek │
│ 16  │ │  7  │ │  API     │
└─────┘ └─────┘ └──────────┘
```

---

## 🚀 快速开始

### 前提条件
- Python 3.10+ 或 Docker
- DeepSeek API Key（[获取](https://platform.deepseek.com/)）

### 本地运行

```bash
git clone https://github.com/JingxuanC/StockSnap.git
cd StockSnap/backend
cp .env.example .env
# 编辑 .env: 填 DEEPSEEK_API_KEY, 改 SECRET_KEY

pip install -r requirements.txt
python run.py
# 打开 http://localhost:5000 → 输入密码 stocksnap → 开始使用
```

### Docker 部署

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env: 填 DEEPSEEK_API_KEY

docker compose up -d
# 打开 http://your-server:5000
```

---

## 📖 API 文档

所有 API 返回统一格式：`{code: 0, msg: "", data: {...}}`

### 认证

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/wechat-login` | POST | 微信登录，返回 JWT token |
| `/api/auth/user-info` | GET | 获取当前用户信息（需 Bearer token） |

### 分析

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/analysis/analyze` | POST | 执行 AI 分析 `{market, symbol}` |
| `/api/analysis/history` | GET | 历史记录分页 |
| `/api/analysis/<id>` | GET | 获取单条分析详情 |

### 回测

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/run` | POST | 运行回测 `{market, symbol, strategy, params}` |
| `/api/backtest/records` | GET | 历史回测分页 |
| `/api/backtest/strategies` | GET | 可用策略列表 |

### 订阅

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/subscription/quota` | GET | 当前套餐 + 剩余额度 |
| `/api/subscription/plans` | GET | 套餐列表 |
| `/api/subscription/create-order` | POST | 创建订阅订单 |

---

## 🛠️ 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | Flask | 3.0+ |
| LLM | DeepSeek (OpenAI 兼容) | deepseek-chat |
| 数据库 | PostgreSQL | 16 |
| 缓存 | Redis | 7 |
| A股数据 | akshare + 东方财富 HTTP | 1.14+ |
| 美股数据 | yfinance | 0.2+ |
| 部署 | Docker Compose | v2 |
| 前端 | 微信小程序原生 | - |

---

## 📁 项目结构

```
StockSnap/
├── backend/                     # Python Flask 后端
│   ├── app/
│   │   ├── config/settings.py   # 环境变量配置
│   │   ├── data_sources/        # 数据源层
│   │   │   ├── base.py          # 抽象基类 + 数据结构
│   │   │   ├── cn_stock.py      # A股 (akshare + 东方财富降级)
│   │   │   ├── us_stock.py      # 美股 (yfinance)
│   │   │   └── factory.py       # 数据源工厂
│   │   ├── routes/              # API 路由
│   │   │   ├── auth.py          # 微信登录
│   │   │   ├── analysis.py      # AI 分析
│   │   │   ├── backtest.py      # 策略回测
│   │   │   └── subscription.py  # 订阅管理
│   │   ├── services/            # 核心服务
│   │   │   ├── analysis.py      # 分析引擎 (LLM 提示词编排)
│   │   │   ├── backtest.py      # 回测引擎 (T+1)
│   │   │   ├── backtest_strategies.py  # 5 个经典策略
│   │   │   ├── data_collector.py       # 数据采集
│   │   │   └── llm.py           # DeepSeek LLM 封装
│   │   └── utils/               # 工具
│   │       ├── auth.py          # JWT 认证装饰器
│   │       ├── db.py            # PostgreSQL 连接池
│   │       └── logger.py        # 日志
│   ├── migrations/init.sql      # 数据库建表
│   ├── run.py                   # 入口
│   └── Dockerfile
├── miniprogram/                 # 微信小程序
│   ├── app.js / app.json        # 全局配置
│   └── pages/
│       ├── index/               # 首页 (搜索 + 历史)
│       ├── analysis/            # 分析报告页 (7 标签页)
│       ├── backtest/            # 回测页
│       └── mine/                # 我的 (额度 + 订阅)
└── docker-compose.yml           # 一键部署
```

---

## 🔧 开发

```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 本地运行（需要 PostgreSQL）
python run.py

# Docker 重建
docker compose up -d --build
```

---

## 🗺️ 路线图

- [x] AI 一键分析 (DeepSeek)
- [x] A 股 + 美股数据源
- [x] 5 策略回测引擎 (T+1)
- [x] 微信小程序登录
- [x] 月度额度管理
- [ ] 微信支付真实接入（当前为 stub）
- [ ] 订阅到期自动降级
- [ ] Redis 缓存层接入
- [ ] 异步任务队列 (LLM 非阻塞)
- [ ] 单元测试 + 集成测试
- [ ] Swagger API 文档
- [ ] 港股数据源
- [ ] 自定义策略编辑器
- [ ] 多 Agent 联合分析
- [ ] 实盘信号推送

---

## ⚠️ 免责声明

本工具生成的 AI 分析报告仅供研究参考，**不构成任何投资建议**。股票投资有风险，决策需谨慎。开发者不对任何交易损失承担责任。

---

## 📜 License

Apache 2.0 © 2026 StockSnap
