---
prompt_version: validator-v1.1.0
schema: validator.schema.json
---

# Independent validator

Independently compare the bounded source evidence, extractor JSON, and catalog candidates.
Return one JSON object matching the schema and no other text. Derive every field in
`observed` independently from the bounded source; an extractor claim is not evidence and
must never be copied into `observed` merely because it was supplied. Include exactly one
`field_checks` entry for every statistics field. Use `null` when unsupported and
**do not guess**. Put factual conflicts in `contradictions` and concise rejection codes in
`rejection_reasons`. Do not output reasoning, explanations, hidden deliberation, or
chain-of-thought.
