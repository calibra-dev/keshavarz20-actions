from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("WP_BASE_URL", "https://example.invalid")
os.environ.setdefault("WP_USERNAME", "test")
os.environ.setdefault("WP_APP_PASSWORD", "test")

spec = importlib.util.spec_from_file_location("k20_product_core_retry_test", ROOT / "product-engine" / "core.py")
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class BridgeReadRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_bridge = core.bridge
        self.original_sleep = core.time.sleep
        core.time.sleep = lambda _seconds: None

    def tearDown(self) -> None:
        core.bridge = self.original_bridge
        core.time.sleep = self.original_sleep

    def test_get_retries_transient_bridge_500_then_succeeds(self) -> None:
        calls = []
        def fake_bridge(action: str, **fields):
            calls.append((action, fields))
            if len(calls) < 3:
                raise RuntimeError("Bridge failure action=rest.proxy http=500 code=internal_server_error")
            return {"result": {"data": {"id": 135126}}}
        core.bridge = fake_bridge
        self.assertEqual(core.rest("GET", "/wc/v3/products/135126"), {"id": 135126})
        self.assertEqual(len(calls), 3)

    def test_seo_read_retries_transient_500(self) -> None:
        calls = []
        def fake_bridge(action: str, **fields):
            calls.append((action, fields))
            if len(calls) == 1:
                raise RuntimeError("Bridge failure action=seo.read http=500 code=internal_server_error")
            return {"result": {"id": 135126}}
        core.bridge = fake_bridge
        self.assertEqual(core.seo_read(135126), {"id": 135126})
        self.assertEqual(len(calls), 2)

    def test_get_does_not_retry_nontransient_4xx(self) -> None:
        calls = []
        def fake_bridge(action: str, **fields):
            calls.append((action, fields))
            raise RuntimeError("Bridge failure action=rest.proxy http=404 code=not_found")
        core.bridge = fake_bridge
        with self.assertRaises(RuntimeError):
            core.rest("GET", "/wc/v3/products/135126")
        self.assertEqual(len(calls), 1)

    def test_put_never_retries_even_on_500(self) -> None:
        calls = []
        def fake_bridge(action: str, **fields):
            calls.append((action, fields))
            raise RuntimeError("Bridge failure action=rest.proxy http=500 code=internal_server_error")
        core.bridge = fake_bridge
        with self.assertRaises(RuntimeError):
            core.rest("PUT", "/wc/v3/products/135126", payload={"description": "x"})
        self.assertEqual(len(calls), 1)

    def test_transport_exception_is_retryable_for_reads(self) -> None:
        calls = []
        def fake_bridge(action: str, **fields):
            calls.append((action, fields))
            if len(calls) == 1:
                raise core.requests.Timeout("temporary timeout")
            return {"result": {"data": {"id": 135126}}}
        core.bridge = fake_bridge
        self.assertEqual(core.rest("GET", "/wc/v3/products/135126"), {"id": 135126})
        self.assertEqual(len(calls), 2)

    def test_producer_live_read_has_bounded_read_only_retry(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "k20-product-producer-live-read.yml").read_text(encoding="utf-8")
        self.assertIn("function Invoke-BridgeReadWithRetry", workflow)
        self.assertIn("for ($attempt = 1; $attempt -le 4; $attempt++)", workflow)
        self.assertIn("HTTP\\s+(429|5\\d\\d)", workflow)
        self.assertIn('Invoke-BridgeReadWithRetry -RequestPath "$productReq.clean"', workflow)
        self.assertIn('Invoke-BridgeReadWithRetry -RequestPath "$seoReq.clean"', workflow)

    def test_publisher_avoids_redundant_terminal_product_read(self) -> None:
        source = (ROOT / "product-engine" / "publish_queue.py").read_text(encoding="utf-8")
        self.assertIn('result["after_media"]=media_snapshot(after)', source)
        self.assertNotIn('result["after_media"]=media_snapshot(product_read(pid))', source)
        self.assertIn("partial_publish_retry_after_transient_readback", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
