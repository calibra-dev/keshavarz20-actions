(function(){
'use strict';

function boot(){
  var root=document.getElementById('k20CatalogV4');
  if(!root||root.dataset.booted==='1')return;
  root.dataset.booted='1';

  var $=function(sel,ctx){return (ctx||root).querySelector(sel);};
  var $$=function(sel,ctx){return Array.prototype.slice.call((ctx||root).querySelectorAll(sel));};

  var state={
    products:[],visible:[],selected:null,compare:[],category:'',search:'',stockOnly:false,
    sort:'default',maxPrice:0,priceCap:null,controller:null,requestSeq:0
  };

  var workspaceGrid=$('#k20WorkspaceProducts');
  var heroGrid=$('#k20HeroProducts');
  var resultCount=$('#k20ResultCount');
  var sortSelect=$('#k20Sort');
  var stockOnly=$('#k20StockOnly');
  var priceRange=$('#k20PriceRange');
  var priceLabel=$('#k20PriceLabel');
  var filterPanel=$('#k20Filters');
  var filterBackdrop=$('#k20FilterBackdrop');
  var compareBar=$('#k20CompareBar');
  var compareBarItems=$('#k20CompareBarItems');
  var compareGrid=$('#k20CompareGrid');
  var toast=$('#k20Toast');
  var loading=$('#k20Loading');
  var searchInputs=$$('[data-k20-search]');
  var detailMedia=$('#k20DetailMedia');
  var detailTitle=$('#k20DetailTitle');
  var detailPrice=$('#k20DetailPrice');
  var detailMeta=$('#k20DetailMeta');
  var detailLink=$('#k20DetailLink');

  function el(tag,className,text){
    var n=document.createElement(tag);
    if(className)n.className=className;
    if(text!==undefined)n.textContent=text;
    return n;
  }
  function clear(n){while(n&&n.firstChild)n.removeChild(n.firstChild);}
  function notify(message){
    if(!toast)return;
    toast.textContent=message;
    toast.classList.add('show');
    setTimeout(function(){toast.classList.remove('show');},1500);
  }
  function firstImage(p){
    return p&&p.images&&p.images.length?(p.images[0].src||p.images[0].thumbnail||''):'';
  }
  function priceValue(p){
    if(!p||!p.prices)return 0;
    var minor=Number(p.prices.currency_minor_unit||0);
    var raw=Number(p.prices.price||0);
    return isFinite(raw)?raw/Math.pow(10,minor):0;
  }
  function priceText(p){
    if(!p||!p.prices)return 'قیمت نامشخص';
    var value=priceValue(p);
    var symbol=p.prices.currency_symbol||'تومان';
    return value.toLocaleString('fa-IR')+' '+symbol;
  }
  function catText(p){
    return p&&p.categories&&p.categories.length?p.categories.map(function(x){return x.name;}).join('، '):'—';
  }
  function brandText(p){
    return p&&p.brands&&p.brands.length?p.brands.map(function(x){return x.name;}).join('، '):'—';
  }
  function imageNode(src,alt){
    if(!src)return el('div','fallback','بدون تصویر');
    var img=el('img');
    img.src=src;
    img.alt=alt||'تصویر محصول';
    img.loading='eager';
    img.decoding='async';
    img.addEventListener('error',function(){
      var p=img.parentNode;
      if(p)p.replaceChild(el('div','fallback','بدون تصویر'),img);
    },{once:true});
    return img;
  }
  function setLoading(on){
    if(loading)loading.hidden=!on;
    if(workspaceGrid)workspaceGrid.setAttribute('aria-busy',on?'true':'false');
  }
  function syncSearch(value,source){
    state.search=String(value||'').trim();
    searchInputs.forEach(function(i){if(i!==source&&i.value!==value)i.value=value;});
  }
  var searchTimer=null;
  function scheduleSearch(value,source){
    syncSearch(value,source);
    clearTimeout(searchTimer);
    searchTimer=setTimeout(fetchProducts,300);
  }
  function setCategory(id){
    state.category=String(id||'');
    $$('[data-category-id]').forEach(function(b){
      b.classList.toggle('active',String(b.getAttribute('data-category-id')||'')===state.category);
    });
  }
  function updatePriceRange(reset){
    var max=0;
    state.products.forEach(function(p){max=Math.max(max,priceValue(p));});
    state.maxPrice=max;
    var m=Math.max(1,Math.ceil(max));
    priceRange.max=String(m);
    if(reset||state.priceCap===null||state.priceCap>m)state.priceCap=m;
    priceRange.value=String(state.priceCap);
    priceLabel.textContent=max?('تا '+Number(state.priceCap).toLocaleString('fa-IR')+' تومان'):'همه قیمت ها';
  }
  function filteredProducts(){
    var arr=state.products.filter(function(p){
      if(state.stockOnly&&p.is_in_stock===false)return false;
      if(state.priceCap!==null&&priceValue(p)>Number(state.priceCap))return false;
      return true;
    });
    if(state.sort==='name')arr.sort(function(a,b){return String(a.name||'').localeCompare(String(b.name||''),'fa');});
    if(state.sort==='price-asc')arr.sort(function(a,b){return priceValue(a)-priceValue(b);});
    if(state.sort==='price-desc')arr.sort(function(a,b){return priceValue(b)-priceValue(a);});
    if(state.sort==='rating')arr.sort(function(a,b){return Number(b.average_rating||0)-Number(a.average_rating||0);});
    return arr;
  }

  async function fetchProducts(){
    var seq=++state.requestSeq;
    if(state.controller)state.controller.abort();
    state.controller=new AbortController();
    setLoading(true);
    var q=new URLSearchParams();
    q.set('per_page','24');
    if(state.category)q.set('category',state.category);
    if(state.search)q.set('search',state.search);
    try{
      var res=await fetch('/wp-json/wc/store/v1/products?'+q.toString(),{
        credentials:'same-origin',headers:{'Accept':'application/json'},signal:state.controller.signal
      });
      if(!res.ok)throw new Error('HTTP '+res.status);
      var data=await res.json();
      if(seq!==state.requestSeq)return;
      state.products=Array.isArray(data)?data:[];
      if(!state.selected&&state.products.length)state.selected=state.products[0];
      else if(state.selected){
        var same=state.products.find(function(p){return Number(p.id)===Number(state.selected.id);});
        state.selected=same||state.products[0]||null;
      }
      updatePriceRange(true);
      renderAll();
    }catch(err){
      if(err&&err.name==='AbortError')return;
      state.products=[];
      state.visible=[];
      renderAll('دریافت محصولات با خطا روبه رو شد.');
      notify('خطا در دریافت محصولات');
    }finally{
      if(seq===state.requestSeq)setLoading(false);
    }
  }

  function makeProductCard(p,compact){
    var card=el('article',compact?'main-product-card':'product-card');
    card.dataset.productId=String(p.id||'');
    if(compact){
      var h=el('span','heart','♡');card.appendChild(h);
      card.appendChild(imageNode(firstImage(p),p.name));
      card.appendChild(el('b','',p.name||'محصول'));
      card.appendChild(el('small','',priceText(p)));
      card.addEventListener('click',function(){selectProduct(p,true);});
      return card;
    }
    var media=el('div','product-media');
    media.appendChild(imageNode(firstImage(p),p.name));
    media.appendChild(el('span','stock-badge'+(p.is_in_stock===false?' out':''),p.is_in_stock===false?'ناموجود':'موجود'));
    card.appendChild(media);
    card.appendChild(el('h3','',p.name||'محصول'));
    var meta=el('div','product-meta');
    meta.appendChild(el('strong','price',priceText(p)));
    meta.appendChild(el('span','cat-label',catText(p)));
    card.appendChild(meta);
    var actions=el('div','card-actions');
    var view=el('button','view','مشاهده محصول');view.type='button';
    view.addEventListener('click',function(e){e.stopPropagation();selectProduct(p,true);});
    var cmp=el('button','','⚖');cmp.type='button';cmp.setAttribute('aria-label','افزودن به مقایسه');
    if(state.compare.some(function(x){return Number(x.id)===Number(p.id);})){cmp.classList.add('active');}
    cmp.addEventListener('click',function(e){e.stopPropagation();toggleCompare(p);});
    var link=el('a','','↗');link.href=p.permalink||'/shop/';link.setAttribute('aria-label','باز کردن صفحه محصول');
    actions.appendChild(view);actions.appendChild(cmp);actions.appendChild(link);
    card.appendChild(actions);
    card.addEventListener('click',function(){selectProduct(p,false);});
    return card;
  }

  function renderHeroProducts(){
    clear(heroGrid);
    state.visible.slice(0,4).forEach(function(p){heroGrid.appendChild(makeProductCard(p,true));});
    if(!state.visible.length)heroGrid.appendChild(el('div','empty','محصولی پیدا نشد.'));
  }

  function renderWorkspace(errorMessage){
    clear(workspaceGrid);
    state.visible=filteredProducts();
    resultCount.textContent=state.visible.length.toLocaleString('fa-IR')+' محصول';
    if(errorMessage){workspaceGrid.appendChild(el('div','empty',errorMessage));return;}
    if(!state.visible.length){workspaceGrid.appendChild(el('div','empty','محصولی با این فیلتر پیدا نشد.'));return;}
    state.visible.forEach(function(p){workspaceGrid.appendChild(makeProductCard(p,false));});
  }

  function renderHeroDetail(){
    var p=state.selected;
    var media=$('#k20HeroDetailMedia');clear(media);
    if(!p){media.appendChild(el('div','fallback','محصول'));$('#k20HeroDetailTitle').textContent='محصولی انتخاب نشده';return;}
    media.appendChild(imageNode(firstImage(p),p.name));
    $('#k20HeroDetailTitle').textContent=p.name||'محصول';
    $('#k20HeroDetailPrice').textContent=priceText(p);
    $('#k20HeroDetailRating').textContent='★ '+(p.average_rating||'—')+'  '+(p.is_in_stock===false?'ناموجود':'موجود');
    $('#k20HeroDetailBuy').href=p.permalink||'/shop/';
  }

  function renderHeroSpec(){
    var p=state.selected;
    var rows=$('#k20HeroSpecRows');clear(rows);
    var values=p?[
      ['نام محصول',p.name||'—'],['دسته بندی',catText(p)],['برند',brandText(p)],
      ['قیمت',priceText(p)],['موجودی',p.is_in_stock===false?'ناموجود':'موجود'],['امتیاز',p.average_rating||'—']
    ]:[['نام محصول','—'],['دسته بندی','—'],['برند','—'],['قیمت','—'],['موجودی','—'],['امتیاز','—']];
    values.forEach(function(row){
      var d=el('div','spec-row');d.appendChild(el('span','',row[0]));d.appendChild(el('b','',row[1]));rows.appendChild(d);
    });
    var rel=$('#k20HeroRelated');clear(rel);
    state.visible.filter(function(x){return !p||Number(x.id)!==Number(p.id);}).slice(0,3).forEach(function(x){
      rel.appendChild(imageNode(firstImage(x),x.name));
    });
  }

  function renderHeroCompare(){
    var thumbs=$('#k20HeroCompareThumbs');clear(thumbs);
    var list=state.compare.length?state.compare:state.visible.slice(0,3);
    list.slice(0,3).forEach(function(p){
      var box=el('div','mini-product');box.appendChild(imageNode(firstImage(p),p.name));thumbs.appendChild(box);
    });
    $('#k20HeroCompareCount').textContent=state.compare.length?'مقایسه ('+state.compare.length.toLocaleString('fa-IR')+' محصول)':'افزودن محصول +';
  }

  function renderDetail(){
    var p=state.selected;clear(detailMedia);clear(detailMeta);
    if(!p){
      detailMedia.appendChild(el('div','fallback','محصول'));
      detailTitle.textContent='یک محصول را انتخاب کنید';detailPrice.textContent='—';detailLink.href='/shop/';return;
    }
    detailMedia.appendChild(imageNode(firstImage(p),p.name));
    detailTitle.textContent=p.name||'محصول';detailPrice.textContent=priceText(p);detailLink.href=p.permalink||'/shop/';
    [['دسته بندی',catText(p)],['برند',brandText(p)],['وضعیت',p.is_in_stock===false?'ناموجود':'موجود'],['امتیاز',p.average_rating||'—']].forEach(function(row){
      var li=el('li');li.appendChild(el('span','',row[0]));li.appendChild(el('b','',row[1]));detailMeta.appendChild(li);
    });
  }

  function selectProduct(p,scroll){
    state.selected=p;renderHeroDetail();renderHeroSpec();renderDetail();
    if(scroll){var d=$('#k20WorkspaceDetail');if(d)d.scrollIntoView({behavior:'smooth',block:'center'});}
  }

  function toggleCompare(p){
    var idx=state.compare.findIndex(function(x){return Number(x.id)===Number(p.id);});
    if(idx>-1){state.compare.splice(idx,1);notify('از مقایسه حذف شد');}
    else{
      if(state.compare.length>=3){notify('حداکثر ۳ محصول قابل مقایسه است');return;}
      state.compare.push(p);notify('به مقایسه اضافه شد');
    }
    renderHeroCompare();renderCompare();renderWorkspace();renderCompareBar();
  }

  function renderCompareBar(){
    clear(compareBarItems);
    state.compare.forEach(function(p){compareBarItems.appendChild(el('span','compare-chip',p.name||'محصول'));});
    compareBar.classList.toggle('show',state.compare.length>0);
  }

  function renderCompare(){
    clear(compareGrid);
    if(!state.compare.length){
      var e=el('div','empty','برای مقایسه، از کارت محصولات روی علامت ⚖ بزنید.');e.style.gridColumn='1/-1';compareGrid.appendChild(e);return;
    }
    [['محصول',function(p){return p.name||'—';}],['قیمت',priceText],['موجودی',function(p){return p.is_in_stock===false?'ناموجود':'موجود';}],['دسته بندی',catText],['برند',brandText]].forEach(function(row,rowIndex){
      compareGrid.appendChild(el('div','compare-cell label',row[0]));
      for(var i=0;i<3;i++){
        var cell=el('div','compare-cell');var p=state.compare[i];
        if(p){
          if(rowIndex===0){var src=firstImage(p);if(src)cell.appendChild(imageNode(src,p.name));}
          cell.appendChild(el('span','',row[1](p)));
        }else cell.appendChild(el('span','','—'));
        compareGrid.appendChild(cell);
      }
    });
  }

  function renderAll(errorMessage){
    state.visible=filteredProducts();
    renderWorkspace(errorMessage);renderHeroProducts();renderHeroDetail();renderHeroSpec();renderHeroCompare();renderDetail();renderCompare();renderCompareBar();
  }

  function resetAll(){
    state.search='';state.stockOnly=false;state.sort='default';state.priceCap=null;
    searchInputs.forEach(function(i){i.value='';});stockOnly.checked=false;sortSelect.value='default';setCategory('');fetchProducts();
  }

  function openFilters(){filterPanel.classList.add('open');filterBackdrop.classList.add('open');}
  function closeFilters(){filterPanel.classList.remove('open');filterBackdrop.classList.remove('open');}

  searchInputs.forEach(function(i){i.addEventListener('input',function(){scheduleSearch(this.value,this);});});
  $$('[data-category-id]').forEach(function(b){
    b.addEventListener('click',function(){
      setCategory(this.getAttribute('data-category-id')||'');fetchProducts();
      if(this.hasAttribute('data-scroll-products'))$('#k20Workspace').scrollIntoView({behavior:'smooth',block:'start'});
    });
  });
  $$('[data-reset]').forEach(function(b){b.addEventListener('click',resetAll);});
  sortSelect.addEventListener('change',function(){state.sort=this.value;renderAll();});
  stockOnly.addEventListener('change',function(){state.stockOnly=this.checked;renderAll();});
  priceRange.addEventListener('input',function(){state.priceCap=Number(this.value||0);priceLabel.textContent='تا '+state.priceCap.toLocaleString('fa-IR')+' تومان';renderAll();});
  $$('[data-open-filters]').forEach(function(b){b.addEventListener('click',openFilters);});
  $('#k20FilterClose').addEventListener('click',closeFilters);filterBackdrop.addEventListener('click',closeFilters);

  $('#k20HeroCompareAdd').addEventListener('click',function(){if(state.selected)toggleCompare(state.selected);});
  $('#k20HeroShowProducts').addEventListener('click',function(){$('#k20Workspace').scrollIntoView({behavior:'smooth',block:'start'});});
  $('#k20HeroShowAll').addEventListener('click',function(){setCategory('');fetchProducts();$('#k20Workspace').scrollIntoView({behavior:'smooth',block:'start'});});
  $('#k20CompareOpen').addEventListener('click',function(){$('#k20CompareSection').scrollIntoView({behavior:'smooth',block:'start'});});
  $('#k20CompareClear').addEventListener('click',function(){state.compare=[];renderAll();});

  $$('.strip-item[data-target]').forEach(function(b){
    b.addEventListener('click',function(){
      $$('.strip-item').forEach(function(x){x.classList.remove('active');});this.classList.add('active');
      var target=this.getAttribute('data-target');
      if(target==='home')root.scrollTo({top:0,behavior:'smooth'});
      if(target==='categories')$('#k20CategorySection').scrollIntoView({behavior:'smooth',block:'start'});
      if(target==='filters'){if(innerWidth<=980)openFilters();else $('#k20Filters').scrollIntoView({behavior:'smooth',block:'center'});}
      if(target==='product')$('#k20WorkspaceDetail').scrollIntoView({behavior:'smooth',block:'center'});
      if(target==='spec')$('#k20WorkspaceDetail').scrollIntoView({behavior:'smooth',block:'center'});
      if(target==='related')$('#k20Workspace').scrollIntoView({behavior:'smooth',block:'start'});
      if(target==='compare')$('#k20CompareSection').scrollIntoView({behavior:'smooth',block:'start'});
    });
  });

  $$('.category-mini').forEach(function(b){
    b.addEventListener('click',function(){setCategory(this.getAttribute('data-category-id')||'');fetchProducts();});
  });

  $('#k20MainSearch').addEventListener('input',function(){scheduleSearch(this.value,this);});
  $('#k20MainMenu').addEventListener('click',function(){$('#k20Workspace').scrollIntoView({behavior:'smooth',block:'start'});});

  fetchProducts();
  window.__K20CatalogV4={
    ready:true,
    getState:function(){return {category:state.category,search:state.search,products:state.products.length,visible:state.visible.length,compare:state.compare.length,selected:state.selected?state.selected.id:null};},
    fetchProducts:fetchProducts
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();
})();