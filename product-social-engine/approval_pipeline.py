from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageOps

import main as base

TEHRAN = ZoneInfo("Asia/Tehran")
PENDING_DIR = Path("product-social-engine/pending")
APPROVAL_DIR = Path("product-social-engine/approvals")
OUT_DIR = Path("product-social-engine/out")
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0").strip() or "v25.0"
TIMEOUT = 30


def tehran_now() -> datetime:
    return datetime.now(TEHRAN)


def resolve_date(value: str | None, *, tomorrow: bool = False) -> str:
    if value:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    day = tehran_now().date() + (timedelta(days=1) if tomorrow else timedelta())
    return day.isoformat()


def candidate_path(publish_date: str) -> Path:
    return PENDING_DIR / f"{publish_date}.json"


def approval_path(publish_date: str) -> Path:
    return APPROVAL_DIR / f"{publish_date}.json"


def make_candidate(product: dict[str, Any], publish_date: str) -> dict[str, Any]:
    candidate = {
        "schema_version": 1,
        "publish_date": publish_date,
        "generated_at": tehran_now().isoformat(),
        "product_id": int(product["id"]),
        "product_name": base.clean_html(str(product.get("name") or "")),
        "slug": str(product.get("slug") or ""),
        "category": base.category_name(product),
        "product_url": base.product_url(product),
        "source_image_url": str((product.get("images") or [{}])[0].get("src") or ""),
        "caption": base.make_caption(product),
        "targets": {
            "whatsapp": "08:45 Asia/Tehran",
            "telegram": "08:50 Asia/Tehran",
            "instagram_story": "08:55 Asia/Tehran",
        },
    }
    hashed = {k: v for k, v in candidate.items() if k != "generated_at"}
    canonical = json.dumps(hashed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    candidate["candidate_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return candidate


def save_candidate(candidate: dict[str, Any]) -> Path:
    path = candidate_path(str(candidate["publish_date"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_candidate(publish_date: str) -> dict[str, Any]:
    path = candidate_path(publish_date)
    if not path.exists():
        raise RuntimeError(f"No prepared candidate for {publish_date}")
    candidate = json.loads(path.read_text(encoding="utf-8"))
    if candidate.get("publish_date") != publish_date:
        raise RuntimeError("Candidate date mismatch")
    return candidate


def load_approval(publish_date: str) -> dict[str, Any] | None:
    path = approval_path(publish_date)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def approval_matches(candidate: dict[str, Any], approval: dict[str, Any] | None) -> bool:
    if not approval:
        return False
    return (
        approval.get("status") == "approved"
        and approval.get("publish_date") == candidate.get("publish_date")
        and int(approval.get("product_id", -1)) == int(candidate.get("product_id", -2))
        and approval.get("candidate_hash") == candidate.get("candidate_hash")
    )


def as_product(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate["product_id"],
        "name": candidate["product_name"],
        "slug": candidate["slug"],
        "permalink": candidate["product_url"],
        "images": [{"src": candidate["source_image_url"]}],
        "categories": [{"name": candidate["category"]}],
    }


def render_story(ad_path: Path, story_path: Path) -> None:
    canvas = Image.new("RGB", (1080, 1920), "#F4F1E8")
    with Image.open(ad_path) as img:
        fitted = ImageOps.contain(img.convert("RGB"), (1080, 1920), method=Image.Resampling.LANCZOS)
        canvas.paste(fitted, ((1080 - fitted.width) // 2, (1920 - fitted.height) // 2))
    story_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(story_path, "JPEG", quality=92, optimize=True)


def build_assets(candidate: dict[str, Any]) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = OUT_DIR / "source-product-image"
    ad = OUT_DIR / "daily-product-ad.png"
    story = OUT_DIR / "daily-product-story.jpg"
    base.download_image(str(candidate["source_image_url"]), source)
    base.render_creative(as_product(candidate), source, ad)
    render_story(ad, story)
    (OUT_DIR / "caption.txt").write_text(str(candidate["caption"]) + "\n", encoding="utf-8")
    return ad, story


def require_env(*names: str) -> dict[str, str]:
    values = {name: os.getenv(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Missing required secrets: " + ", ".join(missing))
    return values


def verify_product(candidate: dict[str, Any]) -> None:
    current = next(
        (p for p in base.fetch_products() if int(p.get("id", 0)) == int(candidate["product_id"])),
        None,
    )
    if current is None:
        raise RuntimeError("Approved product is no longer eligible; publication blocked")
    if base.product_url(current) != candidate["product_url"]:
        raise RuntimeError("Product URL changed after approval; publication blocked")


def upload_whatsapp_media(image_path: Path, phone_id: str, token: str) -> str:
    with image_path.open("rb") as handle:
        response = requests.post(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{phone_id}/media",
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": "image/png"},
            files={"file": (image_path.name, handle, "image/png")},
            timeout=TIMEOUT,
        )
    response.raise_for_status()
    media_id = str(response.json().get("id") or "")
    if not media_id:
        raise RuntimeError("WhatsApp media upload returned no media id")
    return media_id


def send_whatsapp(image_path: Path, caption: str) -> dict[str, Any]:
    env = require_env("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_GROUP_ID")
    media_id = upload_whatsapp_media(image_path, env["WHATSAPP_PHONE_NUMBER_ID"], env["WHATSAPP_ACCESS_TOKEN"])
    response = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{env['WHATSAPP_PHONE_NUMBER_ID']}/messages",
        headers={"Authorization": f"Bearer {env['WHATSAPP_ACCESS_TOKEN']}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "group",
            "to": env["WHATSAPP_GROUP_ID"],
            "type": "image",
            "image": {"id": media_id, "caption": caption},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("messages"):
        raise RuntimeError("WhatsApp returned no message id")
    return payload


def upload_story_to_wordpress(story_path: Path, candidate: dict[str, Any]) -> str:
    env = require_env("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD")
    endpoint = env["WP_BASE_URL"].rstrip("/") + "/wp-json/wp/v2/media"
    filename = f"k20-social-{candidate['publish_date']}-{candidate['product_id']}.jpg"
    with story_path.open("rb") as handle:
        response = requests.post(
            endpoint,
            auth=(env["WP_USERNAME"], env["WP_APP_PASSWORD"]),
            files={"file": (filename, handle, "image/jpeg")},
            data={"title": f"K20 social story {candidate['publish_date']}", "alt_text": candidate["product_name"]},
            timeout=TIMEOUT,
        )
    response.raise_for_status()
    url = str(response.json().get("source_url") or "")
    if not url.startswith("https://"):
        raise RuntimeError("WordPress media upload returned no public HTTPS URL")
    return url


def send_instagram_story(story_path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    env = require_env("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID")
    image_url = upload_story_to_wordpress(story_path, candidate)
    create = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{env['INSTAGRAM_USER_ID']}/media",
        data={"media_type": "STORIES", "image_url": image_url, "access_token": env["INSTAGRAM_ACCESS_TOKEN"]},
        timeout=TIMEOUT,
    )
    create.raise_for_status()
    container_id = str(create.json().get("id") or "")
    if not container_id:
        raise RuntimeError("Instagram returned no story container id")

    status = ""
    for _ in range(10):
        check = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}",
            params={"fields": "status_code,status", "access_token": env["INSTAGRAM_ACCESS_TOKEN"]},
            timeout=TIMEOUT,
        )
        check.raise_for_status()
        status = str(check.json().get("status_code") or "").upper()
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram story container failed: {status}")
        time.sleep(3)
    if status != "FINISHED":
        raise RuntimeError("Instagram story container did not finish in time")

    publish = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{env['INSTAGRAM_USER_ID']}/media_publish",
        data={"creation_id": container_id, "access_token": env["INSTAGRAM_ACCESS_TOKEN"]},
        timeout=TIMEOUT,
    )
    publish.raise_for_status()
    payload = publish.json()
    if not payload.get("id"):
        raise RuntimeError("Instagram publish returned no media id")
    return payload


def record_success(candidate: dict[str, Any], channel: str) -> None:
    state = base.load_state()
    history = state.setdefault("history", [])
    if any(
        item.get("publish_date") == candidate["publish_date"]
        and int(item.get("product_id", -1)) == int(candidate["product_id"])
        and item.get("channel") == channel
        for item in history
    ):
        return
    history.append({
        "product_id": int(candidate["product_id"]),
        "slug": candidate["slug"],
        "name": candidate["product_name"],
        "publish_date": candidate["publish_date"],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
    })
    state["history"] = history[-1500:]
    base.STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(data: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(publish_date: str | None) -> dict[str, Any]:
    date = resolve_date(publish_date, tomorrow=True)
    product = base.choose_product(base.fetch_products(), base.load_state(), day_key=date)
    candidate = make_candidate(product, date)
    path = save_candidate(candidate)
    ad, story = build_assets(candidate)
    result = {
        "ok": True,
        "status": "prepared_waiting_for_user_approval",
        "publish_date": date,
        "candidate_file": str(path),
        "candidate_hash": candidate["candidate_hash"],
        "product_id": candidate["product_id"],
        "product_name": candidate["product_name"],
        "product_url": candidate["product_url"],
        "caption": candidate["caption"],
        "ad_image": str(ad),
        "story_image": str(story),
    }
    write_summary(result)
    return result


def publish(channel: str, publish_date: str | None) -> dict[str, Any]:
    date = resolve_date(publish_date)
    candidate = load_candidate(date)
    if not approval_matches(candidate, load_approval(date)):
        result = {"ok": True, "status": "skipped_not_approved", "channel": channel, "publish_date": date}
        write_summary(result)
        return result

    verify_product(candidate)
    ad, story = build_assets(candidate)
    if channel == "whatsapp":
        platform = send_whatsapp(ad, candidate["caption"])
    elif channel == "telegram":
        platform = base.send_telegram(ad, candidate["caption"])
    elif channel == "instagram":
        platform = send_instagram_story(story, candidate)
    else:
        raise ValueError("Unsupported channel")

    record_success(candidate, channel)
    result = {
        "ok": True,
        "status": "published",
        "channel": channel,
        "publish_date": date,
        "product_id": candidate["product_id"],
        "product_name": candidate["product_name"],
        "product_url": candidate["product_url"],
        "platform_result": platform,
    }
    write_summary(result)
    return result


def status(publish_date: str | None) -> dict[str, Any]:
    date = resolve_date(publish_date)
    candidate_file = candidate_path(date)
    candidate = json.loads(candidate_file.read_text(encoding="utf-8")) if candidate_file.exists() else None
    approval = load_approval(date) if candidate else None
    return {
        "ok": True,
        "publish_date": date,
        "candidate_exists": bool(candidate),
        "approved": approval_matches(candidate, approval) if candidate else False,
        "candidate": candidate,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "status", "whatsapp", "telegram", "instagram"])
    parser.add_argument("--publish-date")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(args.publish_date)
        elif args.action == "status":
            result = status(args.publish_date)
        else:
            result = publish(args.action, args.publish_date)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "action": args.action, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
