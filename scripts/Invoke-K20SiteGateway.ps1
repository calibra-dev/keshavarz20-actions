param(
  [Parameter(Mandatory = $true)][string]$RequestPath,
  [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw $Message }
function To-Hash($Object) { return @{} + $Object }

if (-not (Test-Path -LiteralPath $RequestPath)) { Fail "Request file not found: $RequestPath" }

$base = $env:WP_BASE_URL
$user = $env:WP_USERNAME
$pass = $env:WP_APP_PASSWORD
if ([string]::IsNullOrWhiteSpace($base) -or [string]::IsNullOrWhiteSpace($user) -or [string]::IsNullOrWhiteSpace($pass)) {
  Fail 'Required WordPress secrets are missing.'
}
$base = $base.TrimEnd('/')

$request = Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
if (-not $request.action) { Fail 'Missing action.' }
$action = [string]$request.action
$payload = if ($request.payload) { $request.payload } else { [pscustomobject]@{} }

$allowedActions = @(
  'product.read', 'product.update', 'product.create_draft', 'product.stock', 'product.content',
  'post.read', 'post.update', 'post.create_draft',
  'page.read', 'page.update', 'page.create_draft',
  'media.read', 'media.update',
  'taxonomy.read', 'taxonomy.create', 'taxonomy.update',
  'bridge.health'
)
if ($allowedActions -notcontains $action) { Fail "Action is not allowed: $action" }

$forbiddenNames = @(
  'price','regular_price','sale_price','date_on_sale_from','date_on_sale_to','discount','discount_type',
  'coupon','coupon_code','payment_method','payment_method_title','tax_status','tax_class','password',
  'application_password','token','secret','api_key','consumer_key','consumer_secret','role','roles',
  'capability','capabilities','user_id','customer_id'
)

function Assert-SafeObject($Value, [string]$Path = 'payload') {
  if ($null -eq $Value) { return }
  if ($Value -is [System.Collections.IDictionary]) {
    foreach ($key in $Value.Keys) {
      $name = ([string]$key).ToLowerInvariant()
      if ($forbiddenNames -contains $name) { Fail "Forbidden key at ${Path}: $key" }
      Assert-SafeObject $Value[$key] "$Path.$key"
    }
    return
  }
  if ($Value -is [pscustomobject]) {
    foreach ($p in $Value.PSObject.Properties) {
      $name = $p.Name.ToLowerInvariant()
      if ($forbiddenNames -contains $name) { Fail "Forbidden key at ${Path}: $($p.Name)" }
      Assert-SafeObject $p.Value "$Path.$($p.Name)"
    }
    return
  }
  if (($Value -is [System.Collections.IEnumerable]) -and -not ($Value -is [string])) {
    $i = 0
    foreach ($item in $Value) { Assert-SafeObject $item "$Path[$i]"; $i++ }
  }
}
Assert-SafeObject $payload

$authText = "$user`:$pass"
$authValue = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($authText))
$headers = @{ Authorization = "Basic $authValue"; Accept = 'application/json' }

function Invoke-K20([string]$Method, [string]$Uri, $Body = $null) {
  $args = @{ Uri = $Uri; Method = $Method; Headers = $headers; TimeoutSec = 180 }
  if ($null -ne $Body) {
    $args.ContentType = 'application/json; charset=utf-8'
    $args.Body = ($Body | ConvertTo-Json -Depth 100 -Compress)
  }
  return Invoke-RestMethod @args
}

function Require-Id() {
  $id = [int]$request.id
  if ($id -lt 1) { Fail 'A positive id is required.' }
  return $id
}

function Select-Allowed($Source, [string[]]$Allowed) {
  $out = [ordered]@{}
  if ($null -eq $Source) { return $out }
  foreach ($name in $Allowed) {
    $prop = $Source.PSObject.Properties[$name]
    if ($null -ne $prop) { $out[$name] = $prop.Value }
  }
  return $out
}

$result = $null
$target = $null
$method = 'GET'

