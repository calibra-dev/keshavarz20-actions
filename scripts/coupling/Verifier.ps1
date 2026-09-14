function Test-RecommendationReadback([string]$Html,$Target) {
  $bounds = Get-RecommendationBounds $Html
  if ($null -eq $bounds) { return [pscustomobject]@{ok=$false;reason='block_missing'} }

  $block = $Html.Substring([int]$bounds.start,[int]$bounds.end-[int]$bounds.start)
  foreach ($related in @($Target.proposed_products)) {
    if ($block.IndexOf([string]$related.permalink,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return [pscustomobject]@{ok=$false;reason="missing_link_$([int]$related.id)"}
    }
  }
  if ($block -match '__trashed|_trashed') { return [pscustomobject]@{ok=$false;reason='stale_link'} }

  $links = @([regex]::Matches($block,'<a\b[^>]*href=["''][^"'']+["''][^>]*>',[Text.RegularExpressions.RegexOptions]::IgnoreCase))
  if ($links.Count -ne @($Target.proposed_products).Count) { return [pscustomobject]@{ok=$false;reason='link_count_mismatch'} }

  foreach ($size in @($Target.sizes_mm)) {
    $sizeFa = Convert-ToPersianDigits ([string]$size)
    if ($block.IndexOf($sizeFa,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return [pscustomobject]@{ok=$false;reason="size_copy_missing_$size"}
    }
  }
  return [pscustomobject]@{ok=$true;reason='ok'}
}
