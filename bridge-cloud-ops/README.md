# bridge-cloud-ops

This folder is for public-safe, non-secret write/control requests sent to the custom WordPress operations endpoint.

Do not commit credentials, private customer/order data, authenticated read results, access tokens, application passwords, or private configuration here.

Each JSON request committed to this folder triggers the cloud Bridge workflow. The workflow stores only a sanitized success/status result and never commits the WordPress response body.
