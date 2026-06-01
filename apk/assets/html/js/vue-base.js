/*
* @Author: mcclcm
* @Date:   2019-10-15 15:41:37
* @Last Modified by:   mcclcm
* @Last Modified time: 2019-10-15 15:45:31
*/
var _eval=window||(0,eval)('this');

// header
var _tlheader={template:"<header slot=\"header\" class=\"TLife-header\" v-if=\"!isApp\" id=\"TLife-header\" ref=\"header\" :style=\"{backgroundColor:(headeropacity?'':headercolor)}\"><div class=\"TLife-header-in\"><div class=\"TLife-header-item\"><span class=\"TLife-back-btn touch-active\" @click=\"back\"></span></div><div class=\"TLife-header-item-center\"><span class=\"TLife-header-item-in\">{{title}}</span></div><div class=\"TLife-header-item\"><slot name=\"right\"></slot></div></div></header>",props:{title:{type:String,default:''},headeropacity:{type:Boolean,default:false},headercolor:{type:String,default:'#fff'},scrolltops:{type:Number,default:100}},data:function(){return{}},methods:{back:function(){window.history.go(-1)},_scroll:function(res){var _t=this;var _abs=Math.abs(res.scrollTop);if(_t.headeropacity){if(Math.abs(res.scrollTop)>35){_t.$emit('isopacitys',false)}else{_t.$emit('isopacitys',true)};if(Math.abs(res.scrollTop)>0){var _tops=(_abs/_t.scrolltops)/2,_opacity=_tops?((_tops+0.2).toFixed(1)):_tops;_t.$refs.header.style.backgroundColor='rgba(255,255,255,'+_opacity+')'}else{_t.$refs.header.style.backgroundColor=''}}else{_t.$emit('isopacitys',false)}}}};
Vue.component('tl-header', _tlheader);
var _Switch = {
    template: '<div class="switch-tab" :class="[disabled ? \'disabled\' : \'\', val ? \'active\' : \'\']" @click.stop="$_onChange($event)"><span></span></div>',
    props: {
        vals: '',
        v: '',
        disabled: {
            type: Boolean,
            default: false,
        },
    },
    computed: {
        val: function() {
            var _t = this;
            // console.log(typeof _t.vals);
            if ((typeof _t.vals) === 'string') {
                return !!parseInt(_t.vals)
            }else
            if ((typeof _t.vals) === 'number') {
                // console.log(!!_t.vals);
                return !!_t.vals
            } else
            if ((typeof _t.vals) === 'boolean') {
                return _t.vals;
            }
        }
    },
    methods: {
        $_onChange(event) {
            var _t = this;
            if (_t.disabled) {
                return false
            };
            _t.$emit('change', {vals: _t.vals, v:_t.v,event: event})
        }
    }
}
Vue.component('tl-switch-tab', _Switch);