param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 20
$id=[int]$req.id;$phrase=[string]$req.phrase
if($id-lt1-or[string]::IsNullOrWhiteSpace($phrase)){throw 'id and phrase are required.'}
$base=$env:WP_BASE_URL.TrimEnd('/');$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"));$headers=@{Authorization="Basic $auth";Accept='application/json'}
$p=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}?context=edit" -Headers $headers -Method GET -TimeoutSec 180
$raw=[string]$p.content.raw;$rendered=[string]$p.content.rendered
$meta=$p.meta;$elementorData=''
if($meta -and $meta.PSObject.Properties['_elementor_data']){$elementorData=[string]$meta._elementor_data}
function C([string]$t,[string]$n){if([string]::IsNullOrEmpty($n)){return 0};$c=0;$o=0;while(($i=$t.IndexOf($n,$o,[StringComparison]::OrdinalIgnoreCase))-ge0){$c++;$o=$i+$n.Length};return $c}
function Hash([string]$t){$s=[Security.Cryptography.SHA256]::Create();try{return([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes($t))).Replace('-','').ToLowerInvariant())}finally{$s.Dispose()}}
function HeadingCount([string]$t,[string]$tag,[string]$text){$pattern='(?is)<'+$tag+'\b[^>]*>\s*'+[regex]::Escape($text)+'\s*</'+$tag+'>';return [regex]::Matches($t,$pattern).Count}
function Clip([string]$t,[string]$n){$i=$t.IndexOf($n,[StringComparison]::OrdinalIgnoreCase);if($i-lt0){return ''};$s=[Math]::Max(0,$i-180);$l=[Math]::Min(520,$t.Length-$s);return $t.Substring($s,$l)}
$decodedHits=@();$decodedOk=$false
if(-not[string]::IsNullOrWhiteSpace($elementorData)){
  try{
    $root=$elementorData|ConvertFrom-Json -Depth 100;$decodedOk=$true
    function Walk($node,[string]$path){
      if($null-eq$node){return}
      if($node-is[string]){if($node.IndexOf($phrase,[StringComparison]::OrdinalIgnoreCase)-ge0){$script:decodedHits+=,[pscustomobject][ordered]@{path=$path;snippet=(Clip $node $phrase);target_h1_count=(HeadingCount $node 'h1' $phrase);target_h2_count=(HeadingCount $node 'h2' $phrase)}};return}
      if($node-is[pscustomobject]){foreach($prop in $node.PSObject.Properties){Walk $prop.Value ($path+'.'+$prop.Name)};return}
      if(($node-is[System.Collections.IEnumerable])-and-not($node-is[string])){$i=0;foreach($item in $node){Walk $item ($path+'['+$i+']');$i++}}
    }
    Walk $root '$'
  }catch{}
}
$record=[ordered]@{
  ok=$true;mode='read-only';executed_at_utc=[DateTime]::UtcNow.ToString('o');page=[ordered]@{id=[int]$p.id;slug=[string]$p.slug;status=[string]$p.status;modified_gmt=[string]$p.modified_gmt};
  post_content=[ordered]@{length=$raw.Length;sha256=(Hash $raw);phrase_count=(C $raw $phrase);target_h1_count=(HeadingCount $raw 'h1' $phrase);target_h2_count=(HeadingCount $raw 'h2' $phrase)};
  content_rendered=[ordered]@{length=$rendered.Length;sha256=(Hash $rendered);phrase_count=(C $rendered $phrase);target_h1_count=(HeadingCount $rendered 'h1' $phrase);target_h2_count=(HeadingCount $rendered 'h2' $phrase)};
  elementor_meta=[ordered]@{present=(-not[string]::IsNullOrWhiteSpace($elementorData));length=$elementorData.Length;sha256=if($elementorData){Hash $elementorData}else{''};literal_phrase_count=(C $elementorData $phrase);decoded_ok=$decodedOk;decoded_hit_count=$decodedHits.Count;decoded_hits=@($decodedHits)};
  meta_keys=@($meta.PSObject.Properties.Name)
}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$record|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "ELEMENTOR_META_DIAGNOSTIC_OK id=$id raw_h1=$($record.post_content.target_h1_count) rendered_h1=$($record.content_rendered.target_h1_count) decoded_hits=$($decodedHits.Count)"
