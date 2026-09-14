param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
function Fail([string]$m){throw $m}
$base=$env:WP_BASE_URL;$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){Fail 'Required WordPress secrets are missing.'}
$base=$base.TrimEnd('/')
$request=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 100
$mode=if($request.mode){[string]$request.mode}else{'audit'}
if($mode -notin @('audit','apply_description')){Fail "Unsupported mode: $mode"}
$slug=if($request.category_slug){[string]$request.category_slug}else{'polyethylene-end-cap'}
$max=if($request.max_related){[int]$request.max_related}else{6}

$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Api([string]$method,[string]$path,$body=$null){
  $a=@{Uri=$base+'/'+$path.TrimStart('/');Method=$method;Headers=$headers;TimeoutSec=180}
  if($null-ne$body){$a.ContentType='application/json; charset=utf-8';$a.Body=($body|ConvertTo-Json -Depth 100 -Compress)}
  Invoke-RestMethod @a
}
function Products(){
  $all=@();for($page=1;$page-le100;$page++){
    $items=@(Api 'GET' "wp-json/wc/v3/products?per_page=100&page=$page&status=publish&orderby=id&order=asc")
    if($items.Count-eq0){break};$all+=$items;if($items.Count-lt100){break}
  };@($all)
}
function N([string]$t){
  if($null-eq$t){return ''};$s=$t
  $f=@('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹','٠','١','٢','٣','٤','٥','٦','٧','٨','٩');$to=@('0','1','2','3','4','5','6','7','8','9','0','1','2','3','4','5','6','7','8','9')
  for($i=0;$i-lt$f.Count;$i++){$s=$s.Replace($f[$i],$to[$i])}
  $s.Replace('‌',' ').Replace('٫','.').Replace('٬',',')
}
function NI([string]$t){
  $s=N $t;$s=$s.Replace('½',' 1/2').Replace('¼',' 1/4').Replace('¾',' 3/4')
  $s=[regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*1\s*/\s*2(?!\d)',{param($m);(([double]$m.Groups['w'].Value)+.5).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)})
  $s=[regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*1\s*/\s*4(?!\d)',{param($m);(([double]$m.Groups['w'].Value)+.25).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)})
  $s=[regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\s)\s*3\s*/\s*4(?!\d)',{param($m);(([double]$m.Groups['w'].Value)+.75).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)})
  $s=[regex]::Replace($s,'(?<!\d)3\s*/\s*4(?!\d)','0.75');$s=[regex]::Replace($s,'(?<!\d)1\s*/\s*2(?!\d)','0.5');$s=[regex]::Replace($s,'(?<!\d)1\s*/\s*4(?!\d)','0.25');$s
}
function PF([string]$t){$s=[string]$t;$a=@('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹');for($i=0;$i-lt10;$i++){$s=$s.Replace([string]$i,$a[$i])};$s}
$known=@(16,20,25,32,40,50,63,75,90,110,125,160,200)
$imap=@{'0.5'=20;'0.75'=25;'1'=32;'1.25'=40;'1.5'=50;'2'=63;'2.5'=75;'3'=90;'4'=110;'6'=160}
function Size([string]$name){
  $s=NI $name
  $pair=[regex]::Match($s,'(?<!\d)(?<a>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:x|X|×|\*)\s*(?<b>16|20|25|32|40|50|63|75|90|110|125|160|200)(?!\d)')
  if($pair.Success -and [int]$pair.Groups['a'].Value-ne[int]$pair.Groups['b'].Value){return $null}
  $vals=@()
  foreach($m in [regex]::Matches($s,'(?<!\d)(?<mm>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:میلی\s*متر|میلیمتر|mm\b)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)){$vals+=[int]$m.Groups['mm'].Value}
  $vals=@($vals|Sort-Object -Unique)
  if($vals.Count-eq1){return [int]$vals[0]};if($vals.Count-gt1){return $null}
  $m=[regex]::Match($s,'(?<!\d)(?<i>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if($m.Success){$k=([double]$m.Groups['i'].Value).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture);if($imap.ContainsKey($k)){return [int]$imap[$k]}}
  $null
}
function IsPipe([string]$name){
  $n=N $name
  if($n-notmatch '^\s*لوله\s*پلی\s*اتیلن(?:\s|$)'){return $false}
  if($n-match 'نخدار|لی\s*فلت|مه\s*پاش|بارانی|نوار|تیپ|خرطومی|تاشو'){return $false};$true
}
function Family([string]$name){
  $n=N $name;if(IsPipe $name){return 'pipe'};if($n-match 'تبدیل'){return $null}
  if($n-match '^\s*رابط\b|کوپل'){return 'coupling'};if($n-match 'زانویی|زانو'){return 'elbow'};if($n-match 'سه\s*راه|سه‌راه'){return 'tee'};if($n-match 'شیر'){return 'valve'};if($n-match 'مغزی|بوشن|اتصال'){return 'fitting'};$null
}
function Bounds([string]$h){
  if([string]::IsNullOrWhiteSpace($h)){return $null};$marks=@('قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن','قطعات پیشنهادی برای تکمیل خط پلی اتیلن','محصولات مرتبط','محصولات پیشنهادی','محصولات مکمل','پیشنهادهای مرتبط','پیشنهاد خرید','برای تکمیل خرید','همراه این محصول','خرید همزمان');$idx=-1;$mk=$null
  foreach($m in $marks){$x=$h.IndexOf($m,[StringComparison]::OrdinalIgnoreCase);if($x-ge0-and($idx-lt0-or$x-lt$idx)){$idx=$x;$mk=$m}}
  if($idx-lt0){return $null};$st=$h.LastIndexOf('<h2',$idx,[StringComparison]::OrdinalIgnoreCase);if($st-lt0){return $null};$en=$h.IndexOf('<h2',$idx+$mk.Length,[StringComparison]::OrdinalIgnoreCase);if($en-lt0){$en=$h.Length};[pscustomobject]@{start=$st;end=$en;marker=$mk}
}
function Strip([string]$h){if($null-eq$h){return ''};$b=Bounds $h;if($null-eq$b){return $h};$h.Substring(0,$b.start)+$h.Substring($b.end)}
function Plain([string]$h){if($null-eq$h){return ''};$s=[regex]::Replace($h,'<[^>]+>',' ');$s=[Net.WebUtility]::HtmlDecode($s);([regex]::Replace($s,'\s+',' ')).Trim()}
function SetBlock([string]$h,[string]$block){
  if($null-eq$h){$h=''};$b=Bounds $h;if($null-ne$b){return $h.Substring(0,$b.start)+$block+$h.Substring($b.end)}
  foreach($m in @('پرسش‌های پرتکرار','پرسش های پرتکرار','سوالات متداول','سؤالات متداول')){$i=$h.IndexOf($m,[StringComparison]::OrdinalIgnoreCase);if($i-ge0){$x=$h.LastIndexOf('<h2',$i,[StringComparison]::OrdinalIgnoreCase);if($x-ge0){return $h.Insert($x,$block)}}};$h.TrimEnd()+"`n"+$block
}
function Label([string]$f){switch($f){'pipe'{'لوله پلی‌اتیلن هم‌سایز'}'coupling'{'رابط هم‌سایز'}'elbow'{'زانو هم‌سایز'}'tee'{'سه‌راه هم‌سایز'}'valve'{'شیر هم‌سایز'}default{'اتصال هم‌سایز'}}}
function Note([string]$f,[string]$s){switch($f){'pipe'{"برای اجرای همان خط $s میلی‌متری."}'coupling'{'برای اتصال مستقیم دو بخش هم‌سایز خط.'}'elbow'{'برای تغییر مسیر خط بدون تغییر سایز نامی.'}'tee'{'برای گرفتن انشعاب هم‌سایز از مسیر.'}'valve'{'برای قطع و وصل جریان در همین سایز نامی.'}default{'برای تکمیل اتصال در همین سایز نامی.'}}}
function Block($t){
  $sf=PF ([string]$t.size_mm);$li=@();foreach($r in @($t.proposed_products)){$nm=[Net.WebUtility]::HtmlEncode([string]$r.name);$u=[Net.WebUtility]::HtmlEncode([string]$r.permalink);$l=[Net.WebUtility]::HtmlEncode((Label $r.family));$n=[Net.WebUtility]::HtmlEncode((Note $r.family $sf));$li+=('<li style="margin:7px 0"><strong>{0}:</strong> <a style="color:#176b3a;font-weight:700" href="{1}">{2}</a> — {3}</li>'-f$l,$u,$nm,$n)};$list=$li-join"`n"
@"
<h2 style="font-size:24px;line-height:1.8;color:#176b3a;margin:34px 0 14px;border-right:5px solid #5d9a68;padding-right:12px">قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن $sf میلی‌متر</h2>
<div style="background:#f7fbf8;border:1px solid #dbe8df;border-radius:16px;padding:17px;margin:15px 0">
<p>اگر این درپوش را برای بستن انتهای خط پلی‌اتیلن $sf میلی‌متری انتخاب می‌کنید، لوله و قطعات کناری شبکه هم باید با همین سایز نامی هماهنگ باشند. پیشنهادهای زیر از محصولات واقعی فروشگاه و با تطبیق مستقیم سایز انتخاب شده‌اند تا هنگام تکمیل خط، قطعه نامرتبط یا تبدیل ناخواسته وارد انتخاب شما نشود.</p>
<p>اول لوله پلی‌اتیلن هم‌سایز آمده است؛ بعد از آن فقط چند قطعه کاربردیِ هم‌سایز برای ادامه خط، تغییر مسیر، انشعاب یا کنترل جریان پیشنهاد شده‌اند.</p>
<ul style="padding-right:22px;margin:10px 0">$list</ul>
<p style="margin:12px 0 0"><strong>قبل از خرید:</strong> عدد سایز روی لوله یا اتصال فعلی را با $sf میلی‌متر تطبیق دهید. اگر سایز خط متفاوت است، درپوش و قطعات مکمل را بر اساس همان سایز انتخاب کنید.</p>
</div>
"@
}
function Hash([string]$x){if($null-eq$x){$x=''};$sha=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($x)))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}}
function Integrity($p){$o=[ordered]@{id=[int]$p.id;name=[string]$p.name;slug=[string]$p.slug;status=[string]$p.status;type=[string]$p.type;sku=[string]$p.sku;price=[string]$p.price;regular_price=[string]$p.regular_price;sale_price=[string]$p.sale_price;manage_stock=[bool]$p.manage_stock;stock_quantity=$p.stock_quantity;stock_status=[string]$p.stock_status;backorders=[string]$p.backorders;short_description=Hash([string]$p.short_description);categories=@($p.categories|%{[int]$_.id}|Sort-Object);tags=@($p.tags|%{[int]$_.id}|Sort-Object);images=@($p.images|%{[int]$_.id}|Sort-Object);upsell=@($p.upsell_ids|%{[int]$_}|Sort-Object);cross=@($p.cross_sell_ids|%{[int]$_}|Sort-Object);attributes=($p.attributes|ConvertTo-Json -Depth 30 -Compress)};Hash($o|ConvertTo-Json -Depth 50 -Compress)}
function Verify([string]$h,$t){$b=Bounds $h;if($null-eq$b){return[pscustomobject]@{ok=$false;reason='block_missing'}};$x=$h.Substring($b.start,$b.end-$b.start);foreach($r in@($t.proposed_products)){if($x.IndexOf([string]$r.permalink,[StringComparison]::OrdinalIgnoreCase)-lt0){return[pscustomobject]@{ok=$false;reason="missing_$($r.id)"}}};$links=@([regex]::Matches($x,'<a\b[^>]*href=["''][^"'']+["''][^>]*>',[Text.RegularExpressions.RegexOptions]::IgnoreCase));if($links.Count-ne@($t.proposed_products).Count){return[pscustomobject]@{ok=$false;reason='link_count'}};if($x-notmatch'لوله\s*پلی.?اتیلن\s*هم.?سایز'){return[pscustomobject]@{ok=$false;reason='pipe_copy_missing'}};[pscustomobject]@{ok=$true;reason='ok'}}

$cat=@(Api 'GET' ("wp-json/wc/v3/products/categories?slug="+[Uri]::EscapeDataString($slug)+"&per_page=100"));if($cat.Count-ne1){Fail "Expected one category; got $($cat.Count)"};$cat=$cat[0];$cid=[int]$cat.id
$products=@(Products);$by=@{};foreach($p in$products){$by[[int]$p.id]=$p}
$pipeCatalog=@();$loosePipeLike=@();foreach($p in$products){$nn=N([string]$p.name);if($nn-match'^\s*لوله'){$loosePipeLike+=[pscustomobject]@{id=[int]$p.id;name=[string]$p.name;size_mm=Size([string]$p.name);strict_pe_pipe=(IsPipe([string]$p.name))}};if(IsPipe([string]$p.name){$pipeCatalog+=[pscustomobject]@{id=[int]$p.id;name=[string]$p.name;size_mm=Size([string]$p.name);permalink=[string]$p.permalink;stock_status=[string]$p.stock_status}}}
$targets=@();foreach($p in$products){$in=$false;foreach($c in@($p.categories)){if([int]$c.id-eq$cid){$in=$true;break}};if(-not$in){continue};$size=Size([string]$p.name);$pipes=@();$fam=@{};if($null-ne$size){foreach($c in$products){if([int]$c.id-eq[int]$p.id-or[string]$c.catalog_visibility-eq'hidden'){continue};$inTarget=$false;foreach($cc in@($c.categories)){if([int]$cc.id-eq$cid){$inTarget=$true;break}};if($inTarget){continue};$cn=N([string]$c.name);if($cn-match'درپوش|تبدیل'){continue};$cs=Size([string]$c.name);if($null-eq$cs-or[int]$cs-ne[int]$size){continue};$f=Family([string]$c.name);if(-not$f){continue};$row=[pscustomobject]@{id=[int]$c.id;name=[string]$c.name;permalink=[string]$c.permalink;family=$f;stock_status=[string]$c.stock_status};if($f-eq'pipe'){$pipes+=$row}else{if(-not$fam.ContainsKey($f)){$fam[$f]=@()};$fam[$f]+=$row}}};$pipes=@($pipes|Sort-Object @{Expression={if($_.stock_status-eq'instock'){0}else{1}}},id);$sel=@($pipes|Select-Object -First 2);foreach($f in@('coupling','elbow','tee','valve','fitting')){if($sel.Count-ge$max){break};if($fam.ContainsKey($f)){$b=@($fam[$f]|Sort-Object @{Expression={if($_.stock_status-eq'instock'){0}else{1}}},id|Select-Object -First 1);if($b.Count){$sel+=$b[0]}}};if($sel.Count-gt$max){$sel=@($sel|Select-Object -First $max)};$bnd=Bounds([string]$p.description);$targets+=[pscustomobject]@{id=[int]$p.id;name=[string]$p.name;size_mm=$size;existing_recommendation_block=($null-ne$bnd);same_size_pipe_count=$pipes.Count;proposed_products=@($sel|%{[pscustomobject]@{id=$_.id;name=$_.name;permalink=$_.permalink;family=$_.family;reason="same_size_${size}mm"}})}}
$un=@($targets|?{$null-eq$_.size_mm});$mp=@($targets|?{[int]$_.same_size_pipe_count-lt1});$empty=@($targets|?{@($_.proposed_products).Count-lt1})
if($mode-eq'apply_description' -and $un.Count){Fail "Refusing apply: unparsed $((@($un.id)-join','))"};if($mode-eq'apply_description' -and $mp.Count){Fail "Refusing apply: no same-size polyethylene pipe for $((@($mp.id)-join','))"};if($mode-eq'apply_description' -and $empty.Count){Fail "Refusing apply: empty recommendations $((@($empty.id)-join','))"}
$changes=@();if($mode-eq'apply_description'){foreach($t in$targets){$id=[int]$t.id;$before=$by[$id];$integ=Integrity $before;$outside=Plain(Strip([string]$before.description));$desired=SetBlock([string]$before.description)(Block $t);$v0=Verify([string]$before.description)$t;if($v0.ok){$changes+=[pscustomobject]@{id=$id;changed=$false;semantic_verified=$true;integrity_unchanged=$true;outside_text_unchanged=$true};continue};$null=Api 'PUT' "wp-json/wc/v3/products/$id" ([ordered]@{description=$desired});$after=Api 'GET' "wp-json/wc/v3/products/$id";$v=Verify([string]$after.description)$t;$iu=((Integrity $after)-eq$integ);$ou=(Plain(Strip([string]$after.description))-ceq$outside);if(-not$v.ok){Fail "Readback failed ${id}: $($v.reason)"};if(-not$iu){Fail "Integrity mismatch $id"};if(-not$ou){Fail "Outside text mismatch $id"};$changes+=[pscustomobject]@{id=$id;changed=$true;semantic_verified=$true;integrity_unchanged=$true;outside_text_unchanged=$true}}}
$rec=[ordered]@{ok=$true;mode=$mode;executed_at_utc=[DateTime]::UtcNow.ToString('o');category=[ordered]@{id=$cid;name=[string]$cat.name;slug=[string]$cat.slug};published_product_count=$products.Count;target_count=$targets.Count;unparsed_target_count=$un.Count;missing_same_size_pipe_count=$mp.Count;empty_recommendation_count=$empty.Count;rules=[ordered]@{pipe='strict product name starts with لوله پلی اتیلن; no substring matches';mixed_sizes='reducers and mixed nominal sizes are excluded';related='up to two exact same-size PE pipes plus one exact same-size product per useful family';mutation='description only';protected='commercial, stock, identity, taxonomy, media, attributes, upsells/cross-sells and short description readback-protected'};unparsed_targets=@($un|Select-Object id,name);missing_pipe_targets=@($mp|Select-Object id,name,size_mm);pipe_catalog=@($pipeCatalog);loose_pipe_like_catalog=@($loosePipeLike);targets=@($targets);changes=@($changes);changed_count=@($changes|?{$_.changed}).Count;semantic_verified_count=@($changes|?{$_.semantic_verified}).Count;integrity_verified_count=@($changes|?{$_.integrity_unchanged}).Count;outside_text_verified_count=@($changes|?{$_.outside_text_unchanged}).Count}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null};$rec|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8;Write-Host "K20_END_CAP_V2_OK mode=$mode targets=$($targets.Count) missingPipe=$($mp.Count)"
