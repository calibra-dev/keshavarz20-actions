param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
function Fail([string]$m){throw $m}
if(-not(Test-Path -LiteralPath $RequestPath)){Fail "Request file not found: $RequestPath"}
$base=$env:WP_BASE_URL;$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){Fail 'Required WordPress secrets are missing.'}
$base=$base.TrimEnd('/')
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 100
if([string]$req.taxonomy -ne 'product_cat'){Fail 'Only product_cat is allowed.'}
$id=[int]$req.id;if($id-lt1){Fail 'Positive id required.'}
$description=[string]$req.description;if([string]::IsNullOrWhiteSpace($description)){Fail 'description is required.'}
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Invoke-K20([string]$Method,[string]$Path,$Body=$null){
  $args=@{Uri=($base+'/'+$Path.TrimStart('/'));Method=$Method;Headers=$headers;TimeoutSec=180}
  if($null-ne$Body){$args.ContentType='application/json; charset=utf-8';$args.Body=($Body|ConvertTo-Json -Depth 100 -Compress)}
  Invoke-RestMethod @args
}
function DescRaw($o){if($null-eq$o.description){return ''};if($o.description-is[string]){return [string]$o.description};return [string]$o.description.raw}
$before=Invoke-K20 'GET' "wp-json/wp/v2/product_cat/$id?context=edit"
$beforeSnap=[ordered]@{id=[int]$before.id;name=[string]$before.name;slug=[string]$before.slug;parent=[int]$before.parent}
if($req.expected){
  if($req.expected.name-and([string]$req.expected.name-ne$beforeSnap.name)){Fail "Expected name mismatch: $($beforeSnap.name)"}
  if($req.expected.slug-and([string]$req.expected.slug-ne$beforeSnap.slug)){Fail "Expected slug mismatch: $($beforeSnap.slug)"}
  if($null-ne$req.expected.parent-and[int]$req.expected.parent-ne$beforeSnap.parent){Fail "Expected parent mismatch: $($beforeSnap.parent)"}
}
$null=Invoke-K20 'POST' "wp-json/wp/v2/product_cat/$id" ([ordered]@{description=$description})
$after=Invoke-K20 'GET' "wp-json/wp/v2/product_cat/$id?context=edit"
$afterSnap=[ordered]@{id=[int]$after.id;name=[string]$after.name;slug=[string]$after.slug;parent=[int]$after.parent}
if(($beforeSnap|ConvertTo-Json -Compress)-cne($afterSnap|ConvertTo-Json -Compress)){Fail 'Protected term identity fields changed.'}
$raw=DescRaw $after
$missing=@()
foreach($marker in @($req.required_markers)){if(-not$raw.Contains([string]$marker)){$missing+=[string]$marker}}
if($missing.Count-gt0){Fail ("Readback missing required markers: "+($missing-join' | '))}
$record=[ordered]@{
  ok=$true;executed_at_utc=[DateTime]::UtcNow.ToString('o');taxonomy='product_cat';id=$id;
  protected_identity_unchanged=$true;before=$beforeSnap;after=$afterSnap;
  description_length=$raw.Length;required_marker_count=@($req.required_markers).Count;missing_markers=@($missing);
  has_h2=$raw.Contains('<h2');has_paragraph=$raw.Contains('<p');has_table=$raw.Contains('<table');has_list=$raw.Contains('<ul');has_details=$raw.Contains('<details');has_links=$raw.Contains('<a ');
  description=$raw
}
$dir=Split-Path -Parent $OutputPath;if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "RICH_PRODUCT_CATEGORY_OK id=$id length=$($raw.Length) h2=$($record.has_h2) table=$($record.has_table) details=$($record.has_details)"
