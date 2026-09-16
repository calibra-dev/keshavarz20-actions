param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
$req=Get-Content -Raw -LiteralPath $RequestPath|ConvertFrom-Json -Depth 20
$terms=@($req.terms|ForEach-Object{([string]$_).ToLowerInvariant()}|Where-Object{$_})
if($terms.Count-lt1){throw 'terms are required.'}
$base=$env:WP_BASE_URL.TrimEnd('/')
$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}
$index=Invoke-RestMethod -Uri "$base/wp-json/" -Headers $headers -Method GET -TimeoutSec 180
$matches=@()
foreach($prop in $index.routes.PSObject.Properties){
  $route=[string]$prop.Name;$low=$route.ToLowerInvariant();$hit=$false
  foreach($t in $terms){if($low.Contains($t)){$hit=$true;break}}
  if(-not$hit){continue}
  $def=$prop.Value
  $methods=@()
  foreach($ep in @($def.endpoints)){foreach($m in @($ep.methods)){if($m){$methods+=[string]$m}}}
  $matches+=,[pscustomobject][ordered]@{route=$route;methods=@($methods|Sort-Object -Unique);namespace=[string]$def.namespace}
}
$result=[ordered]@{ok=$true;mode='read-only';terms=$terms;matched=$matches.Count;routes=@($matches|Sort-Object route);executed_at_utc=[DateTime]::UtcNow.ToString('o')}
New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath)|Out-Null
$result|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "REST_ROUTE_DIAGNOSTIC_OK matches=$($matches.Count)"
