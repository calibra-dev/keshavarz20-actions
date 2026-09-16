import json
import runpy

_original_loads = json.loads


def tolerant_loads(value, *args, **kwargs):
    try:
        return _original_loads(value, *args, **kwargs)
    except Exception:
        text = value.decode('utf-8', 'replace') if isinstance(value, (bytes, bytearray)) else str(value)
        return {'_non_json_response': True, 'raw': text[:500]}


json.loads = tolerant_loads
runpy.run_path('scripts/k20_sitewide_media_inventory.py', run_name='__main__')
