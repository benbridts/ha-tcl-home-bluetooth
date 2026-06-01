define(function(require, exports, module) {
    var _Vm = null;
    // window.addEventListener('load', function(){
        // options
        var _vueOpts = {
            el: '#TLife-app-news-detail',
            data: function () {
                return {
                    // scroll
                    refreshText: 'Pull down refresh',
                    refreshActiveText: 'Release to refresh',
                    refreshingText: 'Loading...',
                    iconColor: '#F3130A',
                    isOpacity: true,

                    // isApp
                    isApp: false,

                    // header
                    headerOpacity: false,
                    headerColor: '#fff',

                    // scrollTops
                    scrollTops: 100,

                    // API
                    _UA:'',

                    // content
                    dataFlag: false,
                    titles: '',
                    contents: '',
                    times: ''
                }
            },
            created: function(){
                this.isApp = window.isApp;
                 this._UA = window.AppDatas;
            },
            mounted: function(){
                _CloseLoading();
                this._getDetail();
            },
            methods: {
                // scroll
                _onRefresh: function(way) {
                    // console.log(way,"1111");
                    // do something....
                    var _t = this;
                    setTimeout(function(){
                        // _t._getDetail();
                        window.location.reload();
                        // _t.$refs.detialscrollView.finishRefresh()
                    }, 1000)
                },
                // 设置显示刷新loading
                isOpacityFn: function (res) {
                    this.isOpacity = res;
                },
                _onScroll: function(res) {
                    var _t = this;
                    if(!_t.isApp) _t.$refs.tlHeader._scroll(res);
                        else _t.isOpacity = false;
                },
                _FormatDate:function(date) {
                    var _t = this;
                    var d = new Date(date);
                    var resDate = d.getFullYear() + '-' + _t.p((d.getMonth() + 1)) + '-' + _t.p(d.getDate());
                    var resTime = _t.p(d.getHours()) + ':' + _t.p(d.getMinutes()) + ':' + _t.p(d.getSeconds());
                    return (resDate+' '+resTime)
                },
                p: function(s) {
                  return s < 10 ? '0' + s : s
                },
                _getDetail: function() {
                    var _t = this;
                    console.log(_t._UA);
                    if (!_t._UA) {
                        _t.$toast.info('Error');
                        return false;
                    } else {
                        if (!('api' in _t._UA)) {
                            _t.$toast.info('Error');
                            return false;
                        }
                    };
                    fly.request(_t._UA.api, {}, {
                        method: 'get',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                    })
                    .then(function (log) {
                        var _res = log.data;
                        _t.dataFlag = true
                        if (log.status === 200) {
                            _t.titles = _res['jcr:content']['jcr:title'];
                            _t.contents = _res['jcr:content']['detailText'];
                            _t.times = _t._FormatDate(_res['jcr:created'])
                        } else {
                            _t.dataFlag = true;
                            _t.$toast.info('Error');
                        }
                    })
                    .catch(function (err) {
                        // console.log(1111);
                        _t.dataFlag = true;
                        _t.$toast.info('Error');
                    })
                }
            }

        };
        module.exports = window._Vm = _Vm = new Vue(_vueOpts);

   // },false);
});