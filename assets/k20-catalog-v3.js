(function(){
'use strict';

function boot(){
  var root=document.getElementById('k20CatalogV3');
  if(!root||root.dataset.booted==='1')return;
  root.dataset.booted='1';

  var $=function(sel,ctx){return (ctx||root).querySelector(sel);};
  var $$=function(sel,ctx){return Array.prototype.slice.call((ctx||root).querySelectorAll(sel));};
  var grid=$('#k20ProductsGrid');
  var loading=$('#k20Loading');
  var resultsCount=$('#k20ResultsCount');
  var sortSelect=$('#k20Sort');
  var stockOnly=$('#k20StockOnly');
  var priceRange=$('#k20PriceRange');
  var priceLabel=$('#k20PriceLabel');
  var filterPanel=$('#k20Filters');
  var filterBackdrop=$('#k20FilterBackdrop');
  var toast=$('#k20Toast');
  var compareBar=$('#k20CompareBar');
  var compareBarItems=$('#k20CompareBarItems');
  var compareSection=$('#k20CompareGrid');
  var detailSection=$('#k20Detail');
  var detailMedia=$('#k20DetailMedia');
  var detailTitle=$('#k20DetailTitle');
  var detailPrice=$('#k20DetailPrice');
  var detailStatus=$('#k20DetailStatus');
  var detailList=$('#k20DetailList');
  var detailLink=$('#k20DetailLink');
  var detailCompare=$('#k20DetailCompare');
  var searchInputs=$$('[data-k20-search]');

  var state={
    products:[],
    visible:[],
    category:'',
    search:'',
    sort:'default',
    stockOnly:false,
    priceCap:null,
    maxPrice:0,
    selected:null,
    compare:[],
    controller:null,
    requestSeq:0
  };

  function el(tag,className,text){
    var node=document.createElement(tag);
    if(className)node.className=className;
    if(text!==undefined)node.textContent=text;
    return node;
  }
  function clear(node){while(node&&node.firstChild)node.removeChild(node.firstChild);}
  function notify(message){
    if(!toast)return;
    toast.textContent=message;
    toast.classList.add('show');
    window.setTimeout(function(){toast.classList.remove('show');},1700);
  }
  function priceValue(product){
    if(!product||!product.prices)return 0;
    var minor=Number(product.prices.currency_minor_unit||0);
    var raw=Number(product.prices.price||0);
    if(!isFinite(raw))return 0;
    return raw/Math.pow(10,minor);
  }
  function priceText(product){
    if(!product||!product.prices)return 'قیمت نامشخص';
    var value=priceValue(product);
    var symbol=product.prices.currency_symbol||product.prices.currency_code||'تومان';
    return value.toLocaleString('fa-IR')+' '+symbol;
  }
  function firstImage(product){
    return product&&product.images&&product.images.length?(product.images[0].src||product.images[0].thumbnail||''):'';
  }
  function catText(product){
    return product&&product.categories&&product.categories.length?product.categories.map(function(c){return c.name;}).join('، '):'—';
  }
  function brandText(product){
    return product&&product.brands&&product.brands.length?product.brands.map(function(b){return b.name;}).join('، '):'—';
  }
  function imageNode(src,alt,className){
    if(!src)return el('div',className||'fallback','بدون تصویر');
    var img=el('img');
    img.src=src;
    img.alt=alt||'تصویر محصول';
    img.loading='eager';
    img.decoding='async';
    img.addEventListener('error',function(){
      var parent=img.parentNode;
      if(parent){
        var fallback=el('div','fallback','بدون تصویر');
        parent.replaceChild(fallback,img);
      }
    },{once:true});
    return img;
  }
  function setSearch(value,source){
    state.search=String(value||'').trim();
    searchInputs.forEach(function(input){
      if(input!==source&&input.value!==value)input.value=value;
    });
  }
  var searchTimer=null;
  function scheduleSearch(value,source){
    setSearch(value,source);
    window.clearTimeout(searchTimer);
    searchTimer=window.setTimeout(function(){fetchProducts();},320);
  }
  function setActiveCategory(id){
    state.category=String(id||'');
    $$('[data-category-id]').forEach(function(btn){
      btn.classList.toggle('active',String(btn.getAttribute('data-category-id')||'')===state.category);
    });
  }
  function updatePriceControl(reset){
    var max=0;
    state.products.forEach(function(p){max=Math.max(max,priceValue(p));});
    state.maxPrice=max;
    var maxAttr=Math.max(1,Math.ceil(max));
    priceRange.max=String(maxAttr);
    if(reset||state.priceCap===null||state.priceCap>maxAttr){
      state.priceCap=maxAttr;
      priceRange.value=String(maxAttr);
    }else{
      priceRange.value=String(state.priceCap);
    }
    priceLabel.textContent=max?('تا '+Number(state.priceCap).toLocaleString('fa-IR')+' تومان'):'همه قیمت ها';
  }
  function currentFiltered(){
    var arr=state.products.filter(function(p){
      if(state.stockOnly&&p.is_in_stock===false)return false;
      if(state.priceCap!==null&&priceValue(p)>Number(state.priceCap))return false;
      return true;
    });
    if(state.sort==='name'){
      arr.sort(function(a,b){return String(a.name||'').localeCompare(String(b.name||''),'fa');});
    }else if(state.sort==='price-asc'){
      arr.sort(function(a,b){return priceValue(a)-priceValue(b);});
    }else if(state.sort==='price-desc'){
      arr.sort(function(a,b){return priceValue(b)-priceValue(a);});
    }else if(state.sort==='rating'){
      arr.sort(function(a,b){return Number(b.average_rating||0)-Number(a.average_rating||0);});
    }
    return arr;
  }
  function setLoading(on){
    if(loading)loading.hidden=!on;
    if(grid)grid.setAttribute('aria-busy',on?'true':'false');
  }
  async function fetchProducts(){
    var seq=++state.requestSeq;
    if(state.controller)state.controller.abort();
    state.controller=new AbortController();
    setLoading(true);
    var params=new URLSearchParams();
    params.set('per_page','24');
    if(state.category)params.set('category',state.category);
    if(state.search)params.set('search',state.search);
    var url='/wp-json/wc/store/v1/products?'+params.toString();
    try{
      var response=await fetch(url,{
        credentials:'same-origin',
        headers:{'Accept':'application/json'},
        signal:state.controller.signal
      });
      if(!response.ok)throw new Error('HTTP '+response.status);
      var data=await response.json();
      if(seq!==state.requestSeq)return;
      state.products=Array.isArray(data)?data:[];
      updatePriceControl(true);
      if(!state.selected&&state.products.length)state.selected=state.products[0];
      else if(state.selected){
        var still=state.products.find(function(p){return Number(p.id)===Number(state.selected.id);});
        if(still)state.selected=still;
      }
      renderProducts();
      renderDetail();
    }catch(error){
      if(error&&error.name==='AbortError')return;
      if(seq!==state.requestSeq)return;
      state.products=[];
      renderProducts('دریافت محصولات با خطا روبه رو شد. دوباره تلاش کنید.');
      notify('خطا در دریافت محصولات');
    }finally{
      if(seq===state.requestSeq)setLoading(false);
    }
  }
  function renderProducts(errorMessage){
    clear(grid);
    state.visible=currentFiltered();
    resultsCount.textContent=state.visible.length.toLocaleString('fa-IR')+' محصول';
    if(errorMessage){
      grid.appendChild(el('div','k20-empty',errorMessage));
      return;
    }
    if(!state.visible.length){
      grid.appendChild(el('div','k20-empty','محصولی با این فیلتر پیدا نشد.'));
      return;
    }
    state.visible.forEach(function(product){
      var card=el('article','k20-product-card');
      card.dataset.productId=String(product.id);
      var media=el('div','k20-product-media');
      media.appendChild(imageNode(firstImage(product),product.name,'fallback'));
      var badge=el('span','k20-stock-badge'+(product.is_in_stock===false?' out':''),product.is_in_stock===false?'ناموجود':'موجود');
      media.appendChild(badge);
      card.appendChild(media);
      card.appendChild(el('h3','',product.name||'محصول'));
      var meta=el('div','k20-product-meta');
      meta.appendChild(el('strong','k20-price',priceText(product)));
      meta.appendChild(el('span','k20-cat-label',catText(product)));
      card.appendChild(meta);
      var actions=el('div','k20-card-actions');
      var view=el('button','view','مشاهده محصول');
      view.type='button';
      view.addEventListener('click',function(event){
        event.stopPropagation();
        selectProduct(product,true);
      });
      var compareBtn=el('button','', '⚖');
      compareBtn.type='button';
      compareBtn.setAttribute('aria-label','افزودن به مقایسه');
      if(state.compare.some(function(p){return Number(p.id)===Number(product.id);})){
        compareBtn.classList.add('active');
      }
      compareBtn.addEventListener('click',function(event){
        event.stopPropagation();
        toggleCompare(product);
      });
      var link=el('a','', '↗');
      link.href=product.permalink||'/shop/';
      link.setAttribute('aria-label','باز کردن صفحه محصول');
      actions.appendChild(view);
      actions.appendChild(compareBtn);
      actions.appendChild(link);
      card.appendChild(actions);
      card.addEventListener('click',function(){selectProduct(product,false);});
      grid.appendChild(card);
    });
  }
  function selectProduct(product,scroll){
    state.selected=product;
    renderDetail();
    if(scroll)detailSection.scrollIntoView({behavior:'smooth',block:'center'});
  }
  function renderDetail(){
    var p=state.selected;
    clear(detailMedia);
    clear(detailList);
    if(!p){
      detailMedia.appendChild(el('div','fallback','محصولی انتخاب نشده'));
      detailTitle.textContent='یک محصول را انتخاب کنید';
      detailPrice.textContent='—';
      detailStatus.textContent='—';
      detailLink.href='/shop/';
      return;
    }
    detailMedia.appendChild(imageNode(firstImage(p),p.name,'fallback'));
    detailTitle.textContent=p.name||'محصول';
    detailPrice.textContent=priceText(p);
    detailStatus.textContent=p.is_in_stock===false?'● ناموجود':'● موجود در فروشگاه';
    detailStatus.style.color=p.is_in_stock===false?'#b43c34':'#0a7a3d';
    var rows=[
      ['دسته بندی',catText(p)],
      ['برند',brandText(p)],
      ['امتیاز',p.average_rating?String(p.average_rating):'—'],
      ['وضعیت',p.stock_availability&&p.stock_availability.text?p.stock_availability.text:(p.is_in_stock===false?'ناموجود':'موجود')]
    ];
    rows.forEach(function(row){
      var li=el('li');
      li.appendChild(el('span','',row[0]));
      li.appendChild(el('b','',row[1]));
      detailList.appendChild(li);
    });
    detailLink.href=p.permalink||'/shop/';
    var inCompare=state.compare.some(function(x){return Number(x.id)===Number(p.id);});
    detailCompare.classList.toggle('active',inCompare);
    detailCompare.textContent=inCompare?'✓':'⚖';
  }
  function toggleCompare(product){
    var idx=state.compare.findIndex(function(p){return Number(p.id)===Number(product.id);});
    if(idx>-1){
      state.compare.splice(idx,1);
      notify('از مقایسه حذف شد');
    }else{
      if(state.compare.length>=3){
        notify('حداکثر ۳ محصول قابل مقایسه است');
        return;
      }
      state.compare.push(product);
      notify('به مقایسه اضافه شد');
    }
    renderProducts();
    renderDetail();
    renderCompare();
  }
  function renderCompare(){
    clear(compareBarItems);
    state.compare.forEach(function(p){
      compareBarItems.appendChild(el('span','k20-compare-chip',p.name||'محصول'));
    });
    compareBar.classList.toggle('show',state.compare.length>0);
    clear(compareSection);
    if(!state.compare.length){
      compareSection.appendChild(el('div','k20-compare-empty','برای مقایسه، روی آیکن ⚖ در کارت محصولات بزنید.'));
      return;
    }
    var rows=[
      ['محصول',function(p){return p.name||'—';}],
      ['قیمت',priceText],
      ['موجودی',function(p){return p.is_in_stock===false?'ناموجود':'موجود';}],
      ['دسته بندی',catText],
      ['برند',brandText]
    ];
    rows.forEach(function(row,rowIndex){
      compareSection.appendChild(el('div','k20-compare-cell label',row[0]));
      for(var i=0;i<3;i++){
        var cell=el('div','k20-compare-cell');
        var product=state.compare[i];
        if(product){
          if(rowIndex===0){
            var src=firstImage(product);
            if(src)cell.appendChild(imageNode(src,product.name,'fallback'));
          }
          cell.appendChild(el('span','',row[1](product)));
        }else{
          cell.appendChild(el('span','','—'));
        }
        compareSection.appendChild(cell);
      }
    });
  }
  function resetAll(){
    state.search='';
    state.sort='default';
    state.stockOnly=false;
    state.priceCap=null;
    searchInputs.forEach(function(i){i.value='';});
    sortSelect.value='default';
    stockOnly.checked=false;
    setActiveCategory('');
    fetchProducts();
  }
  function openFilters(){
    filterPanel.classList.add('open');
    filterBackdrop.classList.add('open');
  }
  function closeFilters(){
    filterPanel.classList.remove('open');
    filterBackdrop.classList.remove('open');
  }
  function scrollToId(id){
    var target=document.getElementById(id);
    if(target)target.scrollIntoView({behavior:'smooth',block:'start'});
  }
  function activateNav(button){
    $$('.k20-section-nav [data-scroll],.k20-section-nav [data-action]').forEach(function(item){item.classList.remove('active');});
    if(button)button.classList.add('active');
  }

  searchInputs.forEach(function(input){
    input.addEventListener('input',function(){scheduleSearch(this.value,this);});
  });
  sortSelect.addEventListener('change',function(){
    state.sort=this.value;
    renderProducts();
  });
  stockOnly.addEventListener('change',function(){
    state.stockOnly=this.checked;
    renderProducts();
  });
  priceRange.addEventListener('input',function(){
    state.priceCap=Number(this.value||0);
    priceLabel.textContent='تا '+state.priceCap.toLocaleString('fa-IR')+' تومان';
    renderProducts();
  });
  $$('[data-category-id]').forEach(function(button){
    button.addEventListener('click',function(){
      var id=this.getAttribute('data-category-id')||'';
      setActiveCategory(id);
      fetchProducts();
      if(this.classList.contains('k20-category-card'))scrollToId('k20-products');
    });
  });
  $$('[data-reset]').forEach(function(button){button.addEventListener('click',resetAll);});
  $$('[data-open-filters]').forEach(function(button){button.addEventListener('click',openFilters);});
  $('#k20FilterClose').addEventListener('click',closeFilters);
  filterBackdrop.addEventListener('click',closeFilters);
  detailCompare.addEventListener('click',function(){if(state.selected)toggleCompare(state.selected);});
  $('#k20CompareOpen').addEventListener('click',function(){scrollToId('k20-compare');});
  $('#k20CompareClear').addEventListener('click',function(){state.compare=[];renderProducts();renderDetail();renderCompare();});
  $$('[data-scroll]').forEach(function(button){
    button.addEventListener('click',function(){
      activateNav(this);
      scrollToId(this.getAttribute('data-scroll'));
    });
  });
  $$('[data-action]').forEach(function(button){
    button.addEventListener('click',function(){
      var action=this.getAttribute('data-action');
      activateNav(this);
      if(action==='filters'){
        if(window.innerWidth<=900)openFilters();
        else scrollToId('k20-filters-anchor');
      }else if(action==='detail'){
        if(!state.selected&&state.visible.length)state.selected=state.visible[0];
        renderDetail();
        scrollToId('k20-detail');
      }else if(action==='compare'){
        scrollToId('k20-compare');
      }else if(action==='search'){
        var first=searchInputs[0];
        if(first){first.focus();first.scrollIntoView({behavior:'smooth',block:'center'});}
      }
    });
  });
  $$('[data-hero-action]').forEach(function(button){
    button.addEventListener('click',function(){
      var action=this.getAttribute('data-hero-action');
      if(action==='search'){var hero=$('#k20HeroSearch');hero.focus();}
      if(action==='compare')scrollToId('k20-compare');
      if(action==='detail'){if(!state.selected&&state.visible.length)state.selected=state.visible[0];renderDetail();scrollToId('k20-detail');}
    });
  });

  var observer=new IntersectionObserver(function(entries){
    var visible=entries.filter(function(e){return e.isIntersecting;}).sort(function(a,b){return b.intersectionRatio-a.intersectionRatio;})[0];
    if(!visible)return;
    var id=visible.target.id;
    var btn=$('.k20-section-nav [data-scroll="'+id+'"]');
    if(btn)activateNav(btn);
  },{root:root,threshold:[.18,.35,.6],rootMargin:'-145px 0px -55% 0px'});
  ['k20-home','k20-categories','k20-products','k20-detail','k20-compare'].forEach(function(id){
    var node=document.getElementById(id);if(node)observer.observe(node);
  });

  $$('.k20-category-media img').forEach(function(img){
    img.addEventListener('error',function(){
      var box=img.parentNode;
      if(box){clear(box);box.appendChild(el('div','k20-category-fallback','🌱'));}
    },{once:true});
  });

  renderCompare();
  fetchProducts();
  window.__K20CatalogV3={
    ready:true,
    getState:function(){return {category:state.category,search:state.search,products:state.products.length,visible:state.visible.length,compare:state.compare.length};},
    fetchProducts:fetchProducts
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
else boot();
})();