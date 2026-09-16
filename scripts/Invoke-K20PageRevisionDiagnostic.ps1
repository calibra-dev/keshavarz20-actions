param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 20
$id=[int]$req.id
if($id-ne13){throw 'Diagnostic is hard-limited to page ID 13.'}
$phrase=[string]$req.phrase
$base=$env:WP_BASE_URL.TrimEnd('/');$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"));$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Hash([string]$t){if($null-eq$t){return''};$s=[Security.Cryptography.SHA256]::Create();try{return([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes($t))).Replace('-','').ToLowerInvariant())}finally{$s.Dispose()}}
function C([string]$t,[string]$n){if([string]::IsNullOrEmpty($t)-or[string]::IsNullOrEmpty($n)){return 0};return [regex]::Matches($t,[regex]::Escape($n)).Count}
$revs=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${id}/revisions?context=edit&per_page=100" -Headers $headers -Method GET -TimeoutSec 180
$rows=@()
foreach($r in @($revs)){
  $meta=$r.meta
  $ed=''
  if($meta -and $meta.PSObject.Properties['_elementor_data']){$ed=[string]$meta._elementor_data}
  $rows+=,[pscustomobject][ordered]@{
    id=[int]$r.id;date_gmt=[string]$r.date_gmt;modified_gmt=[string]$r.modified_gmt;parent=[int]$r.parent;
    content_raw_sha256=Hash([string]$r.content.raw);elementor_present=(-not[string]::IsNullOrWhiteSpace($ed));elementor_length=$ed.Length;elementor_sha256=Hash($ed);
    phrase_count=C $ed $phrase;old_h1_count=C $ed ("<h1>$phrase</h1>");new_h2_count=C $ed ("<h2>$phrase</h2>");css_h1_count=C $ed '.k20-hero h1';css_h2_count=C $ed '.k20-hero h2'
  }
}
$result=[ordered]@{ok=$true;page_id=13;revision_count=$rows.Count;revisions=$rows;executed_at_utc=[DateTime]::UtcNow.ToString('o')}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "REVISION_DIAGNOSTIC_OK count=$($rows.Count)"
