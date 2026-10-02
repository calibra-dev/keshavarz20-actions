(function(){
'use strict';
var root=document.getElementById('k20CatalogV2');
if(!root)return;
var source=document.getElementById('k20ProductSource');
var topSearch=document.getElementById('k20TopSearch');
var sideSearch=document.getElementById('k20SideSearch');
var miniSearch=document.getElementById('k20MiniSearch');
var stockOnly=document.getElementById('k20StockOnly');
var priceRange=document.getElementById('k20PriceRange');
var priceLabel=document.getElementById('k20PriceLabel');
var sortSelect=document.getElementById('k20SortSelect');
var noResults=document.getElementById('k20NoResults');
var filterPanel=document.getElementById('k20FilterPanel');
var filterBackdrop=document.getElementById('k20FilterBackdrop');
var toast=document.getElementById('k20Toast');
var compare=[];
var activeKeyword='';
var products=[];
var maxPrice=0;
var initialOrder=[];
var initialMarkup=source?source.innerHTML:'';
var categoryRequest=0;

function txt(node){return node?String(node.textContent||'').trim():'';}
function normalize(value){
  return String(value||'')
    .replaceAll('ي','ی')
    .replaceAll('ك','ک')
    .replaceAll(String.fromCharCode(8204),' ')
    .split(' ').filter(Boolean).join(' ')
    .trim().toLowerCase();
}
function toLatinDigits(value){
  var fa='۰۱۲۳۴۵۶۷۸۹';
  var out='';
  String(value||'').split('').forEach(function(ch){
    var idx=fa.indexOf(ch);
    if(idx>=0){out+=String(idx);}
    else if(ch>='0'&&ch<='9'){out+=ch;}
  });
  return out;
}
function getPrice(li){
  var nodes=li.querySelectorAll('.price .amount,.price bdi');
  var raw=nodes.length?txt(nodes[nodes.length-1]):txt(li.querySelector('.price'));
  var digits=toLatinDigits(raw);
  var n=parseInt(digits,10);
  return isNaN(n)?0:n;
}
function getTitle(li){return txt(li.querySelector('.woocommerce-loop-product__title'))||txt(li.querySelector('h2'))||txt(li);}
function getLink(li){var a=li.querySelector('a.woocommerce-LoopProduct-link,a[href]');return a?a.href:'/shop/';}
function getImage(li){var im=li.querySelector('img');return im?(im.currentSrc||im.src):'';}
function getPriceText(li){return txt(li.querySelector('.price'))||'قیمت را در صفحه محصول ببینید';}
function isOut(li){return li.classList.contains('outofstock')||normalize(txt(li)).indexOf('ناموجود')>-1;}
function clear(node){while(node&&node.firstChild)node.removeChild(node.firstChild);}
function make(tag,className,textValue){
  var node=document.createElement(tag);
  if(className)node.className=className;
  if(textValue!==undefined)node.textContent=textValue;
  return node;
}
function notify(message){
  if(!toast)return;
  toast.textContent=message;
  toast.classList.add('show');
  setTimeout(function(){toast.classList.remove('show');},1600);
}
function apiPrice(product){
  if(!product||!product.prices)return 'قیمت را در صفحه محصول ببینید';
  var unit=Number(product.prices.currency_minor_unit||0);
  var value=Number(product.prices.price||0)/Math.pow(10,unit);
  if(!isFinite(value))return 'قیمت را در صفحه محصول ببینید';
  return value.toLocaleString('fa-IR')+' '+(product.prices.currency_symbol||'تومان');
}
function buildApiCard(product){
  var li=make('li','product');
  li.dataset.productId=String(product.id||'');
  if(product.is_in_stock===false)li.classList.add('outofstock');
  var link=make('a','woocommerce-LoopProduct-link woocommerce-loop-product__link');
  link.href=product.permalink||'/shop/';
  var imageUrl=product.images&&product.images[0]?(product.images[0].src||product.images[0].thumbnail):'';
  if(imageUrl){
    var image=make('img');
    image.src=imageUrl;
    image.alt=(product.images[0].alt||product.name||'محصول کشاورزی');
    image.loading='eager';
    image.decoding='async';
    image.addEventListener('error',function(){
      image.style.display='none';
      var fallback=make('div','k20-product-image-fallback','بدون تصویر');
      link.insertBefore(fallback,link.firstChild);
    },{once:true});
    link.appendChild(image);
  }else{
    link.appendChild(make('div','k20-product-image-fallback','بدون تصویر'));
  }
  link.appendChild(make('h2','woocommerce-loop-product__title',product.name||'محصول'));
  var price=make('span','price');
  price.textContent=apiPrice(product);
  link.appendChild(price);
  li.appendChild(link);
  return li;
}
function renderApiProducts(items){
  clear(source);
  var ul=make('ul','products columns-4');
  (items||[]).forEach(function(product){ul.appendChild(buildApiCard(product));});
  source.appendChild(ul);
  refreshProducts();
}
async function loadCategory(categoryId,button){
  var requestId=++categoryRequest;
  document.querySelectorAll('#k20CatalogV2 .k20-category-strip button').forEach(function(item){item.classList.remove('active');});
  if(button)button.classList.add('active');
  if(!categoryId){
    source.innerHTML=initialMarkup;
    refreshProducts();
    return;
  }
  source.setAttribute('aria-busy','true');
  noResults.hidden=true;
  try{
    var url='/wp-json/wc/store/v1/products?per_page=16&category='+encodeURIComponent(categoryId);
    var response=await fetch(url,{credentials:'same-origin',headers:{'Accept':'application/json'}});
    if(!response.ok)throw new Error('HTTP '+response.status);
    var data=await response.json();
    if(requestId!==categoryRequest)return;
    renderApiProducts(Array.isArray(data)?data:[]);
    noResults.hidden=Array.isArray(data)&&data.length>0;
    if(!data.length){noResults.hidden=false;noResults.textContent='در این دسته محصولی برای نمایش پیدا نشد.';}
  }catch(error){
    if(requestId!==categoryRequest)return;
    source.innerHTML=initialMarkup;
    refreshProducts();
    notify('دریافت محصولات این دسته با خطا روبه رو شد؛ محصولات اصلی نمایش داده شدند.');
  }finally{
    if(requestId===categoryRequest)source.removeAttribute('aria-busy');
  }
}
function refreshProducts(){
  products=Array.prototype.slice.call(source.querySelectorAll('ul.products li.product'));
  initialOrder=products.slice();
  maxPrice=0;
  products.forEach(function(li,index){
    li.dataset.k20Index=String(index);
    var price=getPrice(li);
    if(price>maxPrice)maxPrice=price;
    if(!li.querySelector('.k20-card-tools')){
      var tools=make('div','k20-card-tools');
      var fav=make('button','','♡');
      fav.type='button';
      fav.setAttribute('aria-label','علاقه مندی');
      var cmp=make('button','','⚖');
      cmp.type='button';
      cmp.setAttribute('aria-label','افزودن به مقایسه');
      tools.appendChild(fav);
      tools.appendChild(cmp);
      li.appendChild(tools);
      fav.addEventListener('click',function(event){
        event.preventDefault();event.stopPropagation();
        fav.classList.toggle('active');
        fav.textContent=fav.classList.contains('active')?'♥':'♡';
        notify('علاقه مندی به روز شد');
      });
      cmp.addEventListener('click',function(event){
        event.preventDefault();event.stopPropagation();
        toggleCompare(li,cmp);
      });
    }
    li.addEventListener('mouseenter',function(){updateDetail(li);});
    li.addEventListener('click',function(event){
      if(event.target.closest('.k20-card-tools'))return;
      updateDetail(li);
    });
  });
  priceRange.max=String(maxPrice||100);
  priceRange.value=String(maxPrice||100);
  priceLabel.textContent=maxPrice?('تا '+maxPrice.toLocaleString('fa-IR')+' تومان'):'همه قیمت ها';
  if(products.length)updateDetail(products[0]);
  applyFilters();
}
function applyFilters(){
  var q=normalize(sideSearch.value||topSearch.value||miniSearch.value||'');
  var cat=normalize(activeKeyword);
  var only=stockOnly.checked;
  var max=Number(priceRange.value||maxPrice||0);
  var visible=0;
  products.forEach(function(li){
    var hay=normalize(getTitle(li)+' '+txt(li));
    var passSearch=!q||hay.indexOf(q)>-1;
    var passCat=!cat||hay.indexOf(cat)>-1;
    var passStock=!only||!isOut(li);
    var price=getPrice(li);
    var passPrice=!maxPrice||price===0||price<=max;
    var ok=passSearch&&passCat&&passStock&&passPrice;
    if(ok){li.style.removeProperty('display');}else{li.style.setProperty('display','none','important');}
    if(ok)visible++;
  });
  noResults.hidden=visible!==0;
}
function sortProducts(){
  var ul=source.querySelector('ul.products');
  if(!ul)return;
  var arr=products.slice();
  var mode=sortSelect.value;
  if(mode==='name')arr.sort(function(a,b){return getTitle(a).localeCompare(getTitle(b),'fa');});
  if(mode==='price-asc')arr.sort(function(a,b){return getPrice(a)-getPrice(b);});
  if(mode==='price-desc')arr.sort(function(a,b){return getPrice(b)-getPrice(a);});
  if(mode==='default')arr=initialOrder.slice();
  arr.forEach(function(li){ul.appendChild(li);});
  products=arr;
  applyFilters();
}
function syncSearch(value){
  topSearch.value=value;
  sideSearch.value=value;
  miniSearch.value=value;
  applyFilters();
}
function updateDetail(li){
  var title=getTitle(li);
  var price=getPriceText(li);
  var link=getLink(li);
  var image=getImage(li);
  var stock=isOut(li)?'ناموجود':'موجود';
  document.getElementById('k20DetailTitle').textContent=title;
  document.getElementById('k20DetailPrice').textContent=price;
  var media=document.getElementById('k20DetailMedia');
  clear(media);
  if(image){
    var picture=make('img');
    picture.src=image;
    picture.alt=title;
    picture.decoding='async';
    media.appendChild(picture);
  }else{
    media.appendChild(make('div','k20-detail-placeholder','بدون تصویر'));
  }
  document.getElementById('k20DetailLink').href=link;
  document.getElementById('k20DetailActions').textContent=stock==='موجود'?'● موجود در فروشگاه':'● وضعیت موجودی را بررسی کنید';
  var rows=document.getElementById('k20SpecRows');
  clear(rows);
  [
    ['نام محصول',title],
    ['وضعیت',stock],
    ['قیمت',price],
    ['دسته بندی','اطلاعات صفحه محصول'],
    ['اطلاعات کامل','مشاهده صفحه محصول']
  ].forEach(function(row){
    var item=make('div');
    item.appendChild(make('span','',row[0]));
    item.appendChild(make('b','',row[1]));
    rows.appendChild(item);
  });
}
function toggleCompare(li,button){
  var idx=compare.indexOf(li);
  if(idx>-1){
    compare.splice(idx,1);
    button.classList.remove('active');
    notify('از مقایسه حذف شد');
  }else{
    if(compare.length>=2){notify('برای این نما حداکثر دو محصول انتخاب کنید');return;}
    compare.push(li);
    button.classList.add('active');
    notify('به مقایسه اضافه شد');
  }
  renderCompare();
}
function renderCompare(){
  var box=document.getElementById('k20CompareMini');
  clear(box);
  if(!compare.length){
    box.appendChild(make('p','','دو محصول را برای مقایسه انتخاب کنید.'));
    return;
  }
  compare.forEach(function(li){
    var row=make('div','k20-compare-row');
    var src=getImage(li);
    if(src){
      var image=make('img');
      image.src=src;
      image.alt='';
      image.decoding='async';
      row.appendChild(image);
    }else{
      row.appendChild(make('span'));
    }
    row.appendChild(make('b','',getTitle(li)));
    box.appendChild(row);
  });
  if(compare.length===2){
    var checks=make('div','k20-compare-checks');
    ['✓ قیمت','✓ موجودی','✓ مشخصات','✓ کاربرد'].forEach(function(label){checks.appendChild(make('span','',label));});
    box.appendChild(checks);
  }
}
function setCategory(keyword,button){
  activeKeyword=keyword||'';
  document.querySelectorAll('#k20CatalogV2 .k20-category-strip button').forEach(function(item){item.classList.remove('active');});
  if(button)button.classList.add('active');
  applyFilters();
}
[topSearch,sideSearch,miniSearch].forEach(function(input){
  input.addEventListener('input',function(){syncSearch(this.value);});
});
stockOnly.addEventListener('change',applyFilters);
priceRange.addEventListener('input',function(){
  var value=Number(this.value||0);
  priceLabel.textContent=maxPrice?('تا '+value.toLocaleString('fa-IR')+' تومان'):'همه قیمت ها';
  applyFilters();
});
sortSelect.addEventListener('change',sortProducts);
document.querySelectorAll('#k20CatalogV2 input[name=k20cat]').forEach(function(input){
  input.addEventListener('change',function(){setCategory(this.value,null);});
});
document.querySelectorAll('#k20CatalogV2 .k20-category-strip button').forEach(function(button){
  var image=button.querySelector('img');
  if(image){
    image.addEventListener('error',function(){
      var holder=image.parentNode;
      if(holder){clear(holder);holder.appendChild(make('span','','◫'));}
    },{once:true});
  }
  button.addEventListener('click',function(){
    activeKeyword='';
    syncSearch('');
    loadCategory(this.getAttribute('data-category')||'',this);
  });
});
document.getElementById('k20ClearFilters').addEventListener('click',function(){
  activeKeyword='';
  syncSearch('');
  stockOnly.checked=false;
  sortSelect.value='default';
  priceRange.value=String(maxPrice||100);
  priceLabel.textContent=maxPrice?('تا '+maxPrice.toLocaleString('fa-IR')+' تومان'):'همه قیمت ها';
  document.querySelectorAll('#k20CatalogV2 input[name=k20cat]').forEach(function(input){input.checked=input.value==='';});
  document.querySelectorAll('#k20CatalogV2 .k20-category-strip button').forEach(function(button){button.classList.remove('active');});
  source.innerHTML=initialMarkup;
  refreshProducts();
  sortProducts();
});
document.getElementById('k20ResetView').addEventListener('click',function(){document.getElementById('k20ClearFilters').click();});
document.getElementById('k20ShowProducts').addEventListener('click',function(){source.scrollIntoView({behavior:'smooth',block:'center'});});
function openFilter(){filterPanel.classList.add('open');filterBackdrop.classList.add('open');}
function closeFilter(){filterPanel.classList.remove('open');filterBackdrop.classList.remove('open');}
document.getElementById('k20MobileFilter').addEventListener('click',openFilter);
filterBackdrop.addEventListener('click',closeFilter);
document.querySelectorAll('#k20CatalogV2 [data-focus]').forEach(function(button){
  button.addEventListener('click',function(){
    var target=this.getAttribute('data-focus');
    if(target==='search'){topSearch.focus();}
    else if(target==='compare'){document.getElementById('k20ComparePanel').scrollIntoView({behavior:'smooth',block:'center'});}
    else if(target==='specs'||target==='technical'){document.getElementById('k20SpecPanel').scrollIntoView({behavior:'smooth',block:'center'});}
  });
});
document.querySelectorAll('#k20CatalogV2 [data-nav]').forEach(function(button){
  button.addEventListener('click',function(){
    document.querySelectorAll('#k20CatalogV2 [data-nav]').forEach(function(item){item.classList.remove('active');});
    this.classList.add('active');
    var nav=this.getAttribute('data-nav');
    if(nav==='filters'){
      if(window.innerWidth<=760)openFilter();
      else filterPanel.scrollIntoView({behavior:'smooth',block:'center'});
    }else if(nav==='compare'){
      document.getElementById('k20ComparePanel').scrollIntoView({behavior:'smooth',block:'center'});
    }else if(nav==='product'){
      document.getElementById('k20DetailPanel').scrollIntoView({behavior:'smooth',block:'center'});
    }else if(nav==='technical'){
      document.getElementById('k20SpecPanel').scrollIntoView({behavior:'smooth',block:'center'});
    }else{
      document.getElementById('k20AppShell').scrollIntoView({behavior:'smooth',block:'center'});
    }
  });
});
document.getElementById('k20HeaderFav').addEventListener('click',function(){notify('علاقه مندی ها از کارت محصولات قابل مدیریت است');});
function initWhenReady(){
  var count=source.querySelectorAll('ul.products li.product').length;
  if(!count)return false;
  refreshProducts();
  window.__K20CatalogV2={ready:true,productCount:products.length,applyFilters:applyFilters,loadCategory:loadCategory};
  root.dataset.runtimeReady='1';
  return true;
}
if(!initWhenReady()){
  var observer=new MutationObserver(function(){if(initWhenReady())observer.disconnect();});
  observer.observe(source,{childList:true,subtree:true});
  setTimeout(function(){
    if(!window.__K20CatalogV2)window.__K20CatalogV2={ready:false,productCount:0};
  },3500);
}
})();