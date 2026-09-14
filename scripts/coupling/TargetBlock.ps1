function Get-CouplingSizes([string]$Name) {
  $s = Normalize-InchText $Name
  $pair = [regex]::Match($s,'(?<!\d)(?<a>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:x|X|×|\*)\s*(?<b>16|20|25|32|40|50|63|75|90|110|125|160|200)(?!\d)')
  if ($pair.Success) {
    return @([int]$pair.Groups['a'].Value,[int]$pair.Groups['b'].Value)
  }
  $one = Get-NominalSizeMm $Name
  if ($null -ne $one) { return @([int]$one) }
  return @()
}

function Is-StaleProduct($Product) {
  return ([string]$Product.permalink -match '__trashed|_trashed' -or [string]$Product.slug -match '__trashed|_trashed')
}

function Get-CouplingFamily($Product,[int]$TargetCategoryId,[int]$PipeCategoryId) {
  if (Test-CategoryId $Product $PipeCategoryId) { return 'pipe' }
  $name = Normalize-Digits ([string]$Product.name)
  if ($name -match 'تبدیل') { return $null }
  if (Test-CategoryId $Product $TargetCategoryId) { return 'coupling' }
  if ($name -match 'درپوش') { return 'endcap' }
  if ($name -match 'زانویی|زانو') { return 'elbow' }
  if ($name -match 'سه\s*راه|سه‌راه') { return 'tee' }
  if ($name -match 'شیر') { return 'valve' }
  return $null
}

function Pick-Candidate($Products,[int]$Size,[string]$Family,[int]$TargetCategoryId,[int]$PipeCategoryId,[int]$ExcludeId) {
  $rows = @()
  foreach ($candidate in $Products) {
    if ([int]$candidate.id -eq $ExcludeId) { continue }
    if ([string]$candidate.catalog_visibility -eq 'hidden') { continue }
    if (Is-StaleProduct $candidate) { continue }
    $candidateSize = Get-NominalSizeMm ([string]$candidate.name)
    if ($null -eq $candidateSize -or [int]$candidateSize -ne $Size) { continue }
    $candidateFamily = Get-CouplingFamily $candidate $TargetCategoryId $PipeCategoryId
    if ($candidateFamily -ne $Family) { continue }
    $rows += $candidate
  }
  $rows = @($rows | Sort-Object @{Expression={if ([string]$_.stock_status -eq 'instock') {0} else {1}}},id)
  if ($rows.Count -gt 0) { return $rows[0] }
  return $null
}

function To-RelatedRow($Product,[string]$Family,[int]$Side) {
  if ($null -eq $Product) { return $null }
  return [pscustomobject][ordered]@{
    id = [int]$Product.id
    name = [string]$Product.name
    permalink = [string]$Product.permalink
    family = $Family
    side_mm = $Side
    stock_status = [string]$Product.stock_status
  }
}

$pipeCatalog = @()
foreach ($product in $products) {
  if (Test-CategoryId $product $pipeCategoryId) {
    $pipeCatalog += [pscustomobject][ordered]@{
      id = [int]$product.id
      name = [string]$product.name
      size_mm = Get-NominalSizeMm ([string]$product.name)
      permalink = [string]$product.permalink
      stock_status = [string]$product.stock_status
    }
  }
}

$targets = @()
$ambiguous = @()
foreach ($product in $products) {
  if (-not (Test-CategoryId $product $targetCategoryId)) { continue }

  $sizes = @(Get-CouplingSizes ([string]$product.name))
  $sizes = @($sizes | Select-Object -Unique)
  if ($sizes.Count -lt 1 -or $sizes.Count -gt 2) {
    $ambiguous += [pscustomobject][ordered]@{id=[int]$product.id;name=[string]$product.name;sizes_mm=@($sizes)}
    continue
  }

  $kind = if ($sizes.Count -eq 2 -or [string]$product.name -match 'تبدیل') { 'reducer' } else { 'equal' }
  if ($kind -eq 'reducer' -and $sizes.Count -ne 2) {
    $ambiguous += [pscustomobject][ordered]@{id=[int]$product.id;name=[string]$product.name;sizes_mm=@($sizes)}
    continue
  }

  $selected = @()
  $missingPipeSizes = @()
  foreach ($sizeValue in $sizes) {
    $size = [int]$sizeValue
    $pipe = Pick-Candidate $products $size 'pipe' $targetCategoryId $pipeCategoryId ([int]$product.id)
    if ($null -ne $pipe) { $selected += To-RelatedRow $pipe 'pipe' $size }
    else { $missingPipeSizes += $size }
  }

  if ($kind -eq 'equal') {
    $size = [int]$sizes[0]
    foreach ($family in @('endcap','elbow','tee','valve')) {
      if ($selected.Count -ge $maxRelated) { break }
      $candidate = Pick-Candidate $products $size $family $targetCategoryId $pipeCategoryId ([int]$product.id)
      if ($null -ne $candidate) { $selected += To-RelatedRow $candidate $family $size }
    }
  } else {
    foreach ($sizeValue in $sizes) {
      if ($selected.Count -ge $maxRelated) { break }
      $size = [int]$sizeValue
      $candidate = Pick-Candidate $products $size 'coupling' $targetCategoryId $pipeCategoryId ([int]$product.id)
      if ($null -ne $candidate) { $selected += To-RelatedRow $candidate 'coupling' $size }
    }
    foreach ($family in @('endcap','elbow')) {
      foreach ($sizeValue in $sizes) {
        if ($selected.Count -ge $maxRelated) { break }
        $size = [int]$sizeValue
        $candidate = Pick-Candidate $products $size $family $targetCategoryId $pipeCategoryId ([int]$product.id)
        if ($null -ne $candidate) { $selected += To-RelatedRow $candidate $family $size }
      }
    }
  }

  $selected = @($selected | Where-Object {$null -ne $_} | Select-Object -First $maxRelated)
  $bounds = Get-RecommendationBounds ([string]$product.description)
  $targets += [pscustomobject][ordered]@{
    id = [int]$product.id
    name = [string]$product.name
    kind = $kind
    sizes_mm = @($sizes)
    size_mm = [int]$sizes[0]
    existing_recommendation_block = ($null -ne $bounds)
    same_size_pipe_count = @($selected | Where-Object {$_.family -eq 'pipe'}).Count
    missing_pipe_sizes = @($missingPipeSizes)
    proposed_products = @($selected)
  }
}

$unparsed = @($ambiguous)
$missingPipe = @($targets | Where-Object {@($_.missing_pipe_sizes).Count -gt 0})
$empty = @($targets | Where-Object {@($_.proposed_products).Count -lt 1})
if ($mode -eq 'apply_description' -and $unparsed.Count -gt 0) { Fail "Refusing apply: ambiguous IDs $((@($unparsed.id) -join ','))" }
if ($mode -eq 'apply_description' -and $empty.Count -gt 0) { Fail "Refusing apply: empty recommendations for IDs $((@($empty.id) -join ','))" }
