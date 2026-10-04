# Phase 24 v3 direct capture import

Place only direct answer-surface capture files here.

Accepted formats:
- `.json`
- `.json.gz.b64`

Each file must contain:

```json
{
  "observations": [
    {
      "observation_id": "unique-id",
      "prompt_id": "K20-AI-000",
      "surface": "ChatGPT Search",
      "observed_at_utc": "2026-10-05T00:00:00Z",
      "evidence_type": "DIRECT_SURFACE_CAPTURE",
      "answer_present": true,
      "keshavarz20_cited": false,
      "brand_mentioned": false,
      "citation_urls": [],
      "cited_url": null,
      "recommendation_context": null,
      "competitor_source_set": [],
      "answer_url": null,
      "session_context": "authenticated real answer surface",
      "readback_verified": true
    }
  ]
}
```

Rules:
- exact prompt wording and exact planned surface only;
- no ordinary web search or inferred results;
- no duplicate prompt observations;
- citation=true requires a captured keshavarz20.com URL;
- readback_verified must be true;
- conflicting IDs or prompts fail closed.
