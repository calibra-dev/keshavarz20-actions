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
  'media.read', 'media.update', 'media.webp_validate',
  'taxonomy.read', 'taxonomy.create', 'taxonomy.update',
  'phase16.audit',
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

function Invoke-MediaHead([string]$Uri, [bool]$PreferWebp = $false) {
  $h = @{}
  if ($PreferWebp) { $h['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8' }
  try {
    $r = Invoke-WebRequest -Uri $Uri -Method Head -Headers $h -MaximumRedirection 5 -TimeoutSec 60 -SkipHttpErrorCheck
    $ct = [string]$r.Headers['Content-Type']
    $clRaw = [string]$r.Headers['Content-Length']
    $cl = 0L
    if (-not [string]::IsNullOrWhiteSpace($clRaw)) { [void][long]::TryParse($clRaw, [ref]$cl) }
    return [ordered]@{ ok=([int]$r.StatusCode -ge 200 -and [int]$r.StatusCode -lt 400); status=[int]$r.StatusCode; content_type=$ct; content_length=$cl }
  } catch {
    return [ordered]@{ ok=$false; status=0; content_type=''; content_length=0; error=$_.Exception.Message }
  }
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
    $target = "$base/wp-json/wp/v2/$type/${id}?context=edit"
    $o = Invoke-K20 'GET' $target
    $result = [ordered]@{ id=$o.id; slug=$o.slug; status=$o.status; link=$o.link; modified_gmt=$o.modified_gmt; title=$o.title.raw; comment_status=$o.comment_status; ping_status=$o.ping_status }
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
  'media.webp_validate' {
    $ids = @($payload.ids | ForEach-Object { [int]$_ } | Where-Object { $_ -gt 0 } | Select-Object -Unique)
    if ($ids.Count -lt 1) { Fail 'payload.ids must contain at least one positive media id.' }
    if ($ids.Count -gt 500) { Fail 'media.webp_validate is capped at 500 ids per request.' }

    $items = New-Object System.Collections.Generic.List[object]
    foreach ($id in $ids) {
      try {
        $m = Invoke-K20 'GET' "$base/wp-json/wp/v2/media/$id?context=edit&_fields=id,source_url,mime_type,media_details,parent"
      } catch {
        $items.Add([pscustomobject][ordered]@{ id=$id; media_read_ok=$false; error=$_.Exception.Message })
        continue
      }
      $source = [string]$m.source_url
      $webpUrl = "$source.webp"
      $orig = Invoke-MediaHead $source $false
      $webp = Invoke-MediaHead $webpUrl $false
      $negotiated = Invoke-MediaHead $source $true
      $origBytes = [long]$orig.content_length
      $webpBytes = [long]$webp.content_length
      $savingPct = $null
      if ($origBytes -gt 0 -and $webpBytes -gt 0) { $savingPct = [math]::Round((1.0 - ($webpBytes / [double]$origBytes)) * 100.0, 2) }
      $webpExists = ($webp.ok -and ([string]$webp.content_type).ToLowerInvariant().Contains('image/webp'))
      $webpSmaller = ($webpExists -and $origBytes -gt 0 -and $webpBytes -gt 0 -and $webpBytes -lt $origBytes)
      $servedWebp = ($negotiated.ok -and ([string]$negotiated.content_type).ToLowerInvariant().Contains('image/webp'))
      $items.Add([pscustomobject][ordered]@{
        id=$id; media_read_ok=$true; mime_type=[string]$m.mime_type; parent=[int]$m.parent;
        width=$m.media_details.width; height=$m.media_details.height; source_url=$source;
        original_ok=[bool]$orig.ok; original_status=[int]$orig.status; original_bytes=$origBytes;
        webp_url=$webpUrl; webp_status=[int]$webp.status; webp_bytes=$webpBytes; webp_exists=[bool]$webpExists;
        webp_smaller=[bool]$webpSmaller; saving_pct=$savingPct; served_webp_with_accept=[bool]$servedWebp
      })
    }
    $good = @($items | Where-Object { $_.media_read_ok })
    $webpGood = @($good | Where-Object { $_.webp_exists })
    $smallerGood = @($good | Where-Object { $_.webp_smaller })
    $servedGood = @($good | Where-Object { $_.served_webp_with_accept })
    $origGood = @($good | Where-Object { $_.original_ok })
    $savings = @($good | Where-Object { $null -ne $_.saving_pct } | ForEach-Object { [double]$_.saving_pct })
    $avgSaving = $null
    if ($savings.Count -gt 0) { $avgSaving = [math]::Round(($savings | Measure-Object -Average).Average, 2) }
    $result = [ordered]@{
      requested=$ids.Count; media_reads_ok=$good.Count; originals_reachable=$origGood.Count;
      webp_exists=$webpGood.Count; webp_smaller=$smallerGood.Count; served_webp_with_accept=$servedGood.Count;
      average_saving_pct=$avgSaving; originals_deleted=$false;
      originals_policy='Keep originals for WordPress metadata, fallback, direct URLs, gallery/zoom, and rollback.';
      items=$items
    }
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
  'phase16.audit' {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("k20-phase16-" + [guid]::NewGuid().ToString("N") + ".json")
    try {
      & python scripts/k20_phase16_rest_link_graph.py $tmp
      if ($LASTEXITCODE -ne 0) { Fail "Phase 16 audit script failed with exit code $LASTEXITCODE" }
      if (-not (Test-Path -LiteralPath $tmp)) { Fail "Phase 16 audit did not produce a result file." }
      $audit = Get-Content -Raw -LiteralPath $tmp | ConvertFrom-Json -Depth 100
      $result = $audit
    } finally {
      if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    }
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
