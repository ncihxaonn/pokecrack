# AI extraction and validation

AI is a bounded parser/reviewer after source policy, dedupe, size and catalog prechecks. It is not the source of truth and cannot make an ineligible source statistically eligible by assertion.

## Pipeline

1. Deterministic prechecks reject unsupported source, excessive text/images/keyframes/video duration, impossible counts and obvious catalog mismatch.
2. Extractor returns strict structured fields, evidence tier, field confidence and reason codes.
3. An independent validator receives source evidence plus the extraction but must return a separately derived `observed` fact object; extractor values are never copied into validator facts. It must check each statistics field exactly once.
4. Only exact fact agreement with complete, high-confidence field checks can be accepted. Tier C/D remains auxiliary/activity-only according to deterministic policy.
5. Disagreement invokes at most one configured escalation. It must agree with extractor or validator on facts/decision; otherwise reject.
6. Any low confidence, conflict code, malformed schema, timeout, budget breach or unresolved catalog error fails closed. There is no routine human review queue.

Defaults: `AI_MIN_ACCEPT_CONFIDENCE=0.92`, `AI_MIN_FIELD_CONFIDENCE=0.85`, `AI_MAX_SOURCE_ITEMS_PER_RUN=100`, `AI_MAX_TEXT_CHARS=20000`, `AI_MAX_IMAGES=6`, `AI_MAX_KEYFRAMES=12`, `AI_MAX_VIDEO_SECONDS=900`, `AI_MAX_OUTPUT_TOKENS=4096`, and `AI_CONCURRENCY=2`. The resolver’s threshold must be explicitly wired from settings; a helper default is not permission to weaken it. Provider/model/prompt/catalog versions and estimated usage are recorded privately.

## Budget and privacy

`AI_PROVIDER=fixture` makes no paid request and is mandatory in CI/demo. An optional real AI provider can incur provider charges and needs an explicit base URL, three pinned model identifiers, API key, `AI_DAILY_BUDGET_AUD` (default `5`) and `AI_MONTHLY_SOFT_BUDGET_AUD` (default `50`). The network-provider factory requires one injected shared budget ledger whose limits exactly match validated settings; it reserves a conservative upper bound for the serialized request plus the finite completion-token cap before transport dispatch. Return `budget_paused` rather than exceed either configured gate and record successful usage idempotently/atomically. Persistent cross-process budget accounting is part of the production worker composition-root blocker and is not represented as live today. This is an operating input cost, not a commercial/public paid API product. Send only the minimum bounded evidence, never cookies, passwords, service-role keys, private messages or full unnecessary media. Provider retention/training terms require owner review.

Fixture outputs prove orchestration/schema behavior only; they do not validate real model accuracy. Before live use, evaluate a versioned labelled set for precision, false inclusion, denominator/count error, tier calibration and source/language slices. Prefer conservative rejection; publish methodology/version and never expose raw prompts/provider responses publicly.
