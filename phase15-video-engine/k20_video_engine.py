from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "phase15-video-engine"
OUT = ENGINE / "out"
TRANSCRIPTS = ROOT / "phase2" / "video-program" / "transcripts-fa.md"
SITE = os.getenv("K20_SITE_BASE_URL", "https://keshavarz20.com").rstrip("/")
STORE_API = f"{SITE}/wp-json/wc/store/v1/products"
TARGET_W, TARGET_H = 1080, 1920
FPS = 30

EPISODE_SEARCH = {
    1: "نوار تیپ", 2: "نوار تیپ", 3: "نوار تیپ", 4: "نوار تیپ",
    5: "فیلتر", 6: "نوار تیپ", 7: "لوله نخدار", 8: "لوله نخدار",
    9: "لوله نخدار", 10: "لوله نخدار", 11: "لوله پلی اتیلن",
    12: "اتصال پلی اتیلن", 13: "اتصال پلی اتیلن", 14: "فیلتر دیسکی",
    15: "فیلتر", 16: "فیلتر دیسکی", 17: "شیر", 18: "آبپاش",
    19: "آبیاری", 20: "آبیاری",
}


@dataclass
class Episode:
    number: int
    title: str
    hook: str
    body: str
    cta: str

    @property
    def narration(self) -> str:
        return " ".join(x.strip() for x in (self.hook, self.body, self.cta) if x.strip())


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def health() -> dict:
    checks = {
        "python": sys.version.split()[0],
        "ffmpeg": command_exists("ffmpeg"),
        "ffprobe": command_exists("ffprobe"),
        "nvidia_smi": command_exists("nvidia-smi"),
        "transcripts": TRANSCRIPTS.exists(),
        "out_writable": False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    probe = OUT / ".write-test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    checks["out_writable"] = True

    gpu = None
    if checks["nvidia_smi"]:
        try:
            gpu = run([
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ]).stdout.strip()
        except Exception as exc:
            gpu = f"ERROR: {exc}"
    checks["gpu"] = gpu
    checks["ok"] = all([
        checks["ffmpeg"], checks["ffprobe"], checks["transcripts"],
        checks["out_writable"], checks["nvidia_smi"],
    ])
    return checks


def parse_episodes(path: Path = TRANSCRIPTS) -> dict[int, Episode]:
    text = path.read_text(encoding="utf-8")
    header_re = re.compile(r"^##\s+(\d{2})\s+—\s+(.+)$", re.M)
    matches = list(header_re.finditer(text))
    episodes: dict[int, Episode] = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        number = int(match.group(1))
        title = match.group(2).strip()

        def field(label: str) -> str:
            m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", block)
            return m.group(1).strip() if m else ""

        episodes[number] = Episode(
            number=number,
            title=title,
            hook=field("هوک"),
            body=field("متن"),
            cta=field("CTA"),
        )
    return episodes


def resolve_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "tahoma.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def rtl(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def wrap_rtl(text: str, width: int = 38) -> list[str]:
    return [rtl(line) for line in textwrap.wrap(text, width=width, break_long_words=False)]


def store_products(search: str) -> list[dict]:
    response = requests.get(
        STORE_API,
        params={"search": search, "per_page": 12},
        timeout=30,
        headers={"User-Agent": "K20-Phase15-Video-Engine/1.0"},
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def choose_real_product_image(search: str) -> tuple[str, str, int]:
    products = store_products(search)
    for product in products:
        images = product.get("images") or []
        if not images:
            continue
        src = images[0].get("src")
        permalink = product.get("permalink")
        if src and permalink:
            return src, permalink, int(product["id"])
    raise RuntimeError(f"No real Keshavarz20 product image resolved for search={search!r}")


def download(url: str, dest: Path) -> None:
    r = requests.get(url, timeout=60, headers={"User-Agent": "K20-Phase15-Video-Engine/1.0"})
    r.raise_for_status()
    dest.write_bytes(r.content)


def make_poster(source: Path, ep: Episode, dest: Path) -> None:
    with Image.open(source).convert("RGB") as im:
        canvas = Image.new("RGB", (TARGET_W, TARGET_H), "white")
        im.thumbnail((TARGET_W - 120, 980))
        x = (TARGET_W - im.width) // 2
        y = 190
        canvas.paste(im, (x, y))

    draw = ImageDraw.Draw(canvas)
    title_font = resolve_font(54)
    hook_font = resolve_font(43)
    small_font = resolve_font(32)

    y = 60
    for line in wrap_rtl(ep.title, 30):
        bbox = draw.textbbox((0, 0), line, font=title_font)
        draw.text(((TARGET_W - (bbox[2]-bbox[0]))/2, y), line, font=title_font, fill="black")
        y += 68

    y = 1240
    for line in wrap_rtl(ep.hook, 42):
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        draw.text(((TARGET_W - (bbox[2]-bbox[0]))/2, y), line, font=hook_font, fill="black")
        y += 56

    brand = rtl("کشاورز بیست  |  keshavarz20.com")
    bbox = draw.textbbox((0, 0), brand, font=small_font)
    draw.text(((TARGET_W - (bbox[2]-bbox[0]))/2, 1820), brand, font=small_font, fill="black")
    canvas.save(dest, quality=92)


def synthesize_audio(text: str, dest: Path, voice: str = "fa-IR-FaridNeural") -> None:
    cmd = [sys.executable, "-m", "edge_tts", "--voice", voice, "--text", text, "--write-media", str(dest)]
    run(cmd)


def media_duration(path: Path) -> float:
    p = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ])
    return float(p.stdout.strip())


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(ep: Episode, duration: float, dest: Path) -> None:
    parts = [x for x in (ep.hook, ep.body, ep.cta) if x]
    weights = [max(1, len(x)) for x in parts]
    total = sum(weights)
    cursor = 0.0
    rows = []
    for idx, (part, weight) in enumerate(zip(parts, weights), start=1):
        end = duration if idx == len(parts) else cursor + duration * weight / total
        rows.append(f"{idx}\n{srt_time(cursor)} --> {srt_time(end)}\n{part}\n")
        cursor = end
    dest.write_text("\n".join(rows), encoding="utf-8-sig")


