import unittest
import k20_rtl_pro as rtl

class TestPersianRTLQuality(unittest.TestCase):
    def test_zwnj_mixed_tokens(self):
        text = "آبیاری می‌شود؛ لوله UV-120-A سایز ۲٫۵ اینچ"
        rtl.assert_public_text(text, field="title", require_persian=True)
        self.assertEqual(rtl.normalize_visible(text), text)
        self.assertIn("\u200c", rtl.normalize_visible(text))

    def test_safe_normalization(self):
        self.assertEqual(rtl.normalize_visible("كود يار UV-120-A"), "کود یار UV-120-A")

    def test_reject_bidi_and_corrupt_text(self):
        for text in ("تیتر\u202eشکسته", "آبیاری\u200bتیپ", "جایگزینی\ufffd"):
            with self.subTest(text=repr(text)), self.assertRaises(rtl.RTLQualityError):
                rtl.assert_public_text(text, field="title")

    def test_payload_does_not_change_identifiers(self):
        payload = {
            "title": "راهنمای آبیاری ۲۰۲۶", "slug": "uv-120-a",
            "content_html": "<p>آبیاری می‌شود و UV-120-A محفوظ است.</p>",
            "faq_items": [{"question": "چه زمانی؟", "answer": "پس از بررسی فشار."}],
        }
        result = rtl.audit_payload_text(payload)
        self.assertTrue(result["content_clean"])
        self.assertEqual(payload["slug"], "uv-120-a")
        self.assertIn("faq_items", result["verified_fields"])

    def test_pillow_raqm_if_available(self):
        try:
            from PIL import Image, ImageDraw, features
            if not features.check_feature("raqm"):
                self.skipTest("libraqm unavailable")
            font, _ = rtl.load_font(32, [
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf",
            ])
        except (ImportError, rtl.RTLQualityError):
            self.skipTest("Pillow or approved font unavailable")
        im = Image.new("RGB", (650, 140), "black")
        draw = ImageDraw.Draw(im)
        text = "کشاورز بیست، ۲٫۵ اینچ UV-120-A"
        self.assertGreater(rtl.text_width(draw, text, font), 0)
        rtl.draw_text(draw, (630, 20), text, font, anchor="ra", fill="white")
        self.assertTrue(im.getbbox())

if __name__ == "__main__":
    unittest.main()
