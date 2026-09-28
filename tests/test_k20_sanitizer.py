import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, PngImagePlugin
import k20_sanitizer as s

class K20SanitizerTests(unittest.TestCase):
    def test_preserves_persian_half_space(self):
        raw = "می\u200cشود A\u200bB\u202e C\u00a0D\U000E0061"
        cleaned = s.sanitize_text(raw)
        self.assertEqual(cleaned, "می\u200cشود AB C D")
        self.assertEqual(sum(s.scan_text(cleaned).values()), 0)

    def test_recursive(self):
        payload = {"title":"خبر\u200b امروز","faq":[{"q":"آیا\u202e درست؟","a":"بله\u202fحتماً"}]}
        removed = s.sanitize_payload_inplace(payload)
        self.assertGreaterEqual(sum(removed.values()), 3)
        s.assert_clean(payload)

    def test_file(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.json"
            p.write_text(json.dumps({"content":"A\u200bB"},ensure_ascii=False),encoding="utf-8")
            r=s.sanitize_json_file(p)
            self.assertTrue(r["clean"])
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["content"],"AB")

    def test_image_metadata_strip_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "meta.png"
            meta = PngImagePlugin.PngInfo()
            meta.add_text("Comment", "generated-by-ai")
            meta.add_itxt("XML:com.adobe.xmp", "<x:xmpmeta>AI provenance</x:xmpmeta>")
            Image.new("RGB", (16, 16), "white").save(p, "PNG", pnginfo=meta)
            before = s.verify_image_file(p)
            self.assertFalse(before["clean"])
            result = s.sanitize_image_file(p)
            self.assertTrue(result["clean"])
            after = s.verify_image_file(p)
            self.assertTrue(after["clean"])

if __name__ == "__main__":
    unittest.main()
