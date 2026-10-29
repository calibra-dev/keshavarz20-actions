# Calibra Factor 1.1.5 release QA (2026-10-29)

Target archive SHA-256: 23b1959f8dca22dabf476f307bfa6dcd81eaeaa90a0c6d02b0a5c42971345ad4
Version: 1.1.5; only public branding and gettext domain changes from 1.1.4.

This commit intentionally invokes ONLY the containerized WordPress/WooCommerce infrastructure baseline (HPOS, legacy, Chromium). The commercial plugin ZIP has NOT been provided as a GitHub Actions artifact, and must not be described as installed/tested.

Before approval the exact ZIP must be uploaded via private authorized channel and hash-matched in the runner. Required checks: fresh install, reinstall and genuine upgrade; WooCommerce HPOS/legacy, order CRUD, guest order-pay, expiration/stock, SMS + WhatsApp, PDF storage and signatures, capabilities, RTL responsive admin+checkout. Do not store proprietary plugin ZIP or customer data in this public repository.
