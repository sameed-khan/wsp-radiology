# Harness status

The trusted supervisor, recorder, lifecycle, accounting and seal are **not
implemented**. Container tools and Haiku subagent tools are implemented, but
this repository is not ready to launch F/G runs; do not treat the search
extension as a sandbox.

## Search extension

`harness/pi-ext/web-search.ts` registers only `web_search`. The host-only
wrapper reads `exaApiKey` from `~/.pi/exa-search.json` and calls Exa search
for up to 10 titles, URLs, publication dates and short highlights. It does not
request full page text or expose a page-fetch tool. Never mount the credential
file into a container. Missing or invalid credentials yield a clear error;
provider errors are suppressed and the key is redacted from result fields.
Run `node --test tests/test_exa_search.mjs` for mocked tests. Search results
are untrusted third-party text. Exa generates highlights on its servers; this
search endpoint bypasses the sandbox proxy and snippet access does not enforce
the study denylist or replace network and content controls.
