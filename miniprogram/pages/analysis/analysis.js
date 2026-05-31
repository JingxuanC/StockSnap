const app = getApp();
Page({ data: { report:{}, market:'', symbol:'', overall:0, rating:'HOLD', active:'overview', contentHtml:'' },
  onLoad(options) {
    let r = null;
    if (app.globalData._report) {
      r = app.globalData._report; app.globalData._report = null;
    } else if (options.data) {
      try { r = JSON.parse(decodeURIComponent(options.data)); } catch(e) { r = null; }
    }
    if (r) {
      this.setData({ report:r, market:r.market||'', symbol:r.symbol||'',
        overall:(r.scores||{}).overall||0, rating:(r.rating||{}).decision||'HOLD' });
      this.renderTab('overview');
    }
  },
  onTab(e) { this.renderTab(e.currentTarget.dataset.t); },
  renderTab(tab) {
    this.setData({active:tab});
    const r = this.data.report;
    const sc = r.scores || {}; const rt = r.rating || {}; const co = r.company || {};
    const se = r.sector || {}; const ct = r.catalysts || {}; const ea = r.earnings || {};
    const vl = r.valuation || {}; const rs = r.risks || [];
    let md = '';
    if (tab === 'overview') {
      md = '## 评分汇总\n\n基本面 '+(sc.fundamental||0)+' | 技术 '+(sc.technical||0)+' | 综合 '+(sc.overall||0)+'\n\n'+(rt.summary||'')+'\n\n';
      if (rt.key_reasons) { md += '### 关键理由\n'; rt.key_reasons.forEach(function(x,i){ md += (i+1)+'. '+x+'\n'; }); }
    } else if (tab === 'thesis') {
      md = '## 投资论点\n\n'+(r.thesis?.summary||'')+'\n\n';
      if (co.bull_case) { md += '### 看多\n'; co.bull_case.forEach(function(x){ md += '- '+x+'\n'; }); }
      if (co.bear_case) { md += '### 看空\n'; co.bear_case.forEach(function(x){ md += '- '+x+'\n'; }); }
      md += '\n护城河: '+(co.moat||'')+'\n';
    } else if (tab === 'sector') {
      md = '## 行业分析\n\n'+(se.industry||'')+'\n\n'+(se.dynamics||'')+'\n\n定位: '+(se.competitive_positioning||'');
      if (se.peers) md += '\n\n同行: '+se.peers.join(', ');
    } else if (tab === 'catalysts') {
      md = '## 催化剂\n\n';
      if (ct.near_term) { md += '### 短期\n'; ct.near_term.forEach(function(x){ md += '- '+x+'\n'; }); }
      if (ct.long_term) { md += '### 长期\n'; ct.long_term.forEach(function(x){ md += '- '+x+'\n'; }); }
    } else if (tab === 'earnings') {
      md = '## 财报分析\n\n'+(ea.latest_quarter||'')+'\n\n收入趋势: '+(ea.revenue_trend||'')+'\n利润率: '+(ea.margin_trend||'')+'\n盈利质量: '+(ea.earnings_quality||'');
    } else if (tab === 'valuation') {
      md = '## 估值分析\n\n'+(vl.assessment||'')+'\n\n相对历史: '+(vl.vs_historical||'')+'\n相对同行: '+(vl.vs_peers||'');
    } else if (tab === 'risks') {
      md = '## 风险分析\n\n';
      rs.forEach(function(x,i){ md += (i+1)+'. '+(typeof x==='string'?x:(x.risk||''))+'\n'; });
    }
    this.setData({contentHtml: md.replace(/\n/g,'<br/>').replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')});
  },
  onBacktest() {
    // switchTab不支持query参数，用globalData传递
    app.globalData._backtestSymbol = this.data.symbol || '';
    wx.switchTab({url:'/pages/backtest/backtest'});
  }
});
