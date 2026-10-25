# K20 Persistent Docker QA Lab

This directory is the **durable test environment definition** for Calibra, K20 plugins,
WordPress/WooCommerce, and future projects. It is intentionally independent of
production WordPress data and secrets.

## Persistence model

GitHub-hosted Actions runners are **ephemeral**: containers, volumes and service
processes cannot be left running when a job finishes. What persists is:

- this version-controlled Compose stack, scripts, assertions and workflow;
- Buildx layer caches on GitHub Actions;
- the prebuilt toolbox Docker image in GitHub Container Registry:
  `ghcr.io/calibra-dev/k20-qa-toolbox:stable`, published only after the
  main-branch baseline tests pass;
- a SHA-tagged image for reproducing an exact toolbox build.

To keep a **24/7 running container/database**, a separate always-on self-hosted
server and runner must be explicitly provisioned; GitHub Actions alone does not
provide that infrastructure.

## Installed capabilities

- MariaDB 10.11 with a fresh isolated WordPress test database.
- WordPress + WP-CLI on selectable PHP 8.1 / 8.3 / 8.4 containers.
- Real WooCommerce install and HPOS/Legacy order-storage checks.
- Node.js 22, Python 3, Composer 2, Git, curl, jq, zip/unzip, ShellCheck.
- Playwright 1.56.1 with Chromium, desktop (1366px) and mobile (390px)
  screenshot and page-error smoke checks.
- Optional **real** plugin ZIP install / reinstall / old-version to new-version
  upgrade when both exact release archives are supplied.
- SHA-256 validation of release ZIP inputs. The QA lab never guesses or
  reconstructs a missing historical release.

## Quick start in GitHub

Open **Actions → K20 Reusable Docker QA Lab → Run workflow** (default branch).
Choose PHP and Chromium. The default **Reuse published toolbox** option pulls
the retained GHCR image instead of rebuilding Playwright/PHP/Node; if the
registry pull fails, the workflow safely falls back to building from the pinned
Dockerfile. Repository push validations always build the candidate source and
publish updated stable + immutable SHA tags only after QA passes.

Without a plugin ZIP, this verifies the lab itself on both Legacy and HPOS
WooCommerce storage modes.

For a specific plugin install/upgrade, supply the Action **artifact ID**
containing exactly one installable ZIP and the ZIP's original SHA-256; optional
previous-version artifact and SHA-256 are necessary for a genuine upgrade.
Artifacts must belong to this repository; never put production credentials,
customer orders or site database dumps in fixtures.

The workflow can also be called by other Actions workflows with:
`uses: ./.github/workflows/k20-reusable-docker-qa.yml`.

## Run on a trusted local Docker host

From the repository root:

```bash
mkdir -p qa/docker/fixtures qa/docker/artifacts
docker compose -f qa/docker/compose.yml build toolbox
bash qa/docker/scripts/run.sh legacy
bash qa/docker/scripts/run.sh hpos
```

Set `QA_PHP_VERSION=8.1|8.3|8.4` to vary WordPress/PHP compatibility;
set `QA_ENABLE_BROWSER=0` to skip browser tests. Tests use a local-only
web binding at `http://127.0.0.1:18080`. Plugins for manual tests can be
placed at `qa/docker/fixtures/plugin-under-test.zip`, with an optional
`previous-plugin.zip` for genuine upgrade testing.

The default behavior is `docker compose down --volumes` after each scenario.
Do not disable isolation on shared GitHub runners. A local operator can set
`QA_KEEP_VOLUMES=1` for investigative work and later clean up explicitly.

## Test boundaries and evidence

Passing a baseline smoke test does **not** certify every plugin.
It also does not cover visual pixel diffs of a plugin dashboard, security
penetration tests, license-service behavior, real production traffic or
historical upgrades unless matching real release ZIPs were supplied.
Project-specific suites should be run on top of this lab.

Browser screenshots are retained as **short-lived GitHub Actions artifacts**;
never store sensitive pages in test snapshots. Production operations are
intentionally excluded. Artifacts and fixtures are gitignored.
