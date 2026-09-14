# Migration from keshavarz20-ops

Source: `calibra-dev/keshavarz20-ops` (private)
Target: `calibra-dev/keshavarz20-actions` (public)

## Goal

Move the reusable cloud execution layer needed for `keshavarz20.com` into a public repository so standard GitHub-hosted runners can be used without keeping a personal computer online.

## Migrated / represented here

1. WordPress/WooCommerce authentication contract using repository secrets:
   - `WP_BASE_URL`
   - `WP_USERNAME`
   - `WP_APP_PASSWORD`
2. GitHub-hosted runner execution on Ubuntu.
3. PowerShell REST execution pattern used by the working private-repo workflows.
4. Verified WooCommerce lifecycle test: create -> readback -> delete -> 404.
5. Read-only authenticated health check.
6. Runtime/tooling assumptions needed in cloud jobs: PowerShell (`pwsh`), Git, curl, and jq; workflows verify these before use when relevant.
7. Security boundary: no credentials or authenticated response bodies are stored in the public repository.

## Intentionally NOT copied from the private repository

These items are not required for the cloud control plane or are unsafe/noisy to publish:

- `bridge-v3-queue`, `bridge-v3-results`, `bridge-v2-results`, raw request/result archives.
- article/batch result folders, QA result folders, evidence folders, backups, snapshots, and one-off trigger files.
- historical one-off workflows tied to specific product IDs, batch numbers, dates, or completed incidents.
- Windows-only self-hosted runner configuration and local paths such as `C:\actions-runner`.
- Scheduled Task / Bridge V3 local agent configuration under `C:\ProgramData\Keshavarz20Bridge`.
- tokens, passwords, app passwords, private configs, local logs, or any secret material.

## Important architecture change

Private historical model:

`GitHub -> self-hosted Windows runner -> local Bridge/REST -> WordPress`

Current cloud model:

`GitHub public repo -> GitHub-hosted Ubuntu runner -> WordPress/WooCommerce REST -> keshavarz20.com`

The current model was verified successfully on 2026-09-14 with a real temporary WooCommerce product that was created, read back, deleted, and confirmed absent with HTTP 404.

## Runtime dependencies

The migrated workflows avoid custom local software. They use standard GitHub-hosted Ubuntu tooling and PowerShell Core. No local Windows runner, v2ray client, Scheduled Task, or local Bridge agent is required for the verified WooCommerce REST path.

## Remaining private-only capability

The private repo may still be used as an archive and fallback for historical Bridge-specific operations that return sensitive payloads. Such payloads must not be copied into this public repository or printed into public workflow logs.
