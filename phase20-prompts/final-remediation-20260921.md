# Keshavarz20 Phase 20 Final Remediation — 2026-09-21

## Mission
Close every Phase 20 accessibility defect that can be fixed through supported settings/content/UI mechanisms, while preserving IranKala protected theme code and site behavior.

## Verified defects
- Owl carousel dot buttons rendered without accessible names.
- site-logo anchors rendered without accessible names.
- image-only home/product/promo links rendered without accessible names.
- product image/lightbox links and some theme-generated product links can fail link-name.
- Existing server diagnostics show empty link names across home/product/guides.
- Lighthouse Phase 20 baseline: home 0.74, product 0.75, guides ~0.82-0.83.

## Safety hierarchy
1. Theme/Elementor/widget supported fields/settings.
2. Existing content/HTML attributes where safely editable.
3. Existing installed snippet mechanism only if already explicitly opted in and supported.
4. Do NOT edit IranKala protected PHP/ionCube files.
5. Do NOT install a new code-execution plugin solely for this task.
6. Do NOT inject arbitrary PHP/JS through DB/options/headers as a workaround.

## Execution
- Inspect active theme settings, Elementor/front-page content, widgets, existing snippet/plugin capabilities.
- Fix source-level accessible names wherever a supported editable field exists.
- If an issue is generated only by protected theme/Owl renderer and no supported source field exists, classify THEME_RENDERER_GUARD.
- Do not hide focusable controls or set aria-hidden on interactive elements merely to silence Lighthouse.
- Re-run the existing Phase 20 Lighthouse workflow and server semantic diagnostics after any safe mutations.
- Persist before/after evidence.
- Phase 20 may be marked PASS only if button-name/link-name failures are actually gone on all required targets.
- Otherwise mark PASS_GUARDED/POLICY_GUARD with exact residual selectors and no fabricated closure.

## Required evidence
- phase20-results/final-remediation-20260921.json
- phase25-results/final-release-gate-v10-20260921.json if Phase 20 state materially changes.
