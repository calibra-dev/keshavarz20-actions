function Fail([string]$Message){throw $Message}
$base=$env:WP_BASE_URL;$user=$env:WP_USERNAME;$pass=$env:WP_APP_PASSWORD
if([string]::IsNullOrWhiteSpace($base)-or[string]::IsNullOrWhiteSpace($user)-or[string]::IsNullOrWhiteSpace($pass)){Fail 'Required WordPress secrets are missing.'}
$base=$base.TrimEnd('/')
$auth=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$user`:$pass"));$headers=@{Authorization="Basic $auth";Accept='application/json'}
function Invoke-K20([string]$Method,[string]$Path,$Body=$null){$a=@{Uri=$base+'/'+$Path.TrimStart('/');Method=$Method;Headers=$headers;TimeoutSec=180};if($null-ne$Body){$a.ContentType='application/json; charset=utf-8';$a.Body=($Body|ConvertTo-Json -Depth 100 -Compress)};Invoke-RestMethod @a}
function Get-AllProducts(){
  $all=@();for($page=1;$page-le100;$page++){$response=Invoke-K20 'GET' "wp-json/wc/v3/products?per_page=100&page=$page&status=publish&orderby=id&order=asc";$items=@();foreach($item in $response){$items+=$item};if($items.Count-eq0){break};foreach($item in $items){$all+=$item};if($items.Count-lt100){break}};return $all
}
function Normalize-Digits([string]$Text){if($null-eq$Text){return ''};$s=$Text;$f=@('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹','٠','١','٢','٣','٤','٥','٦','٧','٨','٩');$t=@('0','1','2','3','4','5','6','7','8','9','0','1','2','3','4','5','6','7','8','9');for($i=0;$i-lt$f.Count;$i++){$s=$s.Replace($f[$i],$t[$i])};return $s.Replace('‌',' ').Replace('٫','.').Replace('٬',',')}
function Normalize-InchText([string]$Text){
  $s=Normalize-Digits $Text;$s=$s.Replace('½',' 1/2').Replace('¼',' 1/4').Replace('¾',' 3/4')
  $s=[regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\.|\s)\s*1\s*/\s*2(?!\d)',{param($m);(([double]$m.Groups['w'].Value)+.5).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)})
  $s=[regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\.|\s)\s*1\s*/\s*4(?!\d)',{param($m);(([double]$m.Groups['w'].Value)+.25).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)})
  $s=[regex]::Replace($s,'(?<!\d)(?<w>\d+)\s*(?:و|\.|\s)\s*3\s*/\s*4(?!\d)',{param($m);(([double]$m.Groups['w'].Value)+.75).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture)})
  $s=[regex]::Replace($s,'(?<!\d)3\s*/\s*4(?!\d)','0.75');$s=[regex]::Replace($s,'(?<!\d)1\s*/\s*2(?!\d)','0.5');$s=[regex]::Replace($s,'(?<!\d)1\s*/\s*4(?!\d)','0.25');return $s
}
function Convert-ToPersianDigits([string]$Text){$s=[string]$Text;$to=@('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹');for($i=0;$i-lt10;$i++){$s=$s.Replace([string]$i,$to[$i])};return $s}
$inchToMm=@{'0.5'=20;'0.75'=25;'1'=32;'1.25'=40;'1.5'=50;'2'=63;'2.5'=75;'3'=90;'4'=110;'4.5'=125;'6'=160}
function Get-NominalSizeMm([string]$Name){$s=Normalize-InchText $Name;$pair=[regex]::Match($s,'(?<!\d)(?<a>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:x|X|×|\*)\s*(?<b>16|20|25|32|40|50|63|75|90|110|125|160|200)(?!\d)');if($pair.Success-and[int]$pair.Groups['a'].Value-ne[int]$pair.Groups['b'].Value){return $null};$v=@();foreach($m in[regex]::Matches($s,'(?<!\d)(?<mm>16|20|25|32|40|50|63|75|90|110|125|160|200)\s*(?:میلی\s*متر|میلیمتر|mm\b)',[Text.RegularExpressions.RegexOptions]::IgnoreCase)){$v+=[int]$m.Groups['mm'].Value};$v=@($v|Sort-Object -Unique);if($v.Count-eq1){return[int]$v[0]};if($v.Count-gt1){return $null};$m=[regex]::Match($s,'(?<!\d)(?<i>\d+(?:\.\d+)?)\s*(?:اینچ|inch|in\b|"|″)',[Text.RegularExpressions.RegexOptions]::IgnoreCase);if($m.Success){$k=([double]$m.Groups['i'].Value).ToString('0.##',[Globalization.CultureInfo]::InvariantCulture);if($inchToMm.ContainsKey($k)){return[int]$inchToMm[$k]}};return $null}
function Test-CategoryId($Product,[int]$CategoryId){foreach($c in @($Product.categories)){if([int]$c.id-eq$CategoryId){return $true}};return $false}
