param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){throw "Request file not found: $RequestPath"}
$base=$env:WP_BASE_URL;$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){throw 'Required WordPress secrets are missing.'}
$base=$base.TrimEnd('/')
$req=Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$phrases=@($req.phrases | ForEach-Object {[string]$_} | Where-Object {-not [string]::IsNullOrWhiteSpace($_)} | Select-Object -Unique)
$urls=@($req.urls | ForEach-Object {[string]$_} | Where-Object {-not [string]::IsNullOrWhiteSpace($_)} | Select-Object -Unique)
if($phrases.Count-lt1){throw 'At least one phrase is required.'};if($urls.Count-lt1){throw 'At least one URL is required.'}
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"));$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Invoke-JsonGet([string]$Path){Invoke-RestMethod -Uri ($base+'/'+$Path.TrimStart('/')) -Method GET -Headers $headers -TimeoutSec 180}
function TextOnly([string]$Html){if([string]::IsNullOrWhiteSpace($Html)){return ''};$x=[regex]::Replace($Html,'<script\b[^>]*>.*?</script>',' ','IgnoreCase,Singleline');$x=[regex]::Replace($x,'<style\b[^>]*>.*?</style>',' ','IgnoreCase,Singleline');$x=[regex]::Replace($x,'<[^>]+>',' ');$x=[Net.WebUtility]::HtmlDecode($x);return [regex]::Replace($x,'\s+',' ').Trim()}
function Snippet([string]$Text,[string]$Needle){$i=$Text.IndexOf($Needle,[StringComparison]::OrdinalIgnoreCase);if($i-lt0){return ''};$start=[Math]::Max(0,$i-180);$len=[Math]::Min(520,$Text.Length-$start);return $Text.Substring($start,$len)}
function Get-Attr([string]$Tag,[string]$Name){$pattern='(?is)\b'+[regex]::Escape($Name)+'\s*=\s*["'']([^"'']*)["'']';$m=[regex]::Match($Tag,$pattern);if($m.Success){return [Net.WebUtility]::HtmlDecode($m.Groups[1].Value)};return ''}
function Get-Organizations($Node){
  $items=@();if($null-eq$Node){return @()}
  if($Node-is[pscustomobject]){
    $tp=$Node.PSObject.Properties['@type'];if($tp-and(@($tp.Value)-contains'Organization')){
      $logo=$Node.PSObject.Properties['logo'];$name=$Node.PSObject.Properties['name'];$url=$Node.PSObject.Properties['url'];$idp=$Node.PSObject.Properties['@id']
      $items+=,[pscustomobject][ordered]@{id=if($idp){[string]$idp.Value}else{''};name=if($name){[string]$name.Value}else{''};url=if($url){[string]$url.Value}else{''};has_logo=($null-ne$logo-and$null-ne$logo.Value);logo=if($logo){$logo.Value}else{$null}}
    }
    foreach($p in $Node.PSObject.Properties){$items+=@(Get-Organizations $p.Value)}
  }elseif(($Node-is[System.Collections.IEnumerable])-and-not($Node-is[string])){foreach($item in $Node){$items+=@(Get-Organizations $item)}}
  return @($items)
}
$pageMatches=@();$searchMatches=@()
foreach($phrase in $phrases){
  $enc=[Uri]::EscapeDataString($phrase)
  try{$pages=@(Invoke-JsonGet "wp-json/wp/v2/pages?context=edit&search=$enc&per_page=100&_fields=id,slug,status,link,parent,template,title,content,excerpt");foreach($p in $pages){$raw=[string]$p.content.raw;$title=[string]$p.title.raw;$pageMatches+=,[pscustomobject][ordered]@{phrase=$phrase;id=[int]$p.id;slug=[string]$p.slug;status=[string]$p.status;link=[string]$p.link;parent=[int]$p.parent;template=[string]$p.template;title=$title;content_contains_phrase=$raw.Contains($phrase);title_contains_phrase=$title.Contains($phrase);content_snippet=Snippet (TextOnly $raw) $phrase}}}catch{$pageMatches+=,[pscustomobject][ordered]@{phrase=$phrase;error=$_.Exception.Message}}
  try{$rows=@(Invoke-JsonGet "wp-json/wp/v2/search?search=$enc&per_page=100&type=post&subtype=any");foreach($r in $rows){$searchMatches+=,[pscustomobject][ordered]@{phrase=$phrase;id=[int]$r.id;title=[string]$r.title;url=[string]$r.url;type=[string]$r.type;subtype=[string]$r.subtype}}}catch{$searchMatches+=,[pscustomobject][ordered]@{phrase=$phrase;error=$_.Exception.Message}}
}
$frontends=@()
foreach($url in $urls){
  try{
    $resp=Invoke-WebRequest -Uri $url -Method GET -Headers @{'User-Agent'='K20-Frontend-RootCause/2026-09-16';'Accept'='text/html,application/xhtml+xml'} -MaximumRedirection 5 -TimeoutSec 90 -SkipHttpErrorCheck;$html=[string]$resp.Content
    $h1s=@();foreach($m in [regex]::Matches($html,'(?is)<h1\b[^>]*>(.*?)</h1>')){$h1s+=,(TextOnly $m.Groups[1].Value)}
    $missingAlt=@();foreach($m in [regex]::Matches($html,'(?is)<img\b[^>]*>')){$tag=$m.Value;$altPresent=[regex]::IsMatch($tag,'(?is)\balt\s*=');$alt=Get-Attr $tag 'alt';if((-not$altPresent)-or[string]::IsNullOrWhiteSpace($alt)){$src=Get-Attr $tag 'src';if([string]::IsNullOrWhiteSpace($src)){$src=Get-Attr $tag 'data-src'};$missingAlt+=,[pscustomobject][ordered]@{alt_attribute_present=$altPresent;src=$src;class=(Get-Attr $tag 'class');width=(Get-Attr $tag 'width');height=(Get-Attr $tag 'height')}}}
    $orgs=@();foreach($m in [regex]::Matches($html,'(?is)<script\b[^>]*type\s*=\s*(["'']?)application/ld\+json\1[^>]*>(.*?)</script>')){try{$json=$m.Groups[2].Value|ConvertFrom-Json -Depth 100;$orgs+=@(Get-Organizations $json)}catch{}}
    $plainHtml=TextOnly $html;$phraseHits=@();foreach($phrase in $phrases){$phraseHits+=,[pscustomobject][ordered]@{phrase=$phrase;present=$html.Contains($phrase);snippet=Snippet $plainHtml $phrase}}
    $frontends+=,[pscustomobject][ordered]@{url=$url;http_status=[int]$resp.StatusCode;html_bytes=[Text.Encoding]::UTF8.GetByteCount($html);h1_count=$h1s.Count;h1s=@($h1s);phrase_hits=@($phraseHits);missing_alt_count=$missingAlt.Count;missing_alt_images=@($missingAlt);organization_nodes=@($orgs);organization_count=$orgs.Count}
  }catch{$frontends+=,[pscustomobject][ordered]@{url=$url;error=$_.Exception.Message}}
}
$record=[ordered]@{ok=$true;executed_at_utc=[DateTime]::UtcNow.ToString('o');mode='read-only';phrases=@($phrases);page_search_matches=@($pageMatches);wp_search_matches=@($searchMatches);frontend_pages=@($frontends)}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null};$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "FRONTEND_ROOTCAUSE_OK pages=$($frontends.Count) page_matches=$($pageMatches.Count) search_matches=$($searchMatches.Count)"
