    var _ua = navigator.userAgent;
    var country;
    var language;
    var environment;

    if (_ua.indexOf('=>') > -1) {
        var _UAData = JSON.parse(_ua.split('=>')[1]);
        console.log(_UAData,'_UAData');
        country=_UAData.country
        language = _UAData.language;
        environment = _UAData.environment
    }
    console.log(_ua,"uuuuu");
    console.log(language,'小灰灰',country);
    console.log(environment,'zzz');

    define(function (require, exports, module) {
        window._Vm = null;
        // options
        var _vueOpts = {
            el: '#TLife-app-video-homey',
            data: function () {
                return {
                    isFinished: false,
                    // scroll
                    refreshText: 'Pull down refresh',
                    refreshActiveText: 'Release to refresh',
                    refreshingText: '',
                    iconColor: '#F3130A',
                    isFinished: false,
                    isOpacity: false,
                    YouTube: [],
                    // more
                    isFinished: false,
                    loadingText: 'Loading...',
                    finishedText: '- END -',
    
                    // isApp
                    isApp: false,
    
                    // header
                    headerOpacity: false,
                    headerColor: '#fff',
    
                    // scrollTops
                    scrollTops: 100,
    
                    // data
                    data: [],
                    test: '',
                    // API
                    APIS: {
                        'test': {
                            'recommended': 'https://obgcmstest.tcl.com/cms/api/recommend-video/pageQuery',
                        },
                        'pro': {
                            'recommended': 'https://obgcms.tcl.com/api/recommend-video/pageQuery',
                        },
                        'uat': {
                            'recommended': 'http://obgcmsin-uat.tclking.com/api/recommend-video/pageQuery',
                        }
                    },
                    // cmsAPI
                    cmsAPIS: {
                        'test': {
                            'recommended': 'https://obgcmstest.tcl.com/cms',
                        },
                        'pro': {
                            'recommended': 'https://obgcms.tcl.com',
                        },
                        'uat': {
                            'recommended': 'http://obgcmsin-uat.tclking.com',
                        }
                    },
                    // Message
                    Nodata: false,
                    FailedToLoad: false,
                    tryloading: false,
                    MNoData: 'No Data ~ ',
                    MFailedToLoadTit: 'Data loading failed',
                    MFailedToLoadTxt: 'Please check your network reload',
                    // user
                    sourceId: '',
                    licenseId: '',
                    regionCode: '',
                    pageNo: 1,
                    pageNo1: 1,
                }
            },
            created: function () {
                this.isApp = window.isApp;
                this.test = window.TCLAPI || 'test';
                this.getVideoList1();
            },
            mounted: function () {
                _CloseLoading();
                // init data
                this.regionCode = country ? country : 'US';
                // getList
                console.log(' App 123')
                this.getVideoList();
            },
            methods: {
                // scroll
                _onRefresh: function (way) {
                    // do something....
                    setTimeout(function () {
                        window.location.reload();
                    }, 1000)
                },
    
                // 设置显示刷新loading
                isOpacityFn: function (res) {
                    // console.log(res);
                    this.isOpacity = res;
                },
                _onScroll: function (res) {
                    var _t = this;
                    // console.log(res);
    
                    if (!_t.isApp) _t.$refs.tlHeader._scroll(res);
                    else _t.isOpacity = false;
                },
    
                // more
                _onEndReached: function () {
                    var _t = this;
                    if (_t.isFinished) {
                        return false
                    };
    
                    // async data
                    _t.Nodata = false;
                    _t.FailedToLoad = false;
                
                    _t.getVideoList();
                    _t.getVideoList1();
                },
                
                getDIQU: function() {
                    
                },
    
                // Ajax
                getVideoList: function () {
                    var _t = this;
                    var _ARR = {
                        region: _t.regionCode,
                        page: _t.pageNo,
                        pageSize: 10
                    };
                    fly.request(_t.APIS[environment]['recommended'], _ARR, {
                        method: "get",
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                    })
                        .then(function (log) {
                            var _Data = log.data;
                            console.log(_Data);
                            if (_Data.status == 1) {
                                let cData = _Data.data;
                                if (cData.data.length < 1) {
                                    if (_t.data.length < 1) {
                                        _t.data = [];
                                        _t.Nodata = true;
                                        _t.FailedToLoad = false;
                                    }else {
                                        return
                                    }
                                } else {
                                    _t.Nodata = false;
                                    _t.FailedToLoad = false;
                                    _t.data = _t.data.concat(cData.data);
                                    _t.pageNo++
                                };
                                setTimeout(function () {
                                    _t.$refs.VideoScrollView.finishLoadMore()
                                }, 500)
                            } else {
                                _t.data = [];
                                _t.Nodata = false;
                                _t.FailedToLoad = true;
                            };
                        })
                        .catch(function (err) {
                            _t.$toast.info('Error');
                            _t.data = [];
                            _t.Nodata = false;
                            _t.isFinished = true;
                            _t.FailedToLoad = true;
                            _t.tryloading = false;
                            _t.$refs.VideoScrollView.finishLoadMore()
                        })
                },
                // to
                getVideoList1: function () {
                    var _t = this;
                    console.log('zz1',_t.cmsAPIS[environment]['recommended'] + '/api/information/page/query?categoryId=' + 2 + '&countryCode=' + country + '&languageCode=' + language + '&page=' + _t.pageNo1 + '&isPutway='+true);
                    axios.get(_t.cmsAPIS[environment]['recommended']+'/api/information/page/query?categoryId=' + 2 + '&countryCode=' + country + '&languageCode=' + language + '&page=' + _t.pageNo1 + '&isPutway='+true, {
                    })
                        .then(function (res) {
                            var _Data = res.data;
                            console.log(_Data)
                            if (_Data.status == 1) {
                                if (_Data.data.data.length < 0) {
                                    _t.YouTube = []
                                    _t.Nodata = true;
                                    _t.FailedToLoad = false;
                                    // _t.YouTube = _t.YouTube.concat(_Data.data.data);
                                } else {
                                    if (_t.pageNo1 > Math.ceil(Number(_Data.data.total) / 10)) {
                                        _t.YouTube = _t.YouTube.concat(_Data.data.data);
                                        return;
                                    } else {
                                        console.log('可以下拉', _t.pageNo1, Math.ceil(Number(_Data.data.total) / 10))
                                        _t.Nodata = false;
                                        _t.FailedToLoad = false;
                                        _t.YouTube = _t.YouTube.concat(_Data.data.data);
                                        _t.pageNo1++;
                                    }
                                };
                                setTimeout(function () {
                                    _t.$refs.VideoScrollView.finishLoadMore()
                                }, 500)
                            } else {
                                // _t.YouTube = _t.YouTube.concat(_Data.data.data);
                                _t.YouTube = []
                                _t.Nodata = false;
                                _t.FailedToLoad = true;
                            };
                        })
                        .catch(function (err) {
                            _t.$toast.info('Error');
                            _t.YouTube = [];
                            _t.Nodata = false;
                            _t.isFinished = true;
                            _t.FailedToLoad = true;
                            _t.tryloading = false;
                            _t.$refs.VideoScrollView.finishLoadMore()
                        })
                },
    
                // JumpDetail
                JumpDetail: function (val) {
                    var _t = this;
                    console.log(val, 1)
                    var _ARR = {
                        sourceId: val.sourceId,
                        vid: val.vid,
                        title: val.title
                    };
                    if (_os.android) {
                        console.log('android')
                        AndroidFn({
                            fn: 'intoVideoDetail',
                            arg: _ARR
                        })
                    } else if (_os.ios) {
                        console.log('ios')
                        IosFn('intoVideoDetail', {
                            arg: _ARR
                        })
                    };
                },
    
                // tab 2 
                JumpDetails: function (val) {
                    var _t = this;
                    console.log(val, 2)
                    var _ARR = {
                        sourceId: 41,
                        vid: val.vid,
                        title: val.title
                    };
                    if (_os.android) {
                        console.log('android')
                        AndroidFn({
                            fn: 'intoVideoDetail',
                            arg: _ARR
                        })
                    } else if (_os.ios) {
                        console.log('ios')
                        IosFn('intoVideoDetail', {
                            arg: _ARR
                        })
                    };
                }
    
            }
    
        };
        module.exports = window._Vm = _Vm = new Vue(_vueOpts);
    });
