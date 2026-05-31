Page({ data: { report:{}, market:'', symbol:'', overall:0, rating:'HOLD', active:'overview', contentHtml:'' },
  onLoad(options) {
    if (options.data) {
      const r = JSON.parse(decodeURIComponent(options.data));
      this.setData({ report:r, market:r.market, symbol:r.symbol, overall:r.scores.overall, rating:r.rating.decision });
      this.renderTab('overview');
    }
  },
  onTab(e) { this.renderTab(e.currentTarget.dataset.t); },
  renderTab(tab) {
    this.setData({active:tab});
    const r = this.data.report;
    let md = '';
    if (tab === 'overview') {
      md = '## 评分汇总\n\n基本面 ' + r.scores.fundamental + ' | 技术 ' + r.scores.technical + ' | 综合 ' + r.scores.overall + '\n\n' + (r.rating.summary||'') + '\n\n';
      if (r.rating.key_reasons) { md += '### 关键理由\n'; r.rating.key_reasons.forEach((x,i) => md += (i+1)+'. '+x+'\n')); }
    } else if (tab === 'thesis') {
      md = '## 投资论点\n\n' + (r.thesis?.summary||'') + '\n\n';
      if (r.company?.bull_case) { md += '### 看多\n'; r.company.bull_case.forEach(x => md += '- '+x+'\n')); }
      if (r.company?.bear_case) { md += '### 看空\n'; r.company.bear_case.forEach(x => md += '- '+x+'\n')); }
      md += '\n护城河: ' + (r.company?.moat||'') + '\n';
    } else if (tab === 'sector') {
      md = '## 行业分析\n\n' + (r.sector?.industry||'') + '\n\n' + (r.sector?.dynamics||'') + '\n\n定位: ' + (r.sector?.competitive_positioning||'');
      if (r.sector?.peers) { md += '\n\n同行: ' + r.sector.peers.join(', '); }
    } else if (tab === 'catalysts') {
      md = '## 催化剂\n\n';
      if (r.catalysts?.near_term) { md += '### 短期\n'; r.catalysts.near_term.forEach(x => md += '- '+x+'\n')); }
      if (r.catalysts?.long_term) { md += '### 长期\n'; r.catalysts.long_term.forEach(x => md += '- '+x+'\n')); }
    } else if (tab === 'earnings') {
      md = '## 财报分析\n\n' + (r.earnings?.latest_quarter||'') + '\n\n收入趋势: ' + (r.earnings?.revenue_trend||'') + '\n利润率: ' + (r.earnings?.margin_trend||'') + '\n盈利质量: ' + (r.earnings?.earnings_quality||'');
    } else if (tab === 'valuation') {
      md = '## 估值分析\n\n' + (r.valuation?.assessment||'') + '\n\n相对历史: ' + (r.valuation?.vs_historical||'') + '\n相对同行: ' + (r.valuation?.vs_peers||'');
    } else if (tab === 'risks') {
      md = '## 风险分析\n\n';
      if (r.risks) { r.risks.forEach((x,i) => md += (i+1)+'. '+(typeof x==='string'?x:(x.risk||''))+'\n')); }
    }
    this.setData({contentHtml: md.replace(/\n/g,'<br/>').replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')});
  },
  onBacktest() {
    wx.switchTab({url:'/pages/backtest/backtest?s='+(this.data.symbol||'')});
  }
});
