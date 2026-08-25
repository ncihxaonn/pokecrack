---
prompt_version: escalation-v1.1.0
schema: validator.schema.json
---

# One-shot escalation

Resolve only the stated extractor/validator disagreement against the bounded source and
catalog evidence. Return one validator-schema JSON object and no other text. Derive every
field in `observed` independently from source evidence rather than copying either prior
result, and include exactly one check for every statistics field. Use `null` when unsupported
and **do not guess**. You may agree with either prior structured result only when the source
supports it; otherwise reject with conflict codes. Do not output reasoning, explanations,
hidden deliberation, or chain-of-thought. This prompt may run at most once per source item.
