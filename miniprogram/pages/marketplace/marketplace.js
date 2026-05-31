const app = getApp();
Page({ data: { tier:'free', mcps:[], skills:[], activatedCount:0 },
  onShow() {
    app.checkLogin().then(() => this.load());
  },
  load() {
    app.request('/api/marketplace/my-toolkit').then(d => {
      this.setData({ tier: d.tier, mcps: d.mcps, skills: d.skills,
        activatedCount: d.mcps.filter(m => m.activated).length });
    }).catch(()=>{});
  },
  onToggleMCP(e) {
    const id = e.currentTarget.dataset.id;
    const action = e.detail.value ? 'activate' : 'deactivate';
    app.request('/api/marketplace/mcps/'+id+'/'+action, 'POST').then(() => {
      wx.showToast({title: e.detail.value?'已启用':'已停用', icon:'success'}); this.load();
    }).catch(() => wx.showToast({title:'操作失败', icon:'none'}));
  },
  onUseSkill(e) {
    app.globalData._agentQuery = e.currentTarget.dataset.q;
    wx.switchTab({url:'/pages/index/index'});
  },
  onUpgrade() { wx.switchTab({url:'/pages/mine/mine'}); }
});
