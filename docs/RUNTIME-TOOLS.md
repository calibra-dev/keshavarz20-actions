# Runtime tools

The public cloud workflows are designed to run on GitHub-hosted `ubuntu-latest` and avoid dependence on software installed on a personal Windows computer.

Required/verified command-line tools:

- PowerShell Core (`pwsh`)
- Git
- curl
- jq

The reusable REST helper is `scripts/Invoke-K20Rest.ps1`.

## No longer required for the verified cloud WooCommerce path

- `C:\actions-runner`
- Windows self-hosted GitHub runner
- local Bridge Scheduled Task
- `C:\ProgramData\Keshavarz20Bridge`
- local proxy/VPN client for GitHub Actions execution

Those components can remain as private fallback infrastructure, but they are not part of the primary cloud path.

## Credentials

Runtime credentials must only be supplied through GitHub Actions repository secrets:

- `WP_BASE_URL`
- `WP_USERNAME`
- `WP_APP_PASSWORD`

Never place these values in workflow YAML, scripts, README files, issue bodies, commit messages, or public action logs.
