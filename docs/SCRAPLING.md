# Scrapling use

Scrapling is a policy-gated public-web transport, not permission to scrape. The source registry decides whether a domain and `static`/`dynamic` route are enabled.

## Adapter flow

1. Resolve the exact host in `config/sources.yaml`; unknown/disabled fails.
2. Enforce robots/terms decision, HTTPS, page/run, requests/minute, delay, timeout and per-domain concurrency.
3. Prefer cached conditional HTTP/static parsing.
4. Use dynamic Chromium only when `dynamic_allowed=true` and the approved field cannot be obtained statically.
5. Extract only adapter-declared metadata/bounded text; normalize canonical identity; discard transport buffers.
6. Mark statistics ineligible by default and pass evidence through normal validation.

Conservative defaults are `SCRAPLING_HTTP_CONCURRENCY=4`, `SCRAPLING_PER_DOMAIN_CONCURRENCY=2`, `SCRAPLING_BROWSER_CONCURRENCY=1`, `SCRAPLING_REQUEST_TIMEOUT_SECONDS=30`, and `SCRAPLING_DEFAULT_DELAY_SECONDS=8`; exact source policy can be stricter. The validated worker maximum is `SCRAPLING_MAX_RAW_TEXT_CHARS=20000`. `SCRAPLING_SAVE_RAW_HTML=false` is the only supported production value. If temporary evidence capture is approved for debugging, put it outside Git, restrict permissions, define an expiry and remove it after diagnosis.

## Failure and change control

403/429, robots denial, consent/login wall, CAPTCHA, repeated selector mismatch or unexpected large/media response causes a bounded failure—not bypass/escalation. Disable the adapter after structural drift until fixtures/selectors and policy review are updated. Do not fall back from a blocked public adapter to an authenticated account automatically.

Scrapling does not download videos, evade bot controls, rotate proxies or expose its browser endpoint. CI uses fixtures only and performs no live scrape.
