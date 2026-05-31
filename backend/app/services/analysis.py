"""StockSnap 核心分析引擎 - 数据采集→LLM分析→技术评分→报告生成"""
import time, logging
from typing import Dict, Any, List
from app.services.llm import LLMService
from app.services.data_collector import MarketDataCollector

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_ZH = """你是一位拥有15年以上经验的资深股票研究分析师。请出具机构级别的全面股票分析报告，只输出有效JSON。

## 分析维度
1. company: 主营业务、商业模式、竞争优势(护城河)、管理层质量、看多论点(3个)、看空论点(3个)
2. thesis: 核心投资观点总结、论点强度(strong/moderate/weak)
3. sector: 行业分类、动态、竞争定位、行业趋势(positive/neutral/negative)、同行(3-5个)
4. catalysts: 短期催化剂(1-3个月)、长期催化剂(6-12个月)、关注日期
5. earnings: 最新季报、收入趋势(growing/stable/declining)、利润率趋势、盈利质量(strong/adequate/weak)
6. valuation: 估值评估、相对历史/同行(cheap/fair/expensive)
7. risks: 前3-5个风险(含影响等级high/medium/low和类别)
8. rating: BUY/HOLD/SELL + 置信度(0-100) + 总结 + 关键理由(3个)

所有文本字段用简体中文。只输出JSON。"""

_SYSTEM_PROMPT_EN = """You are a Senior Equity Research Analyst with 15+ years of experience at a top-tier investment bank. Produce an institutional-quality stock analysis. Output ONLY valid JSON.

Analyze: company (business model, moat, management, bull/bear case), thesis, sector, catalysts, earnings, valuation, risks, rating (BUY/HOLD/SELL + confidence 0-100).

Output only JSON, no other text."""

