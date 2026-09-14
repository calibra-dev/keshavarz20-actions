# Guarded requests

Files in this directory trigger the GitHub-hosted guarded site gateway. This directory is PUBLIC. Do not place credentials, customer data, unpublished sensitive drafts or private operational data here.

For normal chat-driven work, ChatGPT should use the private connected WordPress/WPVibe Abilities route instead of placing content in this public directory.

## Schema

```json
{
  "action": "product.read",
  "id": 135383,
  "payload": {}
}
```

Supported cloud actions:

- `product.read`
- `product.update`
- `product.create_draft`
- `product.stock`
- `product.content`
- `post.read`, `post.update`, `post.create_draft`
- `page.read`, `page.update`, `page.create_draft`
- `media.read`, `media.update`
- `taxonomy.read`, `taxonomy.create`, `taxonomy.update`
- `bridge.health`

For taxonomy actions also set `taxonomy` to one of: `category`, `tag`, `product_cat`, `product_tag`.

Price, sale, discount, coupon, credential, role/capability, customer and other administrative fields are rejected by the gateway.
