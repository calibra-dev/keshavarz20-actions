'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const js=fs.readFileSync('/qa/iran-cities.js','utf8');
const admin=fs.readFileSync('/qa/admin.js','utf8');
const ctx={window:{}};
vm.runInNewContext(js,ctx,{timeout:5000});
const catalog=ctx.window.K20IranCities;
assert(catalog && typeof catalog==='object','missing city catalog');
assert.strictEqual(Object.keys(catalog).length,31,'province count');
const count=Object.values(catalog).reduce((a,x)=>a+x.length,0);
assert.strictEqual(count,1494,'catalog entry count');
for(const [province,cities] of Object.entries(catalog)){
  assert(/^IR-[0-9]{2}$/.test(province),'invalid province code '+province);
  assert(Array.isArray(cities)&&cities.length>0,'empty province '+province);
}
console.log('CATALOG_31_PROVINCES_1494_CITIES_OK');
const i=admin.indexOf('function normalizeRegionText(');
const j=admin.indexOf('function canonicalCitiesFor(',i+1);
assert(i>=0 && j>i,'matching section cannot be located');
const helpers=admin.slice(i,j);
const v={};
vm.runInNewContext(helpers+'\nthis.k20qa={areaMatchScore:areaMatchScore,mapLiveCitiesToAreas:mapLiveCitiesToAreas};',v,{timeout:5000});
const {areaMatchScore,mapLiveCitiesToAreas}=v.k20qa;
function shouldMatch(a,b) {assert(areaMatchScore(a,b)>0,a+' should match '+b);}
function shouldNotMatch(a,b) {assert.strictEqual(areaMatchScore(a,b),0,a+' incorrectly matched '+b);}
for(const [a,b] of [['آبادان','آبادان'],['شيراز','شیراز'],['نجف آباد','نجف‌آباد'],['كاشان','کاشان']]) shouldMatch(a,b);
for(const [a,b] of [['آبژدان','آبادان'],['نصرآباد','نجف آباد'],['ریحان','ریگان'],['علامرودشت','مرودشت'],['بناب مرند','بناب'],['خرم آباد','خرم آبادان']]) shouldNotMatch(a,b);
console.log('EXACT_MATCH_POSITIVE_AND_NEGATIVE_OK');
const areas=['آبادان','ریگان','نجف آباد','مرودشت','بناب','شیراز'].map(name=>({name}));
const live={cities:[
 {name:'آبژدان',orders:2,customers:2,revenue:200},
 {name:'ریحان',orders:3,customers:3,revenue:300},
 {name:'نصرآباد',orders:4,customers:4,revenue:400},
 {name:'علامرودشت',orders:5,customers:5,revenue:500},
 {name:'بناب مرند',orders:6,customers:6,revenue:600},
 {name:'شیراز',orders:7,customers:7,revenue:700}
]};
const mapped=mapLiveCitiesToAreas(live,areas);
for(const name of ['آبادان','ریگان','نجف آباد','مرودشت','بناب']){
  assert.strictEqual(mapped[name].revenue,0,'leaked sale to '+name);
  assert.strictEqual(mapped[name].orders,0,'leaked order to '+name);
}
assert.strictEqual(mapped['شیراز'].revenue,700);
assert.strictEqual(mapped['شیراز'].orders,7);
assert.strictEqual(Object.keys(mapped).length,areas.length,'unexpected map geometry created');
console.log('NO_FUZZY_COLOR_LEAK_AND_NO_NEW_POLYGONS_OK');
console.log('LIVE_JS_DOCKER_QA_PASS');
