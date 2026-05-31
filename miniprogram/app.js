App({
  globalData: { token: null, userInfo: null, baseUrl: 'http://localhost:5000', quota: null },
  onLaunch() {
    const token = wx.getStorageSync('token'); const ui = wx.getStorageSync('userInfo');
    if (token && ui) { this.globalData.token = token; this.globalData.userInfo = ui; }
  },
  checkLogin() {
    if (this.globalData.token) return Promise.resolve();
    const self = this;
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => {
          if (!res.code) return reject('login code empty');
          wx.request({ url: self.globalData.baseUrl + '/api/auth/wechat-login', method: 'POST', data: { code: res.code },
            success: (r) => {
              if (r.data && r.data.code === 0) {
                const d = r.data.data;
                self.globalData.token = d.token; self.globalData.userInfo = d.user;
                wx.setStorageSync('token', d.token); wx.setStorageSync('userInfo', d.user);
                resolve(d);
              } else { wx.showToast({ title: r.data.msg || '登录失败', icon: 'none' }); reject(r.data.msg); }
            }, fail: reject });
        }, fail: reject });
    });
  },
  request(url, method = 'GET', data = {}) {
    const self = this;
    return new Promise((resolve, reject) => {
      wx.request({ url: self.globalData.baseUrl + url, method, data,
        header: { 'Authorization': 'Bearer ' + (self.globalData.token || ''), 'Content-Type': 'application/json' },
        timeout: 90000,
        success: (res) => {
          if (res.statusCode === 401 || (res.data && res.data.code === 401)) {
            return self.wechatLogin().then(() => self.request(url, method, data)).then(resolve).catch(reject);
          }
          if (res.data && res.data.code === 0) resolve(res.data.data);
          else reject(new Error((res.data && res.data.msg) || '请求失败'));
        }, fail: reject });
    });
  },
  wechatLogin() {
    return new Promise((resolve, reject) => {
      wx.login({ success: (res) => {
        if (!res.code) return reject('code empty');
        wx.request({ url: this.globalData.baseUrl + '/api/auth/wechat-login', method: 'POST', data: { code: res.code },
          success: (r) => {
            if (r.data && r.data.code === 0) {
              this.globalData.token = r.data.data.token; this.globalData.userInfo = r.data.data.user;
              wx.setStorageSync('token', r.data.data.token); wx.setStorageSync('userInfo', r.data.data.user);
              resolve();
            } else reject(r.data.msg);
          }, fail: reject });
      }, fail: reject });
    });
  }
});
