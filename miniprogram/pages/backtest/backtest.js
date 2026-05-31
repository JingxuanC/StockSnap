const app = getApp();
const STRATEGIES = [{key:'ma_cross',name:'双均线'},{key:'macd_signal',name:'MACD'},{key:'rsi_reversal',name:'RSI'},{key:'bollinger_breakout',name:'布林带'},{key:'turtle_trend',name:'海龟'}];
Page({ data: { markets:[{code:'CN',name:'A股'},{code:'US',name:'美股'}], mi:0, code:'', strategies:STRATEGIES, strat:'ma_cross', capital:'100000', running:false, result:null },
  onLoad(options) { if (options.s) this.setData({code:options.s}); },
  onShow() {
    app.checkLogin().catch(()=>{});
    if (app.globalData._backtestSymbol) {
      this.setData({code:app.globalData._backtestSymbol});
      app.globalData._backtestSymbol = null;
    }
  },
  onM(e) { this.setData({mi:e.detail.value}); },
  onCode(e) { this.setData({code:e.detail.value.toUpperCase().trim()}); },
  onStrat(e) { this.setData({strat:e.currentTarget.dataset.s}); },
  onCap(e) { this.setData({capital:e.detail.value}); },
  onRun() {
    if (!this.data.code || this.data.running) return;
    this.setData({running:true}); wx.showLoading({title:'回测中...',mask:true});
    app.request('/api/backtest/run','POST',{
      market:this.data.markets[this.data.mi].code, symbol:this.data.code,
      strategy:this.data.strat, initial_capital:parseFloat(this.data.capital)||100000
    }).then(r => { wx.hideLoading(); this.setData({running:false,result:r}); })
      .catch(e => { wx.hideLoading(); this.setData({running:false}); wx.showToast({title:e.message||'回测失败',icon:'none'}); });
  }
});
