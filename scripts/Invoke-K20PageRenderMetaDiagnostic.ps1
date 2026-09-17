param(
  [Parameter(Mandatory=$true)][string]$RequestPath,
  [Parameter(Mandatory=$true)][string]$OutputPath
)

$ErrorActionPreference='Stop'
if(-not(Test-Path -LiteralPath $RequestPath)){ throw "Request file not found: $RequestPath" }

$base=$env:WP_BASE_URL
$user=$env:WP_USERNAME
$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){
  throw 'Required WordPress secrets are missing.'
}
$base=$base.TrimEnd('/')
$req=Get-Content -Raw -LiteralPath $RequestPath | ConvertFrom-Json -Depth 100
$ids=@($req.page_ids | ForEach-Object {[int]$_} | Where-Object {$_ -gt 0} | Select-Object -Unique)
if($ids.Count -lt 1){ throw 'At least one positive page id is required.' }
if($ids.Count -gt 10){ throw 'Diagnostic is capped at 10 page ids.' }

$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"))
$headers=@{Authorization="Basic $auth";Accept='application/json'}

function Invoke-JsonGet([string]$Path){
  Invoke-RestMethod -Uri ($base+'/'+$Path.TrimStart('/')) -Method GET -Headers $headers -TimeoutSec 120
}

function Get-Sha256([string]$Text){
  if($null -eq $Text){ return '' }
  $sha=[Security.Cryptography.SHA256]::Create()
  try {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Text)
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
  } finally { $sha.Dispose() }
}

function To-CompactJson($Value){
  if($null -eq $Value){ return '' }
  try { return ($Value | ConvertTo-Json -Depth 100 -Compress) } catch { return [string]$Value }
}

function Get-MetaValue($Meta,[string]$Name){
  if($null -eq $Meta){ return $null }
  $prop=$Meta.PSObject.Properties[$Name]
  if($null -ne $prop){ return $prop.Value }
  return $null
}

function Summarize-ElementorData($RawValue){
  if($null -eq $RawValue){
    return [ordered]@{present=$false;serialized_length=0;sha256='';json_parse_ok=$false;top_level_count=0;widget_type_counts=@{};template_id_refs=@();raw_if_small=''}
  }
  $text=if($RawValue -is [string]){[string]$RawValue}else{To-CompactJson $RawValue}
  $parseOk=$false
  $topCount=0
  if(-not [string]::IsNullOrWhiteSpace($text)){
    try {
      $parsed=$text | ConvertFrom-Json -Depth 100
      $parseOk=$true
      if(($parsed -is [System.Collections.IEnumerable]) -and -not($parsed -is [string])){ $topCount=@($parsed).Count } else { $topCount=1 }
    } catch {}
  }

  $widgetCounts=[ordered]@{}
  foreach($m in [regex]::Matches($text,'(?i)"widgetType"\s*:\s*"([^"]+)"')){
    $name=$m.Groups[1].Value
    if($widgetCounts.Contains($name)){ $widgetCounts[$name]=[int]$widgetCounts[$name]+1 } else { $widgetCounts[$name]=1 }
  }
  $refSet=New-Object System.Collections.Generic.HashSet[int]
  foreach($m in [regex]::Matches($text,'(?i)"(?:template_id|templateId|post_id|postId)"\s*:\s*"?(\d+)"?')){
    $n=0
    if([int]::TryParse($m.Groups[1].Value,[ref]$n) -and $n -gt 0){ [void]$refSet.Add($n) }
  }

  return [ordered]@{
    present=$true
    serialized_length=$text.Length
    sha256=(Get-Sha256 $text)
    json_parse_ok=$parseOk
    top_level_count=$topCount
    widget_type_counts=$widgetCounts
    template_id_refs=@($refSet | Sort-Object)
    raw_if_small=if($text.Length -le 5000){$text}else{''}
  }
}

$rows=@()
foreach($id in $ids){
  $item=[ordered]@{id=$id}

  try {
    $single=Invoke-JsonGet "wp-json/wp/v2/pages/${id}?context=edit&_fields=id,slug,status,link,parent,template,title,content,meta"
    $item.single_endpoint=[ordered]@{ok=$true;returned_id=[int]$single.id;slug=[string]$single.slug;status=[string]$single.status}
  } catch {
    $item.single_endpoint=[ordered]@{ok=$false;error=$_.Exception.Message}
  }

  try {
    $rowsRaw=Invoke-JsonGet "wp-json/wp/v2/pages?context=edit&include=${id}&per_page=1&_fields=id,slug,status,link,parent,template,title,content,meta"
    $p=@($rowsRaw | Where-Object {$null-ne $_ -and $_.id}) | Select-Object -First 1
    if($null -eq $p){ throw "Collection lookup returned no page for id $id" }

    $meta=$p.meta
    $metaNames=@()
    if($null-ne$meta){ $metaNames=@($meta.PSObject.Properties.Name) }
    $editMode=Get-MetaValue $meta '_elementor_edit_mode'
    $templateType=Get-MetaValue $meta '_elementor_template_type'
    $conditions=Get-MetaValue $meta '_elementor_conditions'
    $pageSettings=Get-MetaValue $meta '_elementor_page_settings'
    $elementorData=Get-MetaValue $meta '_elementor_data'

    $raw=[string]$p.content.raw
    $rendered=[string]$p.content.rendered
    $item.collection=[ordered]@{
      ok=$true
      id=[int]$p.id
      slug=[string]$p.slug
      status=[string]$p.status
      link=[string]$p.link
      parent=[int]$p.parent
      template=[string]$p.template
      title=[string]$p.title.raw
      content_raw_length=$raw.Length
      content_rendered_length=$rendered.Length
      meta_keys=@($metaNames)
      elementor_edit_mode=(To-CompactJson $editMode)
      elementor_template_type=(To-CompactJson $templateType)
      elementor_conditions=(To-CompactJson $conditions)
      elementor_page_settings=(To-CompactJson $pageSettings)
      elementor_data=(Summarize-ElementorData $elementorData)
    }
  } catch {
    $item.collection=[ordered]@{ok=$false;error=$_.Exception.Message}
  }
  $rows+=,[pscustomobject]$item
}

$record=[ordered]@{
  ok=$true
  mode='read-only'
  executed_at_utc=[DateTime]::UtcNow.ToString('o')
  page_ids=@($ids)
  pages=@($rows)
}
$dir=Split-Path -Parent $OutputPath
if($dir-and-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}
$record|ConvertTo-Json -Depth 100|Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host "PAGE_RENDER_META_OK pages=$($rows.Count)"
