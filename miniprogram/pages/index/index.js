const app = getApp();
Page({ data: { markets: [{code:'CN',name:'A股'},{code:'US',name:'美股'}], mi:0, code:'', focus:true, loading:false, quota:null, history:[] },
  onShow() {
    app.checkLogin().then(() => { this.loadData(); this.loadQuota(); });
  },
  loadQuota() { app.request('/api/subscription/quota').then(d => this.setData({quota:d})).catch(()=>{}); },
  loadData() { app.request('/api/analysis/history').then(d => this.setData({history:d.records||[]})).catch(()=>{}); },
  onMarket(e) { this.setData({mi:e.detail.value}); },
  onCode(e) { this.setData({code:e.detail.value.toUpperCase().trim()}); },
  onAnalyze() {
    if (!this.data.code || this.data.loading) return;
    this.setData({loading:true});
    wx.showLoading({title:'提交分析任务...',mask:true});
    // 异步提交 → 立即返回 task_id
    app.request('/api/analysis/analyze-async','POST',{market:this.data.markets[this.data.mi].code,symbol:this.data.code})
      .then(r => { wx.hideLoading(); this.setData({loading:false});
        wx.navigateTo({url:'/pages/analysis/analysis?task_id='+r.task_id+'&symbol='+this.data.code});
        this.loadData(); this.loadQuota(); })
      .catch(e => { wx.hideLoading(); this.setData({loading:false}); wx.showToast({title:e.message||'提交失败',icon:'none'}); });
  },
  onHistory(e) {
    const id = e.currentTarget.dataset.id;
    wx.showLoading({title:'加载中...'});
    app.request('/api/analysis/'+id).then(r => { wx.hideLoading();
      app.globalData._report = r;
      wx.navigateTo({url:'/pages/analysis/analysis?loaded=1'});
    }).catch(() => { wx.hideLoading(); wx.showToast({title:'加载失败',icon:'none'}); });
  }
});
