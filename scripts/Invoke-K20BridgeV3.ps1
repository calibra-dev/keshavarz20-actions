param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
function Fail([string]$Message){ throw $Message }
if(-not(Test-Path -LiteralPath $RequestPath)){ Fail "Request file not found: $RequestPath" }

$siteActions=@(
  'system.info','rest.proxy','api.contract',
  'seo.read','seo.update',
  'content.search','content.patch','content.block.inspect','content.block.patch',
  'elementor.inspect','elementor.search','elementor.edit','elementor.structure',
  'media.import','media.transform','media.metadata','media.hash','media.duplicates','media.optimize','media.focal_crop','media.watermark',
  'cache.status','cache.purge','audit.tail','batch',
  'job.create','job.status','job.run','job.retry_failed',
  'snapshot.list','snapshot.rollback',
  'approval.status','approval.execute',
  'observability.status','selftest.run',
  'update.check','update.stage','update.apply','update.rollback'
)
$githubActions=@('engine.status','engine.run','gitops.profile')
$allowed=@($siteActions+$githubActions)
$forbidden=@(
  'price','regular_price','sale_price','date_on_sale_from','date_on_sale_to','discount','discount_type','coupon','coupon_code',
  'payment_method','payment_method_title','tax_status','tax_class','password','application_password','token','secret','api_key',
  'consumer_key','consumer_secret','role','roles','capability','capabilities','author','user_id','customer_id','billing',
  'shipping_address','email','phone','order_id','orders','sql','query_sql','php','code','command','shell'
)

function Assert-Safe($Value,[string]$Path='request'){
  if($null -eq $Value){ return }
  if($Value -is [pscustomobject]){
    foreach($p in $Value.PSObject.Properties){
      $name=$p.Name.ToLowerInvariant()
      if($forbidden -contains $name){ Fail "Forbidden key at $Path : $($p.Name)" }
      Assert-Safe $p.Value "$Path.$($p.Name)"
    }
    return
  }
  if(($Value -is [System.Collections.IEnumerable]) -and -not($Value -is [string])){
    $i=0; foreach($item in $Value){ Assert-Safe $item "$Path[$i]"; $i++ }
  }
}
function Write-Result($Object){
  $dir=Split-Path -Parent $OutputPath
  if($dir -and -not(Test-Path -LiteralPath $dir)){ New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $Object | ConvertTo-Json -Depth 80 | Set-Content -LiteralPath $OutputPath -Encoding utf8
}
function Get-Engine([string]$Name){
  switch($Name.ToLowerInvariant()){
    'question' { return @{workflow='k20-customer-question-engine.yml';label='Customer Question Engine v18'} }
    'news' { return @{workflow='k20-daily-agri-news.yml';label='Daily Agriculture News Engine'} }
    'article' { return @{workflow='k20-article-queue-publisher.yml';label='Daily Article Engine'} }
    'social' { return @{workflow='k20-daily-product-social.yml';label='Daily Product Social Engine'} }
    default { Fail "Unknown engine: $Name" }
  }
}

$request=Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$action=[string]$request.action
if([string]::IsNullOrWhiteSpace($action) -or $allowed -notcontains $action){ Fail "Action is not allow-listed: $action" }
Assert-Safe $request
if([string]::IsNullOrWhiteSpace([string]$request.request_id)){
  $request | Add-Member -NotePropertyName request_id -NotePropertyValue ("gh-"+[IO.Path]::GetFileNameWithoutExtension($RequestPath)) -Force
}

if($githubActions -contains $action){
  if($action -eq 'gitops.profile'){
    Write-Result ([ordered]@{
      ok=$true;schema_version='3.2';action=$action;request_id=[string]$request.request_id;profile='keshavarz20-git-ops';
      primary_path='ChatGPT -> GitHub -> guarded gateway -> WordPress/WooCommerce/K20 Bridge';
      engines=@('question','news','article','social');
      hard_guards=@('no price/discount/coupon/payment mutation','no users/roles/capabilities','no credentials/secrets','no arbitrary code/SQL/shell');
      executed_at_utc=[DateTime]::UtcNow.ToString('o')
    })
    exit 0
  }

  foreach($name in 'GH_TOKEN','GITHUB_REPOSITORY'){
    if([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))){ Fail "Missing GitHub runtime variable: $name" }
  }
  $engine=Get-Engine ([string]$request.engine)
  $headers=@{Authorization="Bearer $env:GH_TOKEN";Accept='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28';'User-Agent'='k20-bridge-v32-engine-router'}
  $workflow=[Uri]::EscapeDataString([string]$engine.workflow)

  if($action -eq 'engine.status'){
    $uri="https://api.github.com/repos/$env:GITHUB_REPOSITORY/actions/workflows/$workflow/runs?branch=main&per_page=5"
    $runs=Invoke-RestMethod -Method Get -Uri $uri -Headers $headers -TimeoutSec 60
    $items=@()
    foreach($r in @($runs.workflow_runs)){
      $items += [ordered]@{
        run_id=$r.id;state=$r.status;conclusion=$r.conclusion;event=$r.event;
        started_at=$r.run_started_at;created_at=$r.created_at;finished_at=if($r.status -eq 'completed'){$r.updated_at}else{$null};
        changed_ids=@();errors=@();artifact=$null;next_action=$null
      }
    }
    Write-Result ([ordered]@{
      ok=$true;schema_version='3.2';action=$action;engine=[string]$request.engine;engine_label=$engine.label;
      workflow=$engine.workflow;state=if($items.Count -gt 0){$items[0].state}else{'unknown'};runs=$items;executed_at_utc=[DateTime]::UtcNow.ToString('o')
    })
    exit 0
  }

  $inputs=[ordered]@{}
  switch([string]$request.engine){
    'question' {
      $ea=[string]$request.engine_action; if([string]::IsNullOrWhiteSpace($ea)){ $ea='status' }
      if(@('status','dry_run','submit_one') -notcontains $ea){ Fail "Unsupported question engine action: $ea" }
      $inputs.action=$ea
    }
    'news' {
      $hours=24; if($null -ne $request.lookback_hours){ $hours=[int]$request.lookback_hours }
      if($hours -lt 1 -or $hours -gt 168){ Fail 'lookback_hours must be 1..168' }
      $inputs.lookback_hours=[string]$hours
      $dr=$true; if($null -ne $request.dry_run){ $dr=[bool]$request.dry_run }
      $inputs.dry_run=$dr.ToString().ToLowerInvariant()
    }
    'article' {
      $q=[string]$request.queue_file
      if($q -notmatch '^daily-agri-articles/queue/[A-Za-z0-9._-]+\.json$'){ Fail 'Article engine requires an allow-listed queue_file path.' }
      $inputs.queue_file=$q
    }
    'social' {
      $ea=[string]$request.engine_action; if([string]::IsNullOrWhiteSpace($ea)){ $ea='status' }
      if(@('status','prepare','whatsapp','telegram','instagram') -notcontains $ea){ Fail "Unsupported social engine action: $ea" }
      $inputs.action=$ea
      if(-not[string]::IsNullOrWhiteSpace([string]$request.publish_date)){
        if([string]$request.publish_date -notmatch '^\d{4}-\d{2}-\d{2}$'){ Fail 'publish_date must be YYYY-MM-DD' }
        $inputs.publish_date=[string]$request.publish_date
      }
    }
  }
  $uri="https://api.github.com/repos/$env:GITHUB_REPOSITORY/actions/workflows/$workflow/dispatches"
  $payload=[ordered]@{ref='main';inputs=$inputs} | ConvertTo-Json -Depth 10
  $resp=Invoke-WebRequest -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $payload -TimeoutSec 60 -SkipHttpErrorCheck
  if([int]$resp.StatusCode -ne 204){ Fail "Engine dispatch failed with HTTP $([int]$resp.StatusCode)" }
  Write-Result ([ordered]@{
    ok=$true;schema_version='3.2';action=$action;engine=[string]$request.engine;engine_label=$engine.label;
    workflow=$engine.workflow;state='accepted';started_at=[DateTime]::UtcNow.ToString('o');finished_at=$null;
    changed_ids=@();errors=@();artifact=$null;next_action='engine.status';inputs=$inputs;executed_at_utc=[DateTime]::UtcNow.ToString('o')
  })
  exit 0
}

