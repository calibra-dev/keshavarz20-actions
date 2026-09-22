# Bridge v3.2 request examples

## Observability
```json
{"action":"observability.status"}
```

## Lifecycle self-test
```json
{"action":"selftest.run"}
```

## Snapshot rollback
First request:
```json
{"action":"snapshot.rollback","payload":{"snapshot_id":123}}
```
The response returns `approval_id` and `fingerprint`. Execute the frozen request with:
```json
{"action":"approval.execute","payload":{"approval_id":"ap_...","fingerprint":"..."}}
```

## Gutenberg block patch
```json
{"action":"content.block.inspect","id":123,"payload":{"block_path":[0]}}
```
```json
{"action":"content.block.patch","id":123,"payload":{"block_path":[0],"old_content":"Old","new_content":"New","expected_sha256":"..."}}
```

## Elementor structural edit
```json
{"action":"elementor.structure","id":123,"payload":{"operation":"update_settings","element_id":"abc1234","settings":{"title":"New title"}}}
```
Remove, duplicate, insert and move require two-phase approval.

## Job recovery
```json
{"action":"job.create","payload":{"items":[{"action":"cache.status"}],"max_retries":2,"backoff_seconds":30}}
```
```json
{"action":"job.retry_failed","payload":{"job_id":"job_..."}}
```

## Media Pro
```json
{"action":"media.optimize","payload":{"attachment_id":321,"mime":"image/webp","quality":82,"max_dimension":1920}}
```
```json
{"action":"media.focal_crop","payload":{"attachment_id":321,"width":1200,"height":1200,"focal_x":0.5,"focal_y":0.35}}
```
```json
{"action":"media.watermark","payload":{"attachment_id":321,"watermark_attachment_id":400,"opacity":0.35,"scale":0.22,"position":"bottom-right"}}
```

## Self update
```json
{"action":"update.check"}
```
```json
{"action":"update.stage"}
```
```json
{"action":"update.apply"}
```
Apply and rollback use the same two-phase approval flow.
