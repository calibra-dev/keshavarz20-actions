param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 20
$action=[string]$req.action
if($action-ne'elementor.cache.clear'){throw 'Only elementor.cache.clear is allowed.'}
$verifyId=[int]($req.verify_page_id)
$verifyPath=[string]$req.verify_path
$phrase=[string]$req.verify_phrase
if($verifyId-ne13 -or $verifyPath-ne'/refund_returns/' -or [string]::IsNullOrWhiteSpace($phrase)){throw 'This guarded workflow is limited to the verified refund page target.'}
$base=$env:WP_BASE_URL.TrimEnd('/')
$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}

$cacheUri="$base/wp-json/elementor/v1/cache"
try{
  $cacheResp=Invoke-RestMethod -Uri $cacheUri -Headers $headers -Method DELETE -TimeoutSec 180
  $cacheOk=$true
}catch{
  throw "Elementor cache DELETE failed: $($_.Exception.Message)"
}
Start-Sleep -Seconds 3
$page=Invoke-RestMethod -Uri "$base/wp-json/wp/v2/pages/${verifyId}?context=edit" -Headers $headers -Method GET -TimeoutSec 180
$rendered=[string]$page.content.rendered
$restH1=[regex]::Matches($rendered,'(?is)<h1\b[^>]*>\s*'+[regex]::Escape($phrase)+'\s*</h1>').Count
$restH2=[regex]::Matches($rendered,'(?is)<h2\b[^>]*>\s*'+[regex]::Escape($phrase)+'\s*</h2>').Count
$front=Invoke-WebRequest -Uri "$base$verifyPath?k20verify=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())" -Headers @{'Cache-Control'='no-cache';Pragma='no-cache'} -TimeoutSec 180 -MaximumRedirection 5
$html=[string]$front.Content
$frontTargetH1=[regex]::Matches($html,'(?is)<h1\b[^>]*>\s*'+[regex]::Escape($phrase)+'\s*</h1>').Count
$frontTargetH2=[regex]::Matches($html,'(?is)<h2\b[^>]*>\s*'+[regex]::Escape($phrase)+'\s*</h2>').Count
$totalH1=[regex]::Matches($html,'(?is)<h1\b[^>]*>').Count
if($restH1-ne0-or$restH2-ne1){throw "REST render verification failed h1=$restH1 h2=$restH2"}
if($frontTargetH1-ne0-or$frontTargetH2-ne1-or$totalH1-ne1){throw "Live verification failed total_h1=$totalH1 target_h1=$frontTargetH1 target_h2=$frontTargetH2"}
$result=[ordered]@{
 ok=$true;action=$action;cache_endpoint='/elementor/v1/cache';cache_delete_succeeded=$cacheOk;
 verify=[ordered]@{page_id=$verifyId;path=$verifyPath;rest_target_h1=$restH1;rest_target_h2=$restH2;http_status=[int]$front.StatusCode;live_total_h1=$totalH1;live_target_h1=$frontTargetH1;live_target_h2=$frontTargetH2};
 executed_at_utc=[DateTime]::UtcNow.ToString('o')
}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "ELEMENTOR_CACHE_REFRESH_OK page=$verifyId live_h1=$totalH1 target_h2=$frontTargetH2"