foreach($name in 'WP_BASE_URL','WP_USERNAME','WP_APP_PASSWORD'){
  if([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))){ Fail "Missing required repository secret: $name" }
}
$base=$env:WP_BASE_URL.TrimEnd('/')
$endpoint="$base/wp-json/keshavarz20-ops/v3/execute"
$authText="$($env:WP_USERNAME):$($env:WP_APP_PASSWORD)"
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($authText))
$headers=@{Authorization="Basic $auth";Accept='application/json'}
$body=$request | ConvertTo-Json -Depth 100 -Compress
$response=Invoke-WebRequest -Uri $endpoint -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180 -SkipHttpErrorCheck
$status=[int]$response.StatusCode
$parsed=$null
try{ $parsed=$response.Content | ConvertFrom-Json -Depth 100 }catch{}

$record=[ordered]@{
  ok=($status -ge 200 -and $status -lt 300 -and $parsed -and $parsed.ok -eq $true)
  schema_version=if($parsed -and $parsed.contract){[string]$parsed.contract}else{$null}
  http_code=$status
  request=[IO.Path]::GetFileName($RequestPath)
  action=$action
  request_id=[string]$request.request_id
  dry_run=[bool]$request.dry_run
  executed_at_utc=[DateTime]::UtcNow.ToString('o')
  bridge=if($parsed){[string]$parsed.bridge}else{$null}
  bridge_version=if($parsed){[string]$parsed.version}else{$null}
  error_code=if($parsed -and $parsed.ok -ne $true){[string]$parsed.code}else{$null}
  message=if($parsed -and $parsed.ok -ne $true){[string]$parsed.message}else{$null}
}
if($parsed -and $parsed.result){
  $result=$parsed.result; $safe=[ordered]@{}
  foreach($name in @(
    'id','status','slug','title','name','sku','stock_status','stock_quantity','count','purged','planned','version','wp_version','php_version',
    'woocommerce','yoast','elementor','object_cache','method','path','job_id','cursor','total','success','failed','retrying','dead_letter',
    'matches','changed','before_sha256','after_sha256','source_attachment_id','new_attachment_id','approval_id','fingerprint','rolled_back',
    'current_version','available_version','update_available','staged','applied','installed_file_version','schema_version',
    'description','focus_keyword','canonical','noindex'
  )){
    $p=$result.PSObject.Properties[$name]; if($p){ $safe[$name]=$p.Value }
  }
  if($result.data){
    $data=$result.data
    if(($data -is [System.Collections.IEnumerable]) -and -not($data -is [string]) -and -not($data -is [pscustomobject])){ $safe['data_count']=@($data).Count }
    else{ foreach($name in @('id','status','slug','title','name','sku','stock_status','stock_quantity','modified_gmt','link','permalink','description','short_description','attributes','images','categories','tags')){ $p=$data.PSObject.Properties[$name]; if($p){ $safe["data_$name"]=$p.Value } } }
  }
  $record['result']=$safe
}
Write-Result $record
if(-not $record.ok){ Fail "K20 Bridge v3 request failed with HTTP $status" }
Write-Host "K20_BRIDGE_V32_OK action=$action request_id=$($request.request_id)"
