from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from pokecrack_worker.extraction.models import ExtractorOutput
from pokecrack_worker.extraction.providers import AICompletion, AIProvider, AIRequest

from .models import ValidatorOutput

VALIDATOR_PROMPT_VERSION = "validator-v1.1.0"
VALIDATOR_SYSTEM_PROMPT = """Independently validate only observable Pokémon TCG opening facts
against source evidence and supplied catalog candidates. Return only the JSON schema.
Use null and do not guess when unsupported. Derive every field in observed independently
from the source; never populate observed by copying the extractor output. Check every
statistics field exactly once. Put factual conflicts in contradictions and concise rejection
codes in rejection_reasons. Do not provide explanations, reasoning, hidden deliberation, or
chain-of-thought.
"""


@dataclass(slots=True)
class AIValidator:
    provider: AIProvider
    system_prompt: str = VALIDATOR_SYSTEM_PROMPT
    prompt_version: str = VALIDATOR_PROMPT_VERSION

    def validate(
        self,
        source_text: str,
        extraction: ExtractorOutput,
        *,
        catalog_context: Mapping[str, Any] | None = None,
        operation: str = "validate",
    ) -> AICompletion[ValidatorOutput]:
        input_payload = {
            "source": source_text,
            "extractor_output": extraction.to_mapping(),
            "catalog_candidates": dict(catalog_context or {}),
        }

        def decode(payload: Mapping[str, Any]) -> ValidatorOutput:
            output = ValidatorOutput.from_mapping(payload)
            set_context = (catalog_context or {}).get("set", {})
            set_id = set_context.get("set_id") if isinstance(set_context, Mapping) else None
            return replace(
                output,
                set_id=set_id if isinstance(set_id, str) else None,
            )

        request = AIRequest(
            operation=operation,
            system_prompt=self.system_prompt,
            input_text=json.dumps(input_payload, ensure_ascii=False, separators=(",", ":")),
            schema_name="validator_output",
            schema=ValidatorOutput.json_schema(),
            decoder=decode,
            prompt_version=self.prompt_version,
        )
        return self.provider.complete(request)
