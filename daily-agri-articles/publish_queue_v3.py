#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

# Load v2 so all SEO-God validation rules stay authoritative.
spec = importlib.util.spec_from_file_location("article_v2", ROOT / "publish_queue_v2.py")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
base = v2.base


class _DummySystem:
    @staticmethod
    def listMethods():
        # base.main only uses this as a capability gate. Actual writes below use REST.
        return ["wp.newPost", "wp.uploadFile", "wp.getPost"]


class _DummyServer:
    system = _DummySystem()


def rest_url(route: str) -> str:
    return f"{base.WP_BASE}/wp-json{route}"


def rest_request(method: str, route: str, **kwargs):
    kwargs.setdefault("auth", (base.WP_USER, base.WP_PASS))
    kwargs.setdefault("timeout", 45)
    r = base.SESSION.request(method, rest_url(route), **kwargs)
    if not r.ok:
        detail = ""
        try:
            body = r.json()
            detail = str(body.get("message") or body.get("code") or "")
        except Exception:
            detail = (r.text or "")[:300]
        raise base.QueuePublishError(
            f"WordPress REST {method} {route} failed: HTTP {r.status_code} {detail}".strip()
        )
    return r


def wp_rest_server():
    return _DummyServer()


def upload_wp_image_rest(server, path: Path, p: dict[str, Any], source: dict[str, Any]) -> int:
    del server
    filename = f"keshavarz20-article-{base.now_tehran().strftime('%Y%m%d-%H%M%S')}.webp"
    headers = {
        "Content-Type": "image/webp",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    r = rest_request("POST", "/wp/v2/media", data=path.read_bytes(), headers=headers, timeout=70)
    media_id = int(r.json()["id"])

    description = " | ".join(
        x for x in [
            source.get("title", ""), source.get("artist", ""),
            source.get("license", ""), source.get("original_url", "")
        ] if x
    )
    rest_request(
        "POST", f"/wp/v2/media/{media_id}",
        json={
            "title": p.get("image_title") or p["title"],
            "alt_text": p["alt_text"],
            "caption": "",
            "description": description,
        },
    )
    return media_id


def normalize_term(value: str) -> str:
    return base.normalize_fa(str(value or "").strip())


def ensure_tag_ids(tags: list[str]) -> list[int]:
    result: list[int] = []
    for tag in tags:
        name = str(tag).strip()
        if not name:
            continue
        r = rest_request("GET", "/wp/v2/tags", params={"search": name, "per_page": 100, "hide_empty": False})
        found = None
        for row in r.json():
            if normalize_term(row.get("name", "")) == normalize_term(name):
                found = int(row["id"])
                break
        if found is None:
            try:
                created = rest_request("POST", "/wp/v2/tags", json={"name": name}).json()
                found = int(created["id"])
            except base.QueuePublishError as exc:
                # A concurrent run may have created the term after our search.
                retry = rest_request("GET", "/wp/v2/tags", params={"search": name, "per_page": 100, "hide_empty": False})
                for row in retry.json():
                    if normalize_term(row.get("name", "")) == normalize_term(name):
                        found = int(row["id"])
                        break
                if found is None:
                    raise exc
        result.append(found)
    return result


def create_draft_rest(server, p: dict[str, Any], media_id: int, category_id: int, category_name: str, image_source: dict[str, Any]) -> int:
    del server, category_name, image_source
    tags = [str(x).strip() for x in p.get("tags", []) if str(x).strip()][:10]
    tag_ids = ensure_tag_ids(tags)

    # These Yoast keys are exposed by the site's authenticated posts REST schema.
    # Evidence/audit data remains durably stored in the committed queue JSON and
    # GitHub Actions artifacts; unregistered protected meta is never forced.
    meta = {
        "_yoast_wpseo_title": p["seo_title"],
        "_yoast_wpseo_metadesc": p["meta_description"],
        "_yoast_wpseo_focuskw": p["focus_keyphrase"],
    }
    payload = {
        "status": "draft",
        "title": p["title"],
        "slug": p["slug"],
        "excerpt": p["excerpt"],
        "content": p["content_html"],
        "featured_media": media_id,
        "categories": [category_id],
        "tags": tag_ids,
        "meta": meta,
        "comment_status": "open",
    }
    update_post_id = int(p.get("update_post_id") or 0)
    if update_post_id:
        existing = rest_request("GET", f"/wp/v2/posts/{update_post_id}", params={"context": "edit"}).json()
        if existing.get("type") != "post":
            raise base.QueuePublishError("update_post_id is not a normal WordPress post")
        r = rest_request("POST", f"/wp/v2/posts/{update_post_id}", json=payload, timeout=70)
        updated_id = int(r.json()["id"])
        if updated_id != update_post_id:
            raise base.QueuePublishError("WordPress updated an unexpected post id")
        return updated_id
    r = rest_request("POST", "/wp/v2/posts", json=payload, timeout=70)
    return int(r.json()["id"])


def verify_rest(server, post_id: int, category_id: int) -> dict[str, Any]:
    del server
    post = rest_request(
        "GET", f"/wp/v2/posts/{post_id}",
        params={"context": "edit"}, timeout=45,
    ).json()
    if post.get("status") != "draft" or post.get("type") != "post":
        raise base.QueuePublishError("Created item is not a normal WordPress post draft")
    if not int(post.get("featured_media") or 0):
        raise base.QueuePublishError("Created draft has no featured image")
    if category_id not in [int(x) for x in post.get("categories", [])]:
        raise base.QueuePublishError("Requested category is missing after write")

    meta = post.get("meta") or {}
    required = {
        "_yoast_wpseo_title": None,
        "_yoast_wpseo_metadesc": None,
        "_yoast_wpseo_focuskw": None,
    }
    missing = [k for k in required if not str(meta.get(k) or "").strip()]
    if missing:
        raise base.QueuePublishError(f"Required Yoast fields missing after REST write: {missing}")

    # Adapt REST shape to the fields used by base.save_result/main result handling.
    return {
        "post_id": post_id,
        "post_status": post.get("status"),
        "post_type": post.get("type"),
        "post_thumbnail": post.get("featured_media"),
        "link": post.get("link"),
    }


# Keep v2 validator and all base quality gates; swap only the WordPress transport.
base.wp_xmlrpc = wp_rest_server
base.upload_wp_image = upload_wp_image_rest
base.create_draft = create_draft_rest
base.verify = verify_rest

if __name__ == "__main__":
    base.main()
