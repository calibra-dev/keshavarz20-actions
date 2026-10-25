'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const assert = require('assert'), crypto = require('crypto');
const root = process.env.QA_DIR || '/qa';
const admin = fs.readFileSync(path.join(root, 'admin.js'), 'utf8');
const hash = text => crypto.createHash('sha256').update(text).digest('hex');
const contract = {
  "source_sha256": "ebbf60a0b7fa0dba37d42d8438d272510d94502dc3674d3052a6074b57fbef1b",
  "patched_sha256": "3a8d306767a467e026775d46d51a56937f986904f5f729b1f3a95b3258623828",
  "replacements": [
    [
      "  function exactAreaKey(value) {\n    return String(value == null ? '' : value)\n",
      "  function exactAreaKey(value) {\n    return String(value == null ? '' : value)\n      .replace(/\\u0640/g, '')\n"
    ],
    [
      "      var best = null, bestScore = 0;",
      "      var best = null, bestScore = 0, ambiguous = false;"
    ],
    [
      "        var score = areaMatchScore(city.name, area.name);",
      "        var score = areaMatchScore(city.name, area.name);\n        if (score > 0 && best && best.name !== area.name) ambiguous = true;"
    ],
    [
      "      if (!best || bestScore <= 0) return;",
      "      if (!best || bestScore <= 0 || ambiguous) return;"
    ]
  ]
};
assert.strictEqual(hash(admin), contract.source_sha256, 'unexpected deployed source; review patch again');
let patched = admin;
for (const [before, after] of contract.replacements) {
  assert.strictEqual(patched.split(before).length - 1, 1, 'patch anchor not unique');
  patched = patched.replace(before, after);
}
assert.strictEqual(hash(patched), contract.patched_sha256, 'patch differs from delivered admin.js');
new vm.Script(admin); new vm.Script(patched);
console.log('LIVE_SOURCE_SHA256=' + hash(admin));
console.log('PATCHED_SOURCE_SHA256=' + hash(patched));
const releaseAssets = {"iran-cities.js": "f3a0785722c858f28e6f0d3789cbf53fedb634ff786d1782a116e6f31d3841bf", "province-geometry.js": "3096bfb24f8e9994b6e44b6193f540631ef1830d098167cbb9fa47f646be1776", "adaptive-geo.js": "9b6dc09812c80ed43ff27886273d7637e0fd1938348a17322017e97471c25fdc"};
const ctx = {window:{}};
for (const name of ['iran-cities.js', 'province-geometry.js', 'adaptive-geo.js']) {
  const content = fs.readFileSync(path.join(root, name), 'utf8');
  assert.strictEqual(hash(content), releaseAssets[name], 'live asset differs from exact 1.8.17 ZIP: '+name);
  vm.runInNewContext(content, ctx, {timeout:5000});
}
const catalog = ctx.window.K20IranCities;
assert.strictEqual(Object.keys(catalog).length, 31);
assert.strictEqual(Object.values(catalog).reduce((n, rows) => n + rows.length, 0), 1494);
for (const [code, cities] of Object.entries(catalog)) {
  assert(/^IR-[0-9]{2}$/.test(code)); assert(cities.length > 0);
}
console.log('CATALOG_31_PROVINCES_1494_CITIES_OK');
function helpers(text) {
  const i = text.indexOf('function normalizeRegionText(');
  const j = text.indexOf('function canonicalCitiesFor(', i);
  assert(i >= 0 && j > i);
  const v = {};
  vm.runInNewContext(text.slice(i,j) + ';this.api={areaMatchScore,mapLiveCitiesToAreas,exactAreaKey};', v, {timeout:5000});
  return v.api;
}
const baseline = helpers(admin), fixed = helpers(patched);
const positive = [['آبادان','آبادان'],['شيراز','شیراز'],['كاشان','کاشان'],['نجف آباد','نجف‌آباد'],['نجف\u200dآباد','نجف آباد'],['شيراز','شىراز']];
const negative = [['آبژدان','آبادان'],['نصرآباد','نجف آباد'],['ریحان','ریگان'],['علامرودشت','مرودشت'],['بناب مرند','بناب'],['خرم آباد','خرم آبادان'],['شیراز۱','شیراز'],['شهر شیراز','شیراز'],['ابادان','آبادان'],['شيراز شمالی','شیراز'],['شیراز','شیرا'],['',''],['ـ',''],[null,'شیراز']];
for (const api of [baseline, fixed]) {
  for (const [a,b] of positive) { assert(api.areaMatchScore(a,b)>0); assert(api.areaMatchScore(b,a)>0); }
  for (const [a,b] of negative) { assert.strictEqual(api.areaMatchScore(a,b),0, a+' / '+b); assert.strictEqual(api.areaMatchScore(b,a),0); }
}
console.log('LIVE_AND_PATCHED_Y_K_EXACT_POSITIVES_AND_NEGATIVES_OK');
assert.strictEqual(baseline.areaMatchScore('شيـراز','شیراز'), 0);
console.log('LIVE_KNOWN_DEFECT_TATWEEL_REPRODUCED_NOT_FIXED_ON_SITE');
for (const [a,b] of [['شيـراز','شیراز'],['شــیـراز','شيراز'],['كـاشان','کاشان'],['نـجف‌آباد','نجف آباد']]) {
  assert(fixed.areaMatchScore(a,b)>0); assert(fixed.areaMatchScore(b,a)>0);
}
console.log('PATCHED_TATWEEL_POSITIVES_OK');
for (const api of [baseline, fixed]) {
  const areas = ['آبادان','ریگان','نجف آباد','مرودشت','بناب','شیراز'].map(name=>({name}));
  const row = {cities:negative.slice(0,5).map(([name],i)=>({name,orders:i+2,customers:i+2,revenue:(i+2)*100})).concat([{name:'شيراز',orders:7,customers:7,revenue:700}])};
  const snapshot = JSON.stringify({areas,row});
  const mapped = api.mapLiveCitiesToAreas(row, areas);
  for (const name of areas.map(a=>a.name).filter(n=>n!=='شیراز')) {
    for (const key of ['orders','customers','revenue']) assert.strictEqual(mapped[name][key],0,'sale leaked to '+name);
  }
  assert.strictEqual(mapped['شیراز'].revenue,700);
  assert.strictEqual(mapped['شیراز'].orders,7);
  assert.strictEqual(Object.keys(mapped).length,areas.length);
  assert.strictEqual(JSON.stringify({areas,row}),snapshot,'input totals/geometry mutated');
}
console.log('LIVE_AND_PATCHED_NO_FUZZY_SALES_TRANSFER_OK');
const ambiguous = [{name:'نجف آباد'},{name:'نجف‌آباد'}];
for (const areas of [ambiguous, [...ambiguous].reverse()]) {
  const mapped = fixed.mapLiveCitiesToAreas({cities:[{name:'نجف‌آباد',orders:1,revenue:100}]}, areas);
  for (const row of Object.values(mapped)) assert.strictEqual(row.revenue,0,'ambiguous area accepted');
}
const duplicateParts = fixed.mapLiveCitiesToAreas({cities:[{name:'دلیجان',orders:1,revenue:100}]},[{name:'دلیجان'},{name:'دلیجان'}]);
assert.strictEqual(duplicateParts['دلیجان'].revenue,100,'multipart shape duplicated sale');
console.log('PATCHED_AMBIGUOUS_NAMES_REJECTED_MULTIPART_PRESERVED_OK');
const geom = ctx.window.K20ProvinceGeometry;
const geometryBefore = JSON.stringify(geom);
assert.strictEqual(Object.keys(geom).length,31);
let polygonCount=0, logicalCount=0;
for (const province of Object.values(geom)) {
  polygonCount+=province.areas.length;
  const names=[...new Set(province.areas.map(a=>a.name))]; logicalCount+=names.length;
  for (const name of names) {
    const variant=name.replace(/ی/g,'ي').replace(/ک/g,'ك').slice(0,1)+'ـ'+name.replace(/ی/g,'ي').replace(/ک/g,'ك').slice(1);
    const mapped=fixed.mapLiveCitiesToAreas({cities:[{name:variant,orders:1,customers:1,revenue:123}]},province.areas);
    assert.strictEqual(mapped[name].revenue,123,'real area variant failed: '+name);
    assert.strictEqual(Object.values(mapped).reduce((sum,c)=>sum+c.revenue,0),123,'real geometry sale transferred/duplicated');
    assert.deepStrictEqual(Object.keys(mapped).sort(),names.slice().sort());
  }
}
assert.strictEqual(polygonCount,427); assert.strictEqual(JSON.stringify(geom),geometryBefore);
console.log('PATCHED_REAL_GEOMETRY_OK='+JSON.stringify({provinces:31,polygons:polygonCount,logicalAreas:logicalCount}));
const provinceA=fixed.mapLiveCitiesToAreas({cities:[{name:'شیراز',orders:1,revenue:100}]},[{name:'شیراز'}]);
const provinceB=fixed.mapLiveCitiesToAreas({cities:[{name:'شیراز',orders:2,revenue:200}]},[{name:'شیراز'}]);
assert.strictEqual(provinceA['شیراز'].revenue,100); assert.strictEqual(provinceB['شیراز'].revenue,200);
const v={};
vm.runInNewContext(patched.slice(patched.indexOf('function metricValue('),patched.indexOf('function normalizeRegionText('))+';this.tint=heat3DTintStrength;',v);
for (const metric of ['orders','customers','revenue']) {
  const mapped=fixed.mapLiveCitiesToAreas({cities:[{name:'شيـراز',orders:1,customers:1,revenue:100},{name:'آبژدان',orders:2,customers:2,revenue:200}]},[{name:'شیراز'},{name:'آبادان'}]);
  const scale=ctx.window.K20AdaptiveGeo.createScale({rows:Object.values(mapped),metric,totalOrders:3,totalCustomers:3,palette:['#111111','#222222','#333333'],zeroColor:'#94a3b8'});
  assert.strictEqual(scale.fill(mapped['آبادان'][metric]),'#94a3b8');
  assert.strictEqual(scale.indexFor(mapped['آبادان'][metric]),-1);
  assert.strictEqual(v.tint(mapped['آبادان'][metric],[mapped['شیراز'][metric]],scale),0);
  assert.notStrictEqual(scale.fill(mapped['شیراز'][metric]),'#94a3b8');
  assert(v.tint(mapped['شیراز'][metric],[mapped['شیراز'][metric]],scale)>0);
}
console.log('PATCHED_PROVINCE_ISOLATION_ZERO_COLOR_2D_3D_OK');
console.log('PATCHED_SOURCE_REGRESSION_PASS_NO_PRODUCTION_DEPLOYMENT');
