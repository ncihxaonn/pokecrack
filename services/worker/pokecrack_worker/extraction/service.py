from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import ExtractorOutput
from .providers import AICompletion, AIImage, AIInputLimitError, AIProvider, AIRequest

EXTRACTOR_PROMPT_VERSION = "extractor-v1.0.0"
EXTRACTOR_SYSTEM_PROMPT = """You extract only observable Pokémon TCG pack-opening facts.
Return only the supplied JSON schema. Use null when evidence does not support a fact;
do not guess. Evidence quotes must be short verbatim excerpts. Do not provide
reasoning, explanations, hidden deliberation, or chain-of-thought.
"""


@dataclass(slots=True)
class AIExtractor:
    provider: AIProvider
    system_prompt: str = EXTRACTOR_SYSTEM_PROMPT
    prompt_version: str = EXTRACTOR_PROMPT_VERSION
    max_text_chars: int = 20_000
    max_images: int = 6

    def extract(
        self, input_text: str, *, images: Sequence[AIImage] = ()
    ) -> AICompletion[ExtractorOutput]:
        if len(input_text) > self.max_text_chars:
            raise AIInputLimitError("max_text_chars", len(input_text), self.max_text_chars)
        if len(images) > self.max_images:
            raise AIInputLimitError("max_images", len(images), self.max_images)
        request = AIRequest(
            operation="extract",
            system_prompt=self.system_prompt,
            input_text=input_text,
            schema_name="extractor_output",
            schema=ExtractorOutput.json_schema(),
            decoder=ExtractorOutput.from_mapping,
            prompt_version=self.prompt_version,
            images=tuple(images),
        )
        return self.provider.complete(request)
