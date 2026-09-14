function Build-RecommendationBlock($Target) {
  $sizes=@($Target.sizes_mm)
  $a=Convert-ToPersianDigits([string]$sizes[0])
  $kind=[string]$Target.kind

  if($kind -eq 'reducer'){
    $b=Convert-ToPersianDigits([string]$sizes[1])
    $heading="قطعات پیشنهادی برای تکمیل خط پلی‌اتیلن $a به $b میلی‌متر"
    $intro="این رابط تبدیل بین دو سایز $a و $b میلی‌متر قرار می‌گیرد. برای اینکه سفارش ناقص نماند، پیشنهادهای زیر بر اساس هر دو سمت اتصال و فقط از محصولات واقعی فروشگاه انتخاب شده‌اند. هر سمت را جداگانه با سایز درج‌شده روی لوله یا اتصال موجود تطبیق دهید."
    $beforeBuy="مبنا را سایز میلی‌متری هر دو سمت قرار دهید و دو طرف اتصال را جداگانه تطبیق دهید."
  } elseif($kind -eq 'male_thread') {
    $heading="لوازم پیشنهادی برای زانو پلی‌اتیلن یکسر نر $a میلی‌متر"
    $intro="در این مدل، یک سمت برای خط پلی‌اتیلن $a میلی‌متری است و سمت دیگر رزوه نر دارد. پیشنهادهای زیر فقط برای سمت پلی‌اتیلن و بر اساس محصولات واقعی هم‌سایز فروشگاه انتخاب شده‌اند؛ اندازه رزوه از روی سایز لوله حدس زده نشده است."
    $beforeBuy="سایز $a میلی‌متر را برای سمت لوله بررسی کنید و اندازه و نوع رزوه سمت نر را جداگانه با قطعه مقابل تطبیق دهید. عدد میلی‌متری لوله، به‌تنهایی اندازه رزوه را تعیین نمی‌کند."
  } elseif($kind -eq 'female_thread') {
    $heading="لوازم پیشنهادی برای زانو پلی‌اتیلن یکسر ماده $a میلی‌متر"
    $intro="در این مدل، یک سمت برای خط پلی‌اتیلن $a میلی‌متری است و سمت دیگر رزوه ماده دارد. پیشنهادهای زیر برای سمت پلی‌اتیلن و از محصولات واقعی هم‌سایز فروشگاه انتخاب شده‌اند. برای سمت رزوه، همان اندازه‌ای را ملاک قرار دهید که در عنوان محصول و روی اتصال مقابل درج شده است."
    $beforeBuy="سایز $a میلی‌متر را برای سمت لوله و سایز رزوه را برای سمت ماده به‌صورت مستقل کنترل کنید؛ این دو مشخصه را به‌جای یکدیگر استفاده نکنید."
  } else {
    $heading="قطعات پیشنهادی برای زانو پلی‌اتیلن $a میلی‌متر"
    $intro="این اتصال برای تغییر مسیر خط پلی‌اتیلن هم‌سایز $a میلی‌متری استفاده می‌شود. برای تکمیل همان شاخه، لوله و چند قطعه کاربردی هم‌سایز از محصولات واقعی فروشگاه در ادامه آمده‌اند."
    $beforeBuy="مبنای انتخاب را سایز میلی‌متری لوله پلی‌اتیلن قرار دهید و دو سر اتصال را با خط موجود تطبیق دهید."
  }

  $items=@()
  foreach($r in @($Target.proposed_products)){
    $s=Convert-ToPersianDigits([string]$r.side_mm)
    $label=switch([string]$r.family){
      'pipe'{"لوله پلی‌اتیلن $s میلی‌متر"}
      'coupling'{"رابط مستقیم پلی‌اتیلن $s میلی‌متر"}
      'endcap'{"درپوش انتهایی $s میلی‌متر"}
      'elbow'{"زانو $s میلی‌متر"}
      'tee'{"سه‌راه $s میلی‌متر"}
      'valve'{"شیر هم‌سایز $s میلی‌متر"}
      default{"اتصال $s میلی‌متر"}
    }
    $note=switch([string]$r.family){
      'pipe'{"برای ادامه سمت پلی‌اتیلن $s میلی‌متری."}
      'coupling'{'برای ادامه مستقیم بخش دیگری از همان خط.'}
      'endcap'{'برای بستن انتهای یک شاخه هم‌سایز.'}
      'elbow'{'برای تغییر مسیر بخش دیگری از همان خط.'}
      'tee'{'برای ایجاد انشعاب در همان سایز.'}
      'valve'{'برای کنترل جریان در یک بخش هم‌سایز؛ نوع اتصال دو سر شیر نیز باید جداگانه تطبیق داده شود.'}
      default{'برای تکمیل همان شاخه.'}
    }
    $name=[Net.WebUtility]::HtmlEncode([string]$r.name)
    $url=[Net.WebUtility]::HtmlEncode([string]$r.permalink)
    $items+=('<li style="margin:7px 0"><strong>{0}:</strong> <a style="color:#176b3a;font-weight:700" href="{1}">{2}</a> — {3}</li>' -f $label,$url,$name,$note)
  }

  $missing=@($Target.missing_pipe_sizes)
  $missingText=''
  if($missing.Count){
    $m=@($missing|ForEach-Object{Convert-ToPersianDigits([string]$_)})-join' و '
    $missingText="<p><strong>نکته:</strong> برای سایز $m میلی‌متر، لوله پلی‌اتیلن منتشرشده‌ای در دسته لوله‌های فروشگاه پیدا نشد؛ بنابراین لینک ساختگی یا سایز نامرتبط پیشنهاد نشده است.</p>"
  }

  $typeNote=''
  if($kind -in @('male_thread','female_thread')){
    $typeNote='<p><strong>نکته اتصال رزوه‌ای:</strong> پیشنهادهای این بخش به معنی سازگاری خودکار سمت رزوه با همه شیرها یا اتصالات هم‌سایز نیست؛ نوع رزوه و اندازه واقعی قطعه مقابل را جداگانه کنترل کنید.</p>'
  }

  $list=$items-join"`n"
  return @"
<h2 style="font-size:24px;line-height:1.8;color:#176b3a;margin:34px 0 14px;border-right:5px solid #5d9a68;padding-right:12px">$heading</h2>
<div style="background:#f7fbf8;border:1px solid #dbe8df;border-radius:16px;padding:17px;margin:15px 0">
<p>$intro</p>
<ul style="padding-right:22px;margin:10px 0">$list</ul>
$missingText
$typeNote
<p style="margin:12px 0 0"><strong>قبل از خرید:</strong> $beforeBuy</p>
</div>
"@
}
