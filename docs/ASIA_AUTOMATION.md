# Asia country automation

## Manual workflow

The six-country `Asia country research` workflow is retained for manual checks
on `main`; it has no timer. It sends only the reviewed research script to a fresh MAM temporary
directory. MAM's existing Codex CLI runs one ephemeral, read-only research call
using ChatGPT authentication, live web search, no shell tools, no inherited
MCP configuration, and no production database/API credentials. There is no
local-Mac timer, paid API fallback, browser login, or source-policy bypass.
Existing Codex account usage limits still apply; this is not unlimited compute.

The `auto` selector still chooses Vietnam → Malaysia → Indonesia →
Philippines → Hong Kong → India by six-hour UTC slots anchored at 2026-09-08
00:00 UTC. Manual dispatch can select a region. The global workflow now also
runs hourly and accepts the same explicit scope choices; all
three workflows preserve their research history in the single
`data/research/research-ledger.json` file.

The research call has a ten-minute hard timeout, no automatic failure retries,
up to three candidates and a 16 KiB output cap. It is instructed to use at most
eight search queries. Only structured public source URLs, provisional pack/date
facts, geography basis and fixed missing-check codes can leave MAM. No media,
article text, account identifiers, private payloads or auth diagnostics are
published. YouTube watch-page URLs are rejected because the current attempted
route encountered access challenges; alternate routes must not bypass them.

Research results are written to the single
`data/research/research-ledger.json` file through a reviewed pull request.
The workflow no longer creates, edits or reopens GitHub issues. Disable the
workflow to stop manual dispatches. An unavailable Codex login/usage window
fails the run rather than falling back to an API key or changing credentials.

## Evidence and release gates remain mandatory

Research is **not admission or publication**. The validator always marks access,
rights and independent review as outstanding. Even a fully populated result
cannot write to Supabase, enable a collector or alter the public coverage map.
Reported pack counts are candidate claims, not verified observations.

For each promising candidate, the implementation agent must independently:

1. Open the primary source and resolve complete-opening denominator, date,
   product identity, duplicates and the exact geographical basis.
2. Review source terms/rights, robots, bounded acquisition, retention and kill
   switch. Stop on access denial; do not use proxies or another identity.
3. Implement an exact source policy/adapter plus adversarial fixtures. Keep
   discovery metadata separate from coverage and probability evidence.
4. Run MAM tests and structured autoreview, then GitHub PR/CI and merge.
5. Where a migration is required, complete the existing verified backup/restore
   and reviewed migration workflow before Worker deployment.
6. Verify the deployed SHA, actual collection and public projection. Only then
   mark the region/source live and update the reviewed evidence record.

The automation intentionally stops at the independent-review handoff. It does
not claim autonomous end-to-end country publication or repair production
monitor credentials. Current approved source collectors continue on their
existing MAM scheduler independently of this research workflow.

## Operator links

- [Run history / manual dispatch](https://github.com/ncihxaonn/pokecrack/actions/workflows/asia-research.yml)
- [Research ledger](https://github.com/ncihxaonn/pokecrack/blob/main/data/research/research-ledger.json)
- [Live sources](https://pokecrack.vercel.app/sources)

The Codex controls follow [non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
No model or API credential is provisioned by this workflow.