switch ($action) {
  'product.read' {
    $id = Require-Id
    $target = "$base/wp-json/wc/v3/products/$id"
    $p = Invoke-K20 'GET' $target
    $result = [ordered]@{
      id = $p.id; name = $p.name; slug = $p.slug; status = $p.status; sku = $p.sku;
      permalink = $p.permalink; stock_status = $p.stock_status; stock_quantity = $p.stock_quantity;
      manage_stock = $p.manage_stock; categories = $p.categories; tags = $p.tags; images = $p.images;
      modified_gmt = $p.date_modified_gmt
    }
  }
  'product.content' {
    $id = Require-Id
    $body = Select-Allowed $payload @('name','slug','description','short_description','status')
    if ($body.Count -eq 0) { Fail 'No allowed product content fields supplied.' }
    $target = "$base/wp-json/wc/v3/products/$id"; $method = 'PUT'
    $p = Invoke-K20 'PUT' $target $body
    $result = [ordered]@{ id=$p.id; name=$p.name; slug=$p.slug; status=$p.status; modified_gmt=$p.date_modified_gmt }
  }
  'product.stock' {
    $id = Require-Id
    $body = Select-Allowed $payload @('manage_stock','stock_quantity','stock_status','backorders','sold_individually')
    if ($body.Count -eq 0) { Fail 'No allowed stock fields supplied.' }
    $target = "$base/wp-json/wc/v3/products/$id"; $method = 'PUT'
    $p = Invoke-K20 'PUT' $target $body
    $result = [ordered]@{ id=$p.id; stock_status=$p.stock_status; stock_quantity=$p.stock_quantity; manage_stock=$p.manage_stock; modified_gmt=$p.date_modified_gmt }
  }
  'product.update' {
    $id = Require-Id
    $body = Select-Allowed $payload @(
      'name','slug','description','short_description','status','sku','featured','catalog_visibility',
      'manage_stock','stock_quantity','stock_status','backorders','sold_individually','weight','dimensions',
      'shipping_class','reviews_allowed','purchase_note','menu_order','categories','tags','images','attributes',
      'default_attributes','grouped_products','external_url','button_text'
    )
    if ($body.Count -eq 0) { Fail 'No allowed product fields supplied.' }
    $target = "$base/wp-json/wc/v3/products/$id"; $method = 'PUT'
    $p = Invoke-K20 'PUT' $target $body
    $result = [ordered]@{ id=$p.id; name=$p.name; slug=$p.slug; status=$p.status; stock_status=$p.stock_status; stock_quantity=$p.stock_quantity; modified_gmt=$p.date_modified_gmt }
  }
  'product.create_draft' {
    $body = Select-Allowed $payload @(
      'name','slug','description','short_description','sku','featured','catalog_visibility','manage_stock',
      'stock_quantity','stock_status','backorders','sold_individually','weight','dimensions','shipping_class',
      'reviews_allowed','purchase_note','menu_order','categories','tags','images','attributes','default_attributes',
      'grouped_products','external_url','button_text','type'
    )
    if (-not $body.Contains('name') -or [string]::IsNullOrWhiteSpace([string]$body['name'])) { Fail 'Product name is required.' }
    $body['status'] = 'draft'
    $target = "$base/wp-json/wc/v3/products"; $method = 'POST'
    $p = Invoke-K20 'POST' $target $body
    $result = [ordered]@{ id=$p.id; name=$p.name; slug=$p.slug; status=$p.status; sku=$p.sku; created_gmt=$p.date_created_gmt }
  }
  { $_ -in @('post.read','page.read') } {
    $id = Require-Id
    $type = if ($action.StartsWith('post.')) { 'posts' } else { 'pages' }
    $target = "$base/wp-json/wp/v2/$type/$id?context=edit"
    $o = Invoke-K20 'GET' $target
    $result = [ordered]@{ id=$o.id; slug=$o.slug; status=$o.status; link=$o.link; modified_gmt=$o.modified_gmt; title=$o.title.raw }
  }
  { $_ -in @('post.update','page.update') } {
    $id = Require-Id
    $type = if ($action.StartsWith('post.')) { 'posts' } else { 'pages' }
    $allowed = @('title','content','excerpt','slug','status','featured_media','comment_status','ping_status','menu_order','template')
    if ($type -eq 'posts') { $allowed += @('categories','tags') }
    $body = Select-Allowed $payload $allowed
    if ($body.Count -eq 0) { Fail 'No allowed content fields supplied.' }
    $target = "$base/wp-json/wp/v2/$type/$id"; $method = 'POST'
    $o = Invoke-K20 'POST' $target $body
    $result = [ordered]@{ id=$o.id; slug=$o.slug; status=$o.status; link=$o.link; modified_gmt=$o.modified_gmt }
  }
  { $_ -in @('post.create_draft','page.create_draft') } {
    $type = if ($action.StartsWith('post.')) { 'posts' } else { 'pages' }
    $allowed = @('title','content','excerpt','slug','featured_media','comment_status','ping_status','menu_order','template')
    if ($type -eq 'posts') { $allowed += @('categories','tags') }
    $body = Select-Allowed $payload $allowed
    if (-not $body.Contains('title')) { Fail 'Title is required.' }
    $body['status'] = 'draft'
    $target = "$base/wp-json/wp/v2/$type"; $method = 'POST'
    $o = Invoke-K20 'POST' $target $body
    $result = [ordered]@{ id=$o.id; slug=$o.slug; status=$o.status; link=$o.link; created_gmt=$o.date_gmt }
  }
  'media.read' {
    $id = Require-Id
    $target = "$base/wp-json/wp/v2/media/$id?context=edit"
    $m = Invoke-K20 'GET' $target
    $result = [ordered]@{ id=$m.id; slug=$m.slug; status=$m.status; source_url=$m.source_url; alt_text=$m.alt_text; title=$m.title.raw; modified_gmt=$m.modified_gmt }
  }
  'media.update' {
    $id = Require-Id
    $body = Select-Allowed $payload @('title','caption','description','alt_text','slug')
    if ($body.Count -eq 0) { Fail 'No allowed media fields supplied.' }
    $target = "$base/wp-json/wp/v2/media/$id"; $method = 'POST'
    $m = Invoke-K20 'POST' $target $body
    $result = [ordered]@{ id=$m.id; slug=$m.slug; source_url=$m.source_url; alt_text=$m.alt_text; modified_gmt=$m.modified_gmt }
  }
  { $_ -in @('taxonomy.read','taxonomy.create','taxonomy.update') } {
    $tax = [string]$request.taxonomy
    $routes = @{ category='wp/v2/categories'; tag='wp/v2/tags'; product_cat='wc/v3/products/categories'; product_tag='wc/v3/products/tags' }
    if (-not $routes.ContainsKey($tax)) { Fail "Taxonomy is not allowed: $tax" }
    $route = $routes[$tax]
    if ($action -eq 'taxonomy.read') {
      $id = Require-Id; $target = "$base/wp-json/$route/$id"; $t = Invoke-K20 'GET' $target
    } elseif ($action -eq 'taxonomy.create') {
      $body = Select-Allowed $payload @('name','slug','description','parent','display','image')
      if (-not $body.Contains('name')) { Fail 'Term name is required.' }
      $target = "$base/wp-json/$route"; $method='POST'; $t = Invoke-K20 'POST' $target $body
    } else {
      $id = Require-Id; $body = Select-Allowed $payload @('name','slug','description','parent','display','image')
      if ($body.Count -eq 0) { Fail 'No allowed taxonomy fields supplied.' }
      $target = "$base/wp-json/$route/$id"; $method='POST'; $t = Invoke-K20 'POST' $target $body
    }
    $result = [ordered]@{ id=$t.id; name=$t.name; slug=$t.slug; parent=$t.parent }
  }
  'bridge.health' {
    $target = "$base/wp-json/keshavarz20-ops/v2/health"
    $b = Invoke-K20 'GET' $target
    $result = [ordered]@{ status=$b.status; plugin=$b.plugin; version=$b.version; auth=$b.auth; https=$b.https }
  }
}

$record = [ordered]@{
  ok = $true
  request = [System.IO.Path]::GetFileName($RequestPath)
  action = $action
  method = $method
  executed_at_utc = [DateTime]::UtcNow.ToString('o')
  result = $result
}

$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$record | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "K20_GATEWAY_OK action=$action output=$OutputPath"
