param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
function Fail([string]$Message) { throw $Message }
if (-not (Test-Path -LiteralPath $RequestPath)) { Fail "Request file not found: $RequestPath" }
foreach ($name in 'WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD') {
  if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) { Fail "Missing required repository secret: $name" }
}

$allowed = @('system.info','rest.proxy','seo.read','seo.update','elementor.inspect','cache.status','cache.purge','audit.tail','batch')
$forbidden = @(
  'price','regular_price','sale_price','date_on_sale_from','date_on_sale_to','discount','discount_type','coupon','coupon_code',
  'payment_method','payment_method_title','tax_status','tax_class','password','application_password','token','secret','api_key',
  'consumer_key','consumer_secret','role','roles','capability','capabilities','author','user_id','customer_id','billing',
  'shipping_address','email','phone','order_id','orders','sql','query_sql','php','code','command','shell'
)
function Assert-Safe($Value, [string]$Path='request') {
  if ($null -eq $Value) { return }
  if ($Value -is [pscustomobject]) {
    foreach ($p in $Value.PSObject.Properties) {
      $name = $p.Name.ToLowerInvariant()
      if ($forbidden -contains $name) { Fail "Forbidden key at ${Path}: $($p.Name)" }
      Assert-Safe $p.Value "$Path.$($p.Name)"
    }
    return
  }
  if (($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])) {
    $i=0; foreach ($item in $Value) { Assert-Safe $item "$Path[$i]"; $i++ }
  }
}

$request = Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$action = [string]$request.action
if ([string]::IsNullOrWhiteSpace($action) -or $allowed -notcontains $action) { Fail "Action is not allow-listed: $action" }
Assert-Safe $request
if ([string]::IsNullOrWhiteSpace([string]$request.request_id)) {
  $request | Add-Member -NotePropertyName request_id -NotePropertyValue ("gh-" + [IO.Path]::GetFileNameWithoutExtension($RequestPath)) -Force
}

$base = $env:WP_BASE_URL.TrimEnd('/')
$endpoint = "$base/wp-json/keshavarz20-ops/v3/execute"
$authText = "$($env:WP_USERNAME):$($env:WP_APP_PASSWORD)"
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($authText))
$headers = @{ Authorization="Basic $auth"; Accept='application/json' }
$body = $request | ConvertTo-Json -Depth 100 -Compress
$response = Invoke-WebRequest -Uri $endpoint -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180 -SkipHttpErrorCheck
$status = [int]$response.StatusCode
$parsed = $null
try { $parsed = $response.Content | ConvertFrom-Json -Depth 100 } catch {}

$record = [ordered]@{
  ok = ($status -ge 200 -and $status -lt 300 -and $parsed -and $parsed.ok -eq $true)
  http_code = $status
  request = [IO.Path]::GetFileName($RequestPath)
  action = $action
  request_id = [string]$request.request_id
  dry_run = [bool]$request.dry_run
  executed_at_utc = [DateTime]::UtcNow.ToString('o')
  bridge = if ($parsed) { [string]$parsed.bridge } else { $null }
  bridge_version = if ($parsed) { [string]$parsed.version } else { $null }
  error_code = if ($parsed -and $parsed.ok -ne $true) { [string]$parsed.code } else { $null }
  message = if ($parsed -and $parsed.ok -ne $true) { [string]$parsed.message } else { $null }
}

if ($parsed -and $parsed.result) {
  $result = $parsed.result
  $safe = [ordered]@{}
  foreach ($name in @('id','type','status','slug','title','name','sku','stock_status','stock_quantity','modified_gmt','permalink','link','count','purged','planned','version','wp_version','php_version','woocommerce','yoast','elementor','object_cache','method','path')) {
    $p = $result.PSObject.Properties[$name]; if ($p) { $safe[$name] = $p.Value }
  }
  if ($result.data) {
    $data = $result.data
    if ($data -is [System.Collections.IEnumerable] -and -not ($data -is [string]) -and -not ($data -is [pscustomobject])) {
      $safe['data_count'] = @($data).Count
    } else {
      foreach ($name in @('id','type','status','slug','title','name','sku','stock_status','stock_quantity','modified_gmt','link')) {
        $p = $data.PSObject.Properties[$name]; if ($p) { $safe["data_$name"] = $p.Value }
      }
    }
  }
  $record['result'] = $safe
}

$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$record | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding utf8
if (-not $record.ok) { Fail "K20 Bridge v3 request failed with HTTP $status" }
Write-Host "K20_BRIDGE_V3_OK action=$action request_id=$($request.request_id)"
