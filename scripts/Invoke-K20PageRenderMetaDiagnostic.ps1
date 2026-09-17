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

function Summarize-ElementorData($RawValue){
  $text=''
  if($null -eq $RawValue){
    return [ordered]@{present=$false;serialized_length=0;sha256='';json_parse_ok=$false;top_level_count=0;node_count=0;widget_type_counts=@{};template_id_refs=@()}
  }
  if($RawValue -is [string]){ $text=[string]$RawValue } else { $text=To-CompactJson $RawValue }
  if([string]::IsNullOrWhiteSpace($text)){
    return [ordered]@{present=$true;serialized_length=0;sha256=(Get-Sha256 $text);json_parse_ok=$false;top_level_count=0;node_count=0;widget_type_counts=@{};template_id_refs=@()}
  }

  $parsed=$null
  $parseOk=$false
  try { $parsed=$text | ConvertFrom-Json -Depth 100; $parseOk=$true } catch {}
  $widgetCounts=@{}
  $templateRefs=New-Object System.Collections.Generic.HashSet[int]
  $nodeCount=0

  function Walk($Node){
    if($null -eq $Node){ return }
    if($Node -is [pscustomobject]){
      $script:nodeCount++
      $wt=$Node.PSObject.Properties['widgetType']
      if($wt -and -not [string]::IsNullOrWhiteSpace([string]$wt.Value)){
        $name=[string]$wt.Value
        if($script:widgetCounts.ContainsKey($name)){ $script:widgetCounts[$name]++ } else { $script:widgetCounts[$name]=1 }
      }
      foreach($propName in @('template_id','templateId','post_id','postId')){
        $p=$Node.PSObject.Properties[$propName]
        if($p){
          $n=0
          if([int]::TryParse([string]$p.Value,[ref]$n) -and $n -gt 0){ [void]$script:templateRefs.Add($n) }
        }
      }
      foreach($p in $Node.PSObject.Properties){ Walk $p.Value }
      return
    }
    if(($Node -is [System.Collections.IEnumerable]) -and -not($Node -is [string])){
      foreach($item in $Node){ Walk $item }
    }
  }

  if($parseOk){ Walk $parsed }
  $topCount=0
  if($parseOk){
    if(($parsed -is [System.Collections.IEnumerable]) -and -not($parsed -is [string])){ $topCount=@($parsed).Count } else { $topCount=1 }
  }
  return [ordered]@{
    present=$true
    serialized_length=$text.Length
    sha256=(Get-Sha256 $text)
    json_parse_ok=$parseOk
    top_level_count=$topCount
    node_count=$nodeCount
    widget_type_counts=$widgetCounts
    template_id_refs=@($templateRefs | Sort-Object)
  }
}

$rows=@()
foreach($id in $ids){
  $item=[ordered]@{id=$id}

  try {
    $single=Invoke-JsonGet "wp-json/wp/v2/pages/$id?context=edit&_fields=id,slug,status,link,parent,template,title,content,meta"
    $item.single_endpoint=[ordered]@{ok=$true;returned_id=[int]$single.id;slug=[string]$single.slug;status=[string]$single.status}
  } catch {
    $item.single_endpoint=[ordered]@{ok=$false;error=$_.Exception.Message}
  }

  try {
    $rowsRaw=Invoke-JsonGet "wp-json/wp/v2/pages?context=edit&include=$id&per_page=1&_fields=id,slug,status,link,parent,template,title,content,meta"
    $p=@($rowsRaw | Where-Object {$null-ne $_ -and $_.id}) | Select-Object -First 1
    if($null -eq $p){ throw "Collection lookup returned no page for id $id" }

    $meta=$p.meta
    $metaNames=@()
    if($null-ne$meta){ $metaNames=@($meta.PSObject.Properties.Name) }
    function MetaVal([string]$Name){
      if($null-eq$meta){ return $null }
      $prop=$meta.PSObject.Properties[$Name]
      if($prop){ return $prop.Value }
      return $null
    }

    $editMode=MetaVal '_elementor_edit_mode'
    $templateType=MetaVal '_elementor_template_type'
    $conditions=MetaVal '_elementor_conditions'
    $pageSettings=MetaVal '_elementor_page_settings'
    $elementorData=MetaVal '_elementor_data'

    $item.collection=[ordered]@{
      ok=$true
      id=[int]$p.id
      slug=[string]$p.slug
      status=[string]$p.status
      link=[string]$p.link
      parent=[int]$p.parent
      template=[string]$p.template
      title=[string]$p.title.raw
      content_raw_length=([string]$p.content.raw).Length
      content_rendered_length=([string]$p.content.rendered).Length
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