def render_video(poster: Path, audio: Path, dest: Path) -> None:
    duration = media_duration(audio)
    frames = max(1, int(math.ceil(duration * FPS)))
    vf = (
        f"scale={TARGET_W}:{TARGET_H},"
        f"zoompan=z='min(zoom+0.00035,1.06)':d={frames}:"
        f"s={TARGET_W}x{TARGET_H}:fps={FPS},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(poster), "-i", str(audio),
        "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
        str(dest),
    ]
    run(cmd)


def render_episode(number: int, voice: str = "fa-IR-FaridNeural") -> dict:
    episodes = parse_episodes()
    if number not in episodes:
        raise ValueError(f"Episode {number} not found")
    ep = episodes[number]
    search = EPISODE_SEARCH[number]

    episode_dir = OUT / f"episode-{number:02d}"
    episode_dir.mkdir(parents=True, exist_ok=True)

    image_url, product_url, product_id = choose_real_product_image(search)
    source = episode_dir / "source-product.jpg"
    poster = episode_dir / "thumbnail.jpg"
    audio = episode_dir / "narration.mp3"
    subtitle = episode_dir / "subtitles-fa.srt"
    video = episode_dir / "video.mp4"
    transcript = episode_dir / "transcript-fa.txt"
    metadata = episode_dir / "metadata.json"

    download(image_url, source)
    make_poster(source, ep, poster)
    synthesize_audio(ep.narration, audio, voice=voice)
    duration = media_duration(audio)
    if not 20 <= duration <= 120:
        raise RuntimeError(f"Narration duration {duration:.1f}s outside guardrail")
    make_srt(ep, duration, subtitle)
    render_video(poster, audio, video)
    transcript.write_text(ep.narration + "\n", encoding="utf-8")

    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    data = {
        "episode": number,
        "title": ep.title,
        "status": "rendered_local",
        "duration_seconds": round(media_duration(video), 3),
        "source_product_id": product_id,
        "source_product_url": product_url,
        "source_image_url": image_url,
        "video_sha256": digest,
        "video_file": video.name,
        "thumbnail_file": poster.name,
        "subtitle_file": subtitle.name,
        "transcript_file": transcript.name,
        "public_video_url": None,
        "public_thumbnail_url": None,
        "landing_page": None,
        "publication_date": None,
        "rendered_at_epoch": int(time.time()),
    }
    metadata.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def package_report(numbers: Iterable[int]) -> dict:
    rows = []
    for number in numbers:
        meta = OUT / f"episode-{number:02d}" / "metadata.json"
        if not meta.exists():
            rows.append({"episode": number, "status": "missing"})
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        video = meta.parent / data["video_file"]
        rows.append({
            "episode": number,
            "status": "ok" if video.exists() and video.stat().st_size > 0 else "broken",
            "duration_seconds": data.get("duration_seconds"),
            "video_sha256": data.get("video_sha256"),
        })
    report = {"episodes": rows, "ok": all(r["status"] == "ok" for r in rows)}
    (OUT / "package-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health")

    render_p = sub.add_parser("render")
    render_p.add_argument("--episode", type=int, required=True)
    render_p.add_argument("--voice", default="fa-IR-FaridNeural")

    batch_p = sub.add_parser("batch")
    batch_p.add_argument("--start", type=int, default=1)
    batch_p.add_argument("--end", type=int, default=20)
    batch_p.add_argument("--voice", default="fa-IR-FaridNeural")

    package_p = sub.add_parser("package")
    package_p.add_argument("--start", type=int, default=1)
    package_p.add_argument("--end", type=int, default=20)

    args = parser.parse_args()

    if args.cmd == "health":
        result = health()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 2

    if args.cmd == "render":
        print(json.dumps(render_episode(args.episode, args.voice), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "batch":
        if args.start < 1 or args.end > 20 or args.start > args.end:
            raise SystemExit("Batch range must be within 1..20")
        results = []
        failures = []
        for number in range(args.start, args.end + 1):
            try:
                results.append(render_episode(number, args.voice))
            except Exception as exc:
                failures.append({"episode": number, "error": str(exc)})
                print(f"EPISODE {number} FAILED: {exc}", file=sys.stderr)
        summary = {"rendered": [r["episode"] for r in results], "failures": failures}
        (OUT / "batch-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if failures else 0

    if args.cmd == "package":
        report = package_report(range(args.start, args.end + 1))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