class StockAnalysisService:
    def __init__(self):
        self.llm = LLMService()
        self.collector = MarketDataCollector()

    def analyze(self, market: str, symbol: str, language: str = "zh-CN") -> dict:
        start = time.time()
        # 1. 采集数据
        data = self.collector.collect_all(market, symbol)
        # 2. 构建提示词
        is_zh = str(language).startswith("zh")
        sys_prompt = _SYSTEM_PROMPT_ZH if is_zh else _SYSTEM_PROMPT_EN
        user_prompt = self._build_user_prompt(data, is_zh)
        # 3. LLM 分析
        llm_start = time.time()
        try:
            result = self.llm.chat_json(sys_prompt, user_prompt)
        except Exception as e:
            logger.error(f"LLM 失败: {e}")
            result = {"rating": {"decision": "HOLD", "confidence": 50, "summary": f"分析失败: {e}", "key_reasons": []}}
        llm_time = time.time() - llm_start
        # 4. 技术评分
        tech = self._tech_score(data)
        # 5. 组装报告
        rating = result.get("rating", {})
        overall = int((rating.get("confidence", 50) + tech) / 2)
        md = self._gen_md(result, tech, is_zh)
        return {"market": market, "symbol": symbol, "company": result.get("company", {}),
                "thesis": result.get("thesis", {}), "sector": result.get("sector", {}),
                "catalysts": result.get("catalysts", {}), "earnings": result.get("earnings", {}),
                "valuation": result.get("valuation", {}), "risks": result.get("risks", []),
                "rating": {"decision": rating.get("decision", "HOLD"), "confidence": rating.get("confidence", 50),
                           "summary": rating.get("summary", ""), "key_reasons": rating.get("key_reasons", [])},
                "scores": {"fundamental": rating.get("confidence", 50), "technical": tech, "overall": overall},
                "report_markdown": md, "model": self.llm.model_name,
                "analysis_time_seconds": round(time.time() - start, 1), "llm_time_seconds": round(llm_time, 1)}

    def _build_user_prompt(self, data: dict, is_zh: bool) -> str:
        text = self.collector.format_for_llm(data)
        return f"{'请分析以下市场数据并输出完整JSON分析报告' if is_zh else 'Analyze the following data and output a complete JSON report'}:\n\n{text}\n\n{'只输出JSON' if is_zh else 'Output ONLY JSON'}."

    def _tech_score(self, data: dict) -> int:
        kd = data.get("kline_daily")
        if kd is None or hasattr(kd, 'data') and kd.data.empty:
            return 50
        df = kd.data if hasattr(kd, 'data') else None
        if df is None or df.empty: return 50
        closes = df['close'].tolist() if 'close' in df.columns else []
        if len(closes) < 20: return 50
        cur = closes[-1]
        # 趋势 40%: MA排列
        ma20 = sum(closes[-20:]) / 20
        trend = 90 if cur > ma20 else 40
        # 动量 30%: RSI
        rsi = self.collector._calc_rsi(closes, 14)
        mom = 15 if rsi >= 70 else (85 if rsi <= 30 else 55)
        # 量 20%
        vol = df['volume'].tolist() if 'volume' in df.columns else []
        vol_score = 50
        if len(vol) >= 2 and sum(vol[:-1]) > 0:
            vr = vol[-1] / (sum(vol[:-1]) / (len(vol) - 1))
            vol_score = 80 if vr > 1.5 and cur > closes[-2] else (20 if vr > 1.5 else 50)
        return max(0, min(100, int(trend * 0.4 + mom * 0.3 + vol_score * 0.2 + 50 * 0.1)))

    def _gen_md(self, r: dict, tech: int, is_zh: bool) -> str:
        lines = []
        c = r.get("company", {}); th = r.get("thesis", {}); s = r.get("sector", {})
        cat = r.get("catalysts", {}); e = r.get("earnings", {}); v = r.get("valuation", {})
        risks = r.get("risks", []); rating = r.get("rating", {})
        dec = {"BUY": "买入", "HOLD": "持有", "SELL": "卖出"}.get(rating.get("decision", "HOLD"), rating.get("decision", "HOLD"))
        lines.append(f"# {c.get('name', 'N/A')} 研究报告")
        lines.append(f"**评级**: {dec} | 置信度: {rating.get('confidence', 50)}/100 | 技术: {tech}/100\n")
        s_text = rating.get("summary", "")
        if s_text: lines.extend(["## 执行摘要", s_text, ""])
        for reason in rating.get("key_reasons", []): lines.append(f"- {reason}")
        lines.append("")
        # 论点
        bs = c.get("business_summary", ""); moat = c.get("moat", "")
        if bs or moat: lines.extend(["## 公司及业务分析", bs, "", f"护城河: {moat}", ""])
        bull, bear = c.get("bull_case", []), c.get("bear_case", [])
        if bull: lines.extend(["### 看多论点"] + [f"- {x}" for x in bull] + [""])
        if bear: lines.extend(["### 看空论点"] + [f"- {x}" for x in bear] + [""])
        # 行业
        if s.get("industry"): lines.extend([f"## 行业分析", s.get("industry", ""), s.get("dynamics", ""), ""])
        # 催化剂
        nt = cat.get("near_term", []); lt = cat.get("long_term", [])
        if nt or lt: lines.extend(["## 催化剂"] + [f"短期: {x}" for x in nt] + [f"长期: {x}" for x in lt] + [""])
        # 盈利
        if e.get("latest_quarter"): lines.extend(["## 盈利分析", e["latest_quarter"], ""])
        # 估值
        if v.get("assessment"): lines.extend(["## 估值分析", v["assessment"], ""])
        # 风险
        if risks:
            lines.append("## 风险分析")
            for rk in risks:
                lines.append(f"- {rk.get('risk', rk) if isinstance(rk, dict) else rk}")
            lines.append("")
        lines.extend(["## 评分", f"基本面: {rating.get('confidence', 50)} | 技术: {tech} | 综合: {int((rating.get('confidence', 50)+tech)/2)}", ""])
        lines.append("---\n*AI生成，仅供参考，不构成投资建议*")
        return "\n".join(lines)
