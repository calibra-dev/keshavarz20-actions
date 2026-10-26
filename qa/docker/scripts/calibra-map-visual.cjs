'use strict';
// Calibra 1.8.17 isolated WordPress UI visual QA. No production browser login.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const mode = process.env.QA_STORAGE_MODE || 'legacy';
const base = process.env.QA_URL || 'http://wordpress';
const output = '/qa/artifacts/' + mode + '-calibra-map';
fs.mkdirSync(output, { recursive: true });
const failures = [];
const diagnostics = { version: '1.8.17', mode, base, test: 'map-visual', pages: [], states: [], errors: [], limits: [] };
const slug = (x) => String(x).replace(/[^a-z0-9_-]/gi, '_');
function fail(s) { failures.push(s); console.error('CALIBRA_VISUAL_FAIL ' + s); }
async function inspect(page) {
  return page.evaluate(() => {
    const re = /map|iran|geo|province|city|cinema|3d|2d|نقشه|استان|شهر|سه.?بعد|دو.?بعد/i;
    const txt = (e) => ((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.title || '')).trim().slice(0,110);
    const vis = (e) => {
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
    };
    const maps = [];
    for (const e of document.querySelectorAll('svg,canvas,img,[id],[class]')) {
      const r = e.getBoundingClientRect();
      if (!vis(e) || r.width < 160 || r.height < 110) continue;
      const id = e.id || '', cls = String(e.className && (e.className.baseVal || e.className) || '');
      const src = e.getAttribute('src') || '';
      const tags = [id,cls,src].join(' ');
      const shapeCount = e.querySelectorAll('path,polygon,svg,canvas,img').length;
      if (!re.test(tags) && !(e.tagName.toLowerCase() === 'svg' && shapeCount >= 5)) continue;
      const nesting = e.querySelectorAll('path,polygon').length;
      const score = (re.test(id) ? 50 : 0) + (re.test(cls) ? 25 : 0) +
                    (e.tagName.toLowerCase() === 'svg' ? 30 : 0) + Math.min(20, nesting / 10) +
                    ((r.width > 450 && r.height > 250) ? 30 : 0) - ((r.height > 2500) ? 50 : 0);
      maps.push({ tag:e.tagName.toLowerCase(), id, cls:cls.slice(0,110), src:src.slice(0,140),
        width:Math.round(r.width),height:Math.round(r.height),x:Math.round(r.x),y:Math.round(r.y),
        shapes:nesting,score});
    }
    maps.sort((a,b)=>b.score-a.score);
    const controls = [];
    for (const e of document.querySelectorAll('button,a,[role="tab"],select,input[type=radio],[data-map-mode]')) {
      if (!vis(e)) continue;
      const label = txt(e); const id = e.id || '', cls = String(e.className || '').slice(0,100);
      if (!re.test(label + ' ' + id + ' ' + cls)) continue;
      controls.push({tag:e.tagName.toLowerCase(),label, id, cls,
        href:e.getAttribute('href'),value:e.value,html:e.outerHTML.slice(0,260)});
    }
    const resources = [...document.images].filter(e => {
      const r=e.getBoundingClientRect();return r.width>120&&r.height>80;
    }).map(e=>({src:(e.currentSrc||e.src).slice(0,180),loaded:e.complete&&e.naturalWidth>0,naturalWidth:e.naturalWidth}));
    const candidates = [...document.querySelectorAll('#adminmenu a')].map(a => ({text:txt(a),href:a.getAttribute('href')}))
      .filter(x=>re.test(x.text+' '+x.href)).slice(0,35);
    return { url:location.href,title:document.title,dir:document.documentElement.dir||getComputedStyle(document.body).direction,
      lang:document.documentElement.lang,windowWidth:innerWidth,bodyScroll:document.documentElement.scrollWidth,
      mapElements:maps.slice(0,50),controls:controls.slice(0,100),
      images:resources.slice(0,35),adminLinks:candidates,
      svgCount:document.querySelectorAll('svg').length,canvasCount:document.querySelectorAll('canvas').length,
      pathCount:document.querySelectorAll('svg path').length,
      screenText:(document.body.innerText||'').slice(0,1700)};
  });
}
async function pixelMetrics(page, a, b) {
  return page.evaluate(async ([aa,bb]) => {
    const load = async (b64) => {
      const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
      const can=document.createElement('canvas');can.width=img.width;can.height=img.height;
      const ctx=can.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0);
      return {width:img.width,height:img.height,pixels:ctx.getImageData(0,0,img.width,img.height).data};
    };
    const x=await load(aa), y=await load(bb);
    if(x.width !== y.width || x.height !== y.height) return {error:'IMAGE_SIZE_CHANGE',first:[x.width,x.height],second:[y.width,y.height]};
    let changed=0,sameNeighbor=0,total=x.width*x.height;
    const unique=new Set();
    for(let i=0;i<x.pixels.length;i+=4){
      if(x.pixels[i]!==y.pixels[i]||x.pixels[i+1]!==y.pixels[i+1]||x.pixels[i+2]!==y.pixels[i+2]||x.pixels[i+3]!==y.pixels[i+3]) changed++;
      if(i>0&&x.pixels[i]===x.pixels[i-4]&&x.pixels[i+1]===x.pixels[i-3]&&x.pixels[i+2]===x.pixels[i-2])sameNeighbor++;
      if((i/4)%17===0)unique.add(((x.pixels[i]>>3)<<10)|((x.pixels[i+1]>>3)<<5)|(x.pixels[i+2]>>3));
    }
    return {width:x.width,height:x.height,pixels:total,changedPixels:changed,changedPct:Math.round(changed*10000/total)/100,
      sampledColors:unique.size,flatNeighborPct:Math.round(sameNeighbor*10000/total)/100};
  }, [a.toString('base64'),b.toString('base64')]);
}
async function preview(page, png, tag) {
  if(mode !== 'legacy' || !/1366.*base/.test(tag))return;
  const thumb = await page.evaluate(async b64 => {
    const i = new Image();i.src='data:image/png;base64,'+b64;await i.decode();
    const c=document.createElement('canvas'); c.width=480;c.height=Math.max(100,Math.round(i.height*480/i.width));
    c.getContext('2d').drawImage(i,0,0,c.width,c.height);
    return c.toDataURL('image/jpeg',0.50).split(',')[1];
  },png.toString('base64'));
  console.log('CALIBRA_VISUAL_PREVIEW_B64_'+tag+'='+thumb);
}
async function capture(page,tag) {
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const info=await inspect(page);
  const name=slug(tag);
  const full=path.join(output,name+'-full.png');
  await page.screenshot({path:full,fullPage:true,animations:'disabled',caret:'hide',timeout:30000});
  const target = await page.evaluate(() => {
    const re=/map|iran|geo|province|cinema|نقشه/i;
    const nodes=[...document.querySelectorAll('svg,canvas,img,[id],[class]')].filter(e=>{
      const r=e.getBoundingClientRect();const css=getComputedStyle(e);
      const key=[e.id,String(e.className?.baseVal||e.className||''),e.getAttribute('src')||''].join(' ');
      return re.test(key)&&r.width>300&&r.height>150&&r.height<1800&&css.display!=='none'&&css.visibility!=='hidden';
    });
    nodes.sort((a,b)=> {
      const v=x=>{const r=x.getBoundingClientRect();return ((/map|iran/i).test(x.id)?40:0)+((/map|iran/i).test(String(x.className?.baseVal||x.className||''))?15:0)+((r.width>500&&r.height>300)?10:0) + ((x.tagName.toLowerCase()==='svg')?10:0)-Math.abs(r.width*r.height-520000)/50000;};
      return v(b)-v(a);
    });
    const el=nodes[0];if(!el)return null;
    document.querySelectorAll('[data-calibra-visual-target]').forEach(x=>x.removeAttribute('data-calibra-visual-target'));
    el.setAttribute('data-calibra-visual-target','yes');
    const r=el.getBoundingClientRect();
    return {tag:el.tagName,id:el.id,cls:String(el.className?.baseVal||el.className||'').slice(0,100),width:r.width,height:r.height};
  });
  let pixels=null;
  if (target) {
    const loc=page.locator('[data-calibra-visual-target="yes"]');
    try {
      const file=path.join(output,name+'-map.png');
      const a=await loc.screenshot({path:file,animations:'disabled',caret:'hide',timeout:20000});
      const b=await loc.screenshot({animations:'disabled',caret:'hide',timeout:20000});
      pixels=await pixelMetrics(page,a,b);
      await preview(page,a,tag);
      if(pixels.sampledColors<5)fail('MAP_POSSIBLY_BLANK '+tag+' colors='+pixels.sampledColors);
      if(pixels.changedPct>4)fail('MAP_UNSTABLE '+tag+' changed='+pixels.changedPct+'%');
    }catch(e){fail('MAP_CAPTURE_FAILED '+tag+' '+e.message.slice(0,160));}
  } else fail('NO_VISIBLE_MAP_TARGET '+tag);
  const row={tag,dom:info,mapTarget:target,pixelDiff:pixels};
  diagnostics.states.push(row);
  console.log('CALIBRA_VISUAL_STATE '+JSON.stringify({tag,url:info.url,dir:info.dir,svg:info.svgCount,paths:info.pathCount,
    maps:info.mapElements.slice(0,5),controls:info.controls.slice(0,20).map(x=>({label:x.label,tag:x.tag,id:x.id})),
    target,pixels,unloaded:info.images.filter(x=>!x.loaded).slice(0,5)}));
  return row;
}
(async () => {
  const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    const page=await browser.newPage({viewport:{width:1366,height:900},deviceScaleFactor:1,
      locale:'fa-IR',colorScheme:'light',reducedMotion:'reduce'});
    page.on('pageerror',e=>diagnostics.errors.push('JS '+e.message));
    page.on('response',r=>{
      if(r.status()>=400 && /k20-dashboard|\/wp-json\/k20-dashboard/i.test(r.url()))
        diagnostics.errors.push('HTTP '+r.status()+' '+r.url().slice(0,160));
    });
    await page.goto(base+'/wp-login.php',{waitUntil:'domcontentloaded',timeout:30000});
    await page.locator('#user_login').fill('qa-admin');
    await page.locator('#user_pass').fill('QaDisposableOnly123');
    await Promise.all([page.waitForURL(/wp-admin/, {timeout:30000}),page.locator('#wp-submit').click()]);
    const urlCandidates=[base+'/wp-admin/index.php'];
    const menus=await inspect(page);
    diagnostics.adminLinks=menus.adminLinks;
    for(const x of menus.adminLinks){
      if(x.href && /(?:page=|\/wp-admin\/)/.test(x.href) && /calibra|k20|dashboard|نقشه/i.test(x.text+' '+x.href)) {
        try { const u=new URL(x.href,base+'/wp-admin/').href;if(!urlCandidates.includes(u))urlCandidates.push(u); }catch{}
      }
    }
    // Only visit known WordPress-admin screens, never outside isolated site.
    let best=null,score=-1;
    for(const url of urlCandidates.slice(0,12)){
      try {
        await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
        await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
        const info=await inspect(page);
        const s=info.mapElements.length*4 + (info.pathCount>10?12:0) + (info.canvasCount>0?4:0);
        diagnostics.pages.push({url:info.url,score:s,maps:info.mapElements.slice(0,6),controls:info.controls.slice(0,15),text:info.screenText.slice(0,900)});
        if(s>score){score=s;best=info.url;}
      } catch(e){diagnostics.pages.push({url,error:e.message.slice(0,160)});}
    }
    console.log('CALIBRA_VISUAL_DISCOVERY '+JSON.stringify({best,score,adminLinks:menus.adminLinks,pages:diagnostics.pages}));
    if(!best||score<4){fail('MAP_UI_NOT_FOUND_IN_WORDPRESS_ADMIN');return;}
    await page.goto(best,{waitUntil:'domcontentloaded',timeout:30000});
    await capture(page,'1366-base');
    let variantSeen=0;
    for(const label of ['3d','2d']){
      const dom=await inspect(page);
      const ctrl=dom.controls.find(x=>new RegExp(label,'i').test(x.label+' '+x.id+' '+x.cls));
      if(!ctrl) { console.log('CALIBRA_VISUAL_NO_EXPLICIT_'+label.toUpperCase()+'_CONTROL');continue; }
      try{
        const clicked=await page.evaluate((html)=>{
          const es=[...document.querySelectorAll('button,a,[role="tab"],select,input[type=radio],[data-map-mode]')];
          const el=es.find(e=>e.outerHTML.slice(0,260)===html);
          if(!el)return false;
          if(el.tagName==='SELECT'){
            const opt=[...el.options].find(o=>new RegExp(html.includes('3d')?'3d':'2d','i').test(o.textContent+' '+o.value));
            if(!opt)return false;el.value=opt.value;el.dispatchEvent(new Event('change',{bubbles:true}));
          }else el.click();
          return true;
        },ctrl.html);
        if(!clicked){fail('CONTROL_NOT_ACTIONABLE_'+label);continue;}
        await capture(page,'1366-'+label);variantSeen++;
      }catch(e){fail('CONTROL_CLICK_'+label+' '+e.message.slice(0,150));}
    }
    if(!variantSeen) diagnostics.limits.push('2D/3D controls not discovered or are not explicit; visual mode switching NOT VERIFIED');
    for(const [w,h] of [[390,844],[768,1024],[1920,1080]]){
      await page.setViewportSize({width:w,height:h});
      await capture(page,w+'-base');
      const info=await inspect(page);
      if(info.bodyScroll>info.windowWidth+50)diagnostics.limits.push('HORIZONTAL_OVERFLOW_'+w+'_'+info.bodyScroll);
    }
    if(diagnostics.errors.length)fail('BROWSER_ERRORS count='+diagnostics.errors.length+' first='+diagnostics.errors[0]);
  } finally {
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({...diagnostics,failures},null,2));
    await browser.close();
  }
  if(failures.length)throw Error('CALIBRA_VISUAL_QA_FAILED '+failures.join(' | ').slice(0,450));
  console.log('CALIBRA_VISUAL_QA_SCREENSHOTS_PASS mode='+mode+' states='+diagnostics.states.length+' limits='+diagnostics.limits.join(','));
})().catch(e=>{console.error(e.stack||e.message);process.exitCode=1;});