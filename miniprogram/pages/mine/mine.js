const app = getApp();
Page({ data: { quota:{}, selPlan:'monthly' },
  onShow() { app.checkLogin().then(() => app.request('/api/subscription/quota').then(d => this.setData({quota:d})).catch(()=>{})); },
  onPlan(e) { this.setData({selPlan:e.currentTarget.dataset.p}); },
  onSubscribe() {
    app.request('/api/subscription/create-order','POST',{plan_id:this.data.selPlan}).then(r => {
      wx.showToast({title:'订阅已激活',icon:'success'}); this.onShow();
    }).catch(e => wx.showToast({title:e.message||'订阅失败',icon:'none'}));
  }
});
