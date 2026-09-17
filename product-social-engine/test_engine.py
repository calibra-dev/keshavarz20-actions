from pathlib import Path

from PIL import Image

import main


def product(pid, name="لوله آبیاری نمونه"):
    return {
        "id": pid,
        "name": name,
        "slug": f"p-{pid}",
        "permalink": f"https://keshavarz20.com/product/p-{pid}/",
        "summary": "محصول مناسب برای استفاده در سامانه‌های آبیاری و کاربردهای کشاورزی.",
        "description": "",
        "is_in_stock": True,
        "images": [{"src": "https://example.test/image.jpg"}],
        "categories": [{"name": "آبیاری"}],
    }


def test_choose_product_prefers_never_used():
    state = {"history": [{"product_id": 1, "published_at": "2026-09-17T00:00:00Z"}]}
    chosen = main.choose_product([product(1), product(2)], state, day_key="2026-09-18")
    assert chosen["id"] == 2


def test_choose_product_rotates_oldest_when_all_used():
    state = {"history": [
        {"product_id": 1, "published_at": "2026-09-10T00:00:00Z"},
        {"product_id": 2, "published_at": "2026-09-12T00:00:00Z"},
    ]}
    chosen = main.choose_product([product(1), product(2)], state, day_key="2026-09-18")
    assert chosen["id"] == 1


def test_caption_is_telegram_safe_and_has_url():
    p = product(3, name="شیر توپی دو اینچ")
    p["summary"] = "توضیح " * 300
    caption = main.make_caption(p)
    assert len(caption) <= 1000
    assert p["permalink"] in caption
    assert "موجود" in caption


def test_render_creative(tmp_path: Path):
    source = tmp_path / "src.png"
    output = tmp_path / "out.png"
    Image.new("RGB", (600, 600), "white").save(source)
    main.render_creative(product(4), source, output)
    assert output.exists()
    with Image.open(output) as generated:
        assert generated.size == (1080, 1350)


def test_load_state_recovers_from_invalid_json(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{bad", encoding="utf-8")
    state = main.load_state(state_file)
    assert state == {"version": 1, "history": []}
