# K20 Phase 15 Local Video Engine

GitHub-orchestrated Windows renderer for the 20 prepared Phase 15 educational videos.

## Architecture

ChatGPT -> GitHub Actions -> Windows self-hosted runner -> K20 renderer -> FFmpeg -> MP4/SRT/thumbnail/metadata -> GitHub artifact.

The engine keeps orchestration in GitHub while render work runs on a labelled Windows machine. No credential is committed to the repository.

## Source of truth

- `phase2/video-program/transcripts-fa.md`
- `phase2/video-program/assets.json`
- `phase2/video-program/manifest.json`
- `seo-god1/phase15-visual-video-final-gate-20260921.json`

There are **20 prepared episodes**. Phase 15 is the phase number, not a 15-video count.

## Policy

- 1080x1920, H.264/AAC, 30 fps.
- 30-90 second target.
- Real Keshavarz20 product media only.
- Never fabricate technical values, reviews, price, stock, certification, warranty or field results.
- If suitable real media cannot be resolved, block the episode instead of inventing evidence.
- Every successful render produces MP4, SRT, transcript, thumbnail and metadata JSON.
- Product appearance must not be generatively altered.
- Rendering and publishing are separate operations.

## Runner labels

Render jobs require:

`self-hosted, Windows, X64, k20-video, gpu`

## One-time setup

1. Repository Settings -> Actions -> Runners -> New self-hosted runner -> Windows x64.
2. Use a dedicated folder such as `C:\k20-runner`.
3. Run GitHub's displayed runner download/configuration commands. Never paste the registration token into chat or the repo.
4. Add custom labels `k20-video` and `gpu`.
5. Run `phase15-video-engine/setup-windows.ps1` from PowerShell.
6. Start the runner interactively for the first health test. Install as a Windows service only after health passes.

## Local test

```powershell
python -m pip install -r phase15-video-engine/requirements.txt
python phase15-video-engine/k20_video_engine.py health
python phase15-video-engine/k20_video_engine.py render --episode 1
```
