# Harness status

The trusted supervisor, container tools, subagent tools, recorder, lifecycle,
accounting and seal are **not implemented**. This repository is not ready to
launch F/G runs; do not treat the search extension as a sandbox.

## Search extension

`harness/pi-ext/web-search.ts` registers only `web_search`. It uses the Brave
Search API for result titles, URLs and snippets, without a page-fetch tool or
page-content request. Set `BRAVE_API_KEY` in the trusted host process; do not
pass it to the container. Without it the tool reports that search is
unavailable. The installed pi-web-access package supports search and fetching,
but no pi-web-access configuration file or Brave environment credential was
present during implementation. This wrapper does not use that package's
configuration, other providers, content retrieval, or automatic fallback.
Provider errors are suppressed and credentials are redacted from result fields.
Search results remain untrusted third-party text; snippet access does not enforce
the study denylist or replace the sandbox/proxy controls.
