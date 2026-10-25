"""Offline adversarial tests of the live-response validator; no site request."""
import contextlib, copy, io, json, os, runpy, urllib.request
from pathlib import Path
from unittest.mock import patch

provinces = [{"code":f"IR-{i:02d}","orders":0,"revenue":0,"city_count":0,"cities":[]} for i in range(1,32)]
provinces[0].update(orders=2,revenue=200,city_count=1,cities=[{"name":"شیراز","orders":2,"revenue":200}])
fixture={"section":"regional","ok":True,"source":"fixture","data":{"available":True,"provinces":provinces,"total_orders":4,"mapped_revenue":200,"total_revenue":350,"unmatched":{"count":1,"revenue":50},"external":{"count":1,"revenue":100}}}

def validate(payload):
    with patch.dict(os.environ,{"WP_BASE_URL":"https://example.invalid","WP_USERNAME":"fixture","WP_APP_PASSWORD":"fixture"}), patch.object(urllib.request,"urlopen",return_value=io.BytesIO(json.dumps(payload).encode())), contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(str(Path(__file__).with_name('calibra-1817-live-regional-readonly.py')),run_name='__main__')

validate(fixture)
print('FIXTURE_VALID_WITH_UNMATCHED_EXTERNAL_PASS')
blank=copy.deepcopy(fixture); blank['data']['provinces'][0].update(city_count=0,cities=[])
validate(blank)
print('FIXTURE_EMPTY_CITY_REMAINS_IN_PROVINCE_TOTAL_PASS')
cases=[
 ('national money',lambda d:d.update(total_revenue=351),'REGIONAL_NATIONAL_REVENUE_MISMATCH'),
 ('mapped money',lambda d:d.update(mapped_revenue=201),'REGIONAL_MAPPED_REVENUE_MISMATCH'),
 ('national orders',lambda d:d.update(total_orders=5),'REGIONAL_NATIONAL_ORDER_BALANCE_MISMATCH'),
 ('city money',lambda d:d['provinces'][0]['cities'][0].update(revenue=199),'REGIONAL_CITY_PROVINCE_REVENUE_MISMATCH'),
 ('city orders',lambda d:d['provinces'][0]['cities'][0].update(orders=3),'REGIONAL_CITY_ORDERS_GREATER_THAN_PROVINCE'),
 ('zero orders',lambda d:d['provinces'][0]['cities'][0].update(orders=0),'REGIONAL_CITY_WITH_NO_ORDERS'),
 ('duplicate province',lambda d:d['provinces'][1].update(code='IR-01'),'REGIONAL_PROVINCE_CODES_DUPLICATED'),
 ('NaN national',lambda d:d.update(total_revenue=float('nan')),'REGIONAL_NONFINITE_NATIONAL_REVENUE'),
 ('NaN city',lambda d:d['provinces'][0]['cities'][0].update(revenue=float('nan')),'REGIONAL_NONFINITE_CITY_REVENUE'),
]
for label,mutate,expected in cases:
    payload=copy.deepcopy(fixture); mutate(payload['data'])
    try:
        validate(payload)
    except SystemExit as error:
        assert str(error)==expected,(label,error,expected)
    else:
        raise AssertionError('Validator accepted '+label)
    print('CORRUPT_FIXTURE_REJECTED: '+label)
print('REGIONAL_VALIDATOR_2_POSITIVE_9_NEGATIVE_PASS')
