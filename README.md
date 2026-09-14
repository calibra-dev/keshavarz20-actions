# keshavarz20-actions

Public GitHub Actions control plane for `keshavarz20.com`.

## Purpose

This repository contains only cloud-safe, reusable automation required to operate the public website without a personal computer or self-hosted runner.

The private repository `calibra-dev/keshavarz20-ops` remains the archive for historical evidence, local-runner tooling, backups, raw bridge queues/results, one-off batch artifacts, and anything that may contain sensitive operational data.

## Verified cloud path

`GitHub -> GitHub-hosted ubuntu runner -> WordPress/WooCommerce REST API -> keshavarz20.com`

The lifecycle workflow has been verified end-to-end with:

- create temporary draft product
- authenticated readback
- delete
- verify 404

No personal computer is required for this path.

## Required repository secrets

- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`

Do not commit credentials, tokens, application passwords, raw authenticated API responses, local bridge config, or backups to this public repository.

## Workflows

- `woocommerce-hosted-lifecycle.yml` - end-to-end WooCommerce write/read/delete verification.
- `k20-cloud-health.yml` - authenticated read-only WordPress/WooCommerce connectivity check.

## Migration policy

Only reusable and public-safe operational logic is migrated from `keshavarz20-ops`. Historical batch workflows, self-hosted runner paths, Windows scheduled-task configuration, bridge queue/result archives, backups, and diagnostic evidence remain private.

See `docs/MIGRATION-FROM-KESHAVARZ20-OPS.md` for details.
