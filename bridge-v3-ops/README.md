# Keshavarz20 Bridge v3.1 requests

Commit a uniquely named JSON file under bridge-v3-ops/.

## Search and patch content

```json
{"action":"content.search","payload":{"target_type":"post","post_id":123,"field":"post_content","pattern":"old text"}}
```

```json
{"action":"content.patch","payload":{"target_type":"post","post_id":123,"field":"post_content","old_content":"old text","new_content":"new text","expected_sha256":"<from search>"}}
```

## Elementor safe edit

```json
{"action":"elementor.search","id":123,"payload":{"pattern":"old heading"}}
```

```json
{"action":"elementor.edit","id":123,"payload":{"old_content":"old heading","new_content":"new heading","expected_sha256":"<from search>"}}
```

## Media

```json
{"action":"media.import","payload":{"url":"https://example.com/image.webp","alt_text":"Example"}}
```

```json
{"action":"media.transform","payload":{"attachment_id":321,"width":1200,"height":1200,"crop":true,"quality":82}}
```

## Background job

```json
{"action":"job.create","payload":{"items":[{"action":"seo.read","id":123},{"action":"cache.status"}]}}
```

Use job.status or job.run with payload.job_id to inspect/resume.

## Engine router

```json
{"action":"engine.status","engine":"question"}
```

```json
{"action":"engine.run","engine":"news","lookback_hours":24,"dry_run":true}
```

```json
{"action":"engine.run","engine":"social","engine_action":"prepare"}
```

Article runs require an existing allow-listed daily-agri-articles/queue/*.json path.

## GitOps profile

```json
{"action":"gitops.profile"}
```
