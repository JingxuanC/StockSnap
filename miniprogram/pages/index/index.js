const app = getApp();
Page({ data: { markets: [{code:'CN',name:'A股'},{code:'US',name:'美股'}], mi:0, code:'', focus:true, loading:false, quota:null, history:[] },
  onShow() {
    app.checkLogin().then(() => this.loadData());
    app.request('/api/subscription/quota').then(d => this.setData({quota:d})).catch(()=>{});
  },
  loadData() { app.request('/api/analysis/history').then(d => this.setData({history:d.records||[]})).catch(()=>{}); },
  onMarket(e) { this.setData({mi:e.detail.value}); },
  onCode(e) { this.setData({code:e.detail.value.toUpperCase().trim()}); },
  onAnalyze() {
    if (!this.data.code || this.data.loading) return;
    this.setData({loading:true});
    wx.showLoading({title:'AI分析中...',mask:true});
    app.request('/api/analysis/analyze','POST',{market:this.data.markets[this.data.mi].code,symbol:this.data.code})
      .then(r => { wx.hideLoading(); this.setData({loading:false});
        wx.navigateTo({url:'/pages/analysis/analysis?data='+encodeURIComponent(JSON.stringify(r))});
        this.loadData(); app.request('/api/subscription/quota').then(d => this.setData({quota:d})).catch(()=>{}); })
      .catch(e => { wx.hideLoading(); this.setData({loading:false}); wx.showToast({title:e.message||'分析失败',icon:'none'}); });
  },
  onHistory(e) {
    const id = e.currentTarget.dataset.id;
    app.request('/api/analysis/'+id).then(r => { wx.navigateTo({url:'/pages/analysis/analysis?data='+encodeURIComponent(JSON.stringify(r))}); }).catch(()=>{});
  }
});
