import json
from pathlib import Path

from PIL import Image

import approval_pipeline as pipe


def product(pid: int):
    return {
        "id": pid,
        "name": "شیر توپی دو اینچ",
        "slug": f"p-{pid}",
        "permalink": f"https://keshavarz20.com/product/p-{pid}/",
        "summary": "توضیح واقعی محصول",
        "description": "",
        "is_in_stock": True,
        "images": [{"src": "https://example.test/image.jpg"}],
        "categories": [{"name": "آبیاری"}],
    }


def test_candidate_contains_direct_link_and_stable_hash(monkeypatch):
    class FakeNow:
        def isoformat(self):
            return "2026-09-18T23:00:00+03:30"

    monkeypatch.setattr(pipe, "tehran_now", lambda: FakeNow())
    a = pipe.make_candidate(product(1), "2026-09-19")
    b = pipe.make_candidate(product(1), "2026-09-19")
    assert a["candidate_hash"] == b["candidate_hash"]
    assert a["product_url"] in a["caption"]


def test_approval_requires_exact_date_product_and_hash():
    candidate = pipe.make_candidate(product(2), "2026-09-19")
    approval = {
        "status": "approved",
        "publish_date": "2026-09-19",
        "product_id": 2,
        "candidate_hash": candidate["candidate_hash"],
    }
    assert pipe.approval_matches(candidate, approval)
    assert not pipe.approval_matches(candidate, dict(approval, candidate_hash="wrong"))


def test_story_output_is_9_by_16(tmp_path: Path):
    ad = tmp_path / "ad.png"
    story = tmp_path / "story.jpg"
    Image.new("RGB", (1080, 1350), "white").save(ad)
    pipe.render_story(ad, story)
    with Image.open(story) as image:
        assert image.size == (1080, 1920)
        assert image.format == "JPEG"


def test_unapproved_publish_never_calls_platform(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pipe, "PENDING_DIR", tmp_path / "pending")
    monkeypatch.setattr(pipe, "APPROVAL_DIR", tmp_path / "approvals")
    monkeypatch.setattr(pipe, "OUT_DIR", tmp_path / "out")
    candidate = pipe.make_candidate(product(3), "2026-09-19")
    pipe.save_candidate(candidate)
    monkeypatch.setattr(pipe, "verify_product", lambda candidate: (_ for _ in ()).throw(AssertionError("must not verify")))
    result = pipe.publish("telegram", "2026-09-19")
    assert result["status"] == "skipped_not_approved"
