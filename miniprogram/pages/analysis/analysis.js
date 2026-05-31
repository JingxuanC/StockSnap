const app = getApp();
Page({ data: { report:null, market:'', symbol:'', overall:0, rating:'HOLD', active:'overview', contentHtml:'',
    taskId:'', status:'', elapsed:0, pollTimer:null },
  onLoad(options) {
    // Agent 对话模式
    if (options.mode === 'agent' && app.globalData._agentAnswer) {
      const r = app.globalData._agentAnswer; app.globalData._agentAnswer = null;
      this.setData({ report:{company:{name:''}, rating:{}, scores:{}},
        symbol:'', overall:50, rating:'HOLD', active:'overview',
        contentHtml: '<div style="padding:20rpx;line-height:1.8">'+this.md2html(r.answer||'分析完成')+'</div>' });
      wx.setNavigationBarTitle({title:'AI 分析'});
      return;
    }
    if (options.task_id) {
      this.setData({taskId:options.task_id, symbol:options.symbol||'', status:'pending'});
      this.startPoll();
    } else if (app.globalData._report) {
      this.setReport(app.globalData._report); app.globalData._report = null;
    } else if (options.loaded) {
      this.setData({contentHtml:'<p>加载完成，请返回查看</p>'});
    }
  },
  onUnload() {
    if (this.data.pollTimer) { clearInterval(this.data.pollTimer); this.data.pollTimer = null; }
  },
  // 轮询任务状态
  startPoll() {
    wx.showLoading({title:'AI 分析中...',mask:true});
    let elapsed = 0;
    const timer = setInterval(() => {
      elapsed += 3; this.setData({elapsed});
      app.request('/api/analysis/task/'+this.data.taskId, 'GET', {}, {silent:true})
        .then(task => {
          this.setData({status:task.status});
          if (task.status === 'completed') {
            clearInterval(timer); wx.hideLoading();
            this.setReport(task.result);
          } else if (task.status === 'failed') {
            clearInterval(timer); wx.hideLoading();
            wx.showToast({title:task.error||'分析失败',icon:'none'});
            this.setData({contentHtml:'<p style="color:#e17055">分析失败: '+(task.error||'未知错误')+'</p>'});
          } else if (elapsed > 180) {
            clearInterval(timer); wx.hideLoading();
            this.setData({contentHtml:'<p>分析超时，请稍后重试</p>'});
          } else if (task.status === 'processing') {
            wx.setLoadingTitle({title:'AI 分析中... ' + (elapsed<10?'加载模型':(elapsed<30?'分析基本面':(elapsed<60?'评估估值':'生成报告')))});
          }
        }).catch(() => {}); // 网络抖动静默重试
    }, 3000);
    this.setData({pollTimer:timer});
  },
  // 渲染报告
  setReport(r) {
    this.setData({ report:r, market:r.market||'', symbol:r.symbol||'',
      overall:(r.scores||{}).overall||0, rating:(r.rating||{}).decision||'HOLD' });
    this.renderTab('overview');
    this.loadAnalysisHistory();
  },
  // 后台静默加载历史（ID回填后更新）
  loadAnalysisHistory() {
    app.request('/api/analysis/history?page_size=1').then(d => {
      if (d.records && d.records.length > 0) {
        this.setData({_latestId: d.records[0].id});
      }
    }).catch(()=>{});
  },
  onTab(e) { this.renderTab(e.currentTarget.dataset.t); },
  renderTab(tab) {
    this.setData({active:tab});
    const r = this.data.report;
    if (!r) { this.setData({contentHtml:'<p>等待数据加载...</p>'}); return; }
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
    app.globalData._backtestSymbol = this.data.symbol || '';
    wx.switchTab({url:'/pages/backtest/backtest'});
  },
  // Markdown → HTML
  md2html(md) {
    if (!md) return '';
    return md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/^# (.+)$/gm,'<h1>$1</h1>')
      .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br/>');
  }
});
