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
function HeadingCount([string]$t,[string]$tag,[string]$text){$pattern='(?is)<'+$tag+'\b[^>]*>\s*'+[regex]::Escape($text)+'\s*</'+$tag+'>' ;return [regex]::Matches($t,$pattern).Count}
$record=[ordered]@{
  ok=$true;mode='read-only';executed_at_utc=[DateTime]::UtcNow.ToString('o');page=[ordered]@{id=[int]$p.id;slug=[string]$p.slug;status=[string]$p.status;modified_gmt=[string]$p.modified_gmt};
  post_content=[ordered]@{length=$raw.Length;sha256=(Hash $raw);phrase_count=(C $raw $phrase);target_h1_count=(HeadingCount $raw 'h1' $phrase);target_h2_count=(HeadingCount $raw 'h2' $phrase)};
  content_rendered=[ordered]@{length=$rendered.Length;sha256=(Hash $rendered);phrase_count=(C $rendered $phrase);target_h1_count=(HeadingCount $rendered 'h1' $phrase);target_h2_count=(HeadingCount $rendered 'h2' $phrase)};
  elementor_meta=[ordered]@{present=(-not[string]::IsNullOrWhiteSpace($elementorData));length=$elementorData.Length;sha256=if($elementorData){Hash $elementorData}else{''};phrase_count=(C $elementorData $phrase);target_h1_count=(HeadingCount $elementorData 'h1' $phrase);target_h2_count=(HeadingCount $elementorData 'h2' $phrase);contains_h1_tag=([regex]::IsMatch($elementorData,'(?i)<h1\b'));contains_h2_tag=([regex]::IsMatch($elementorData,'(?i)<h2\b'))};
  meta_keys=@($meta.PSObject.Properties.Name)
}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$record|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "ELEMENTOR_META_DIAGNOSTIC_OK id=$id raw_h1=$($record.post_content.target_h1_count) rendered_h1=$($record.content_rendered.target_h1_count) elementor_phrase=$($record.elementor_meta.phrase_count)"
