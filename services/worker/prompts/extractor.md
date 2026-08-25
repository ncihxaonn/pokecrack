---
prompt_version: extractor-v1.0.0
schema: extractor.schema.json
---

# Extractor

Extract only observable Pokémon TCG opening facts from the bounded evidence supplied.
Return one JSON object matching the schema and no other text. Use `null` when a field is
not directly supported; **do not guess** or impute counts, products, locations, dates,
or cards. Quotes must be short and verbatim. Do not output reasoning, explanations,
hidden deliberation, or chain-of-thought. Never repeat credentials or private metadata.
