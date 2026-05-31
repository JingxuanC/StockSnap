const app = getApp();
Page({ data: { query:'', focus:true, loading:false, quota:null, history:[] },
  onShow() { app.checkLogin().then(() => { this.loadData(); this.loadQuota(); }); },
  loadQuota() { app.request('/api/subscription/quota').then(d => this.setData({quota:d})).catch(()=>{}); },
  loadData() { app.request('/api/analysis/history').then(d => this.setData({history:d.records||[]})).catch(()=>{}); },
  onQuery(e) { this.setData({query:e.detail.value}); },
  // Agent 对话
  onChat() {
    if (!this.data.query || this.data.loading) return;
    this.setData({loading:true});
    wx.showLoading({title:'AI分析中...',mask:true});
    app.request('/api/agent/chat','POST',{query:this.data.query})
      .then(r => { wx.hideLoading(); this.setData({loading:false,query:''});
        app.globalData._agentAnswer = r;
        wx.navigateTo({url:'/pages/analysis/analysis?mode=agent'});
        this.loadData(); this.loadQuota(); })
      .catch(e => { wx.hideLoading(); this.setData({loading:false}); wx.showToast({title:e.message||'请求失败',icon:'none'}); });
  },
  onQuickAsk(e) {
    this.setData({query:e.currentTarget.dataset.q}); this.onChat();
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
