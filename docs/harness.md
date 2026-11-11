# Harness

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

---

# Harness design (supersedes the status line above)

The simple backend and the networked `infra` backend have both been exercised
with real Haiku. Infra starts the L2 sandbox, watcher and GPU watchdog; helper
exits are logged and restarted by the supervisor.

## Components and trust boundary
Trusted, host-only (never mounted into containers): `harness/pi-ext/*`
(container-tools, subagents, web-search + exa-search.mjs), `src/wsp_harness/*`
(supervisor, run, cli, evidence, config, sandbox_*), the run directory
`runs/<id>/{recorder,state,control,snapshots,launch.json,interventions.jsonl}`,
and `~/.pi` credentials. The agent container gets only `runs/<id>/workspace`
(rw, `/workspace`) and the pool/labels directories read-only
(`/inputs/pool`, `/inputs/labels`). Container: network none (simple backend),
cap-drop ALL, no-new-privileges, read-only rootfs, uid 1004, no docker.sock.
Pi itself runs on the host; its read/write/edit/bash tools are replaced by
`container-tools.ts`, which uses `docker exec` argv arrays with no host shell.
Subagents (`subagents.ts`) are fixed to `anthropic/claude-haiku-5-5`, have
container tools only (one level), at most 8 run concurrently, and are killed
at the deadline. API keys stay on the host.

## Run layout
`launch.json` (git revision, input/extension hashes, models, labels sha256,
start/deadline, rendered launch prompt + hash, image id);
`recorder/rpc-events.jsonl` (verbatim Pi stdout) + `rpc-receive-times.jsonl`;
`recorder/sessions/*.jsonl` (Pi session), `recorder/subagents/<uuid>.events.jsonl`
+ session files; `state/status.json`; `control/` (STOP_REQUEST.json, messages/);
`snapshots/` (hourly rsync link-dest + manifest, final snapshot);
`interventions.jsonl` (every auto/manual intervention).

## What is and is not guaranteed (ADR-001)
Guaranteed by construction/tests: complete tool-result record (`verify`
cross-checks the RPC log against parent and subagent session files), subagent
assistant messages all Haiku, frozen filesystem at the deadline
(abort, kill process group and run-tagged children, `docker pause`, final
snapshot, `docker rm -f`), host-clock deadline, logged interventions.
Not guaranteed: periodic snapshots are not atomic with a running agent; a
process that escapes the in-container process group is only stopped by
sandbox teardown; web_search goes through Exa outside the sandbox proxy and
cannot enforce the denylist; the secret scan is pattern-based; helper supervision is polling-based, and
watcher/watchdog outages between checks are possible.

## Orchestrator commands
(`wsp-harness [--root R] ...`; `--root` defaults to the repo.)
- `prepare-launch --k 10|50 --resample 1 [--image TAG] [--proxy-image TAG]` creates a fresh private `.runtime/run-inputs/` receipt and a separate labels-only directory in the main checkout. It prints both preview prompts and their unified diff, then a JSON checklist; exit 1 means at least one check failed. GPU free memory requires 22 GiB for two 11 GiB caps. Receipt includes image IDs and available repository digests, not a claim that mutable tags are pinned. The prompt preview uses a shared current timestamp; actual launch times and prompt hashes differ. Use the printed labels path for both arms, recheck its hash and all dynamic checks at launch. Readiness is not approval: orchestrator must verify red-team, prerequisite baselines, freeze/tag and investigator authorization. The receipt and labels contain private material; retain securely or delete when no longer needed.
- `launch --arm F|G --k K --labels DIR --pool DIR [--hours 24] [--backend simple|infra] [--test-model]`
  detaches the supervisor (setsid or `--daemonizer systemd`) and prints the run id.
  Infra backend also needs `--models-dir --external-dir --hash-corpus`; it defaults to `wsp-agent:phase1` and the sandbox defaults to `wsp-proxy:phase1`. `--image` overrides the agent image.
  Pass the resolved main-checkout pool, an agent-only labels directory, the
  main-checkout models and external directories, and the private hash corpus.
  State, proxy logs, CA keys and helper logs stay under the run's `state/`.
  `TASK.md`, `output/`, and (when available in the root or image) `TOOLKIT.md`
  are seeded in the workspace. The launch receipt records the selected image.
- `status [--run R]` — all runs, or one run's status.json plus supervisor liveness. The effective deadline, original deadline and total extension seconds are recorded in status.
- `extend --run R --seconds S --reason TEXT` — append a positive finite number of seconds to the host-owned extension ledger and log an infrastructure intervention. The supervisor picks it up on its next tick; `state/deadline.json` publishes the effective deadline atomically to subagents. An automatic rate-limit outage runs from the first classified failure to the next successful model progress; a fixed notice is sent after recovery. During an unresolved outage the supervisor and subagents wait for recovery rather than freezing at the unextended deadline. Stop remains available for operator action.
- `intervene --run R --kind infra|message --note TEXT` — logged; `message` is
  delivered as a Pi steer (or prompt when idle).
- `detach --run R` — abort Pi, terminate its process group and recorded children, stop helpers, and exit with phase `detached`; the sandbox and proxy remain running and no final snapshot is taken. Waits for supervisor exit.
- `adopt --run R` — start a new supervisor on the existing sandbox, restoring counters and the latest parent session; resumes with the standard continuation prompt. Backend is inferred from `state/backend.json`; no sandbox is created. Refuses a live supervisor or frozen run. Adoption failures leave the sandbox running for operator investigation.
- `stop --run R --reason TEXT` — writes control/STOP_REQUEST.json; supervisor freezes.
- `verify --run R` — JSON completeness report (exit 1 when incomplete).
- `account --run R [--no-prices]` — usage/cost by model, source, token type; retries; wall clock; GPU.
- `seal --run R [--artifacts DIR]` — receipt.json with sha256s, secret scan,
  copy to `artifacts/runs/<run>/` for `dvc add`. Never pushes.

## Cutover procedure

From the **new code worktree**, using an absolute run directory `R` and the same host account/environment as launch:

1. `uv run wsp-harness detach --run "$R"`; inspect `uv run wsp-harness status --run "$R"` for `phase: detached`, no live supervisor, and confirm the agent (and infra proxy) remain running. Detach is supported only by supervisors started with this version of the code.
2. For an older supervisor that has no detach implementation, first independently verify its PID and command line against `R/state/supervisor.pid`, then `kill -KILL "$PID"` (NOT SIGTERM, which freezes the run). Wait for it to exit; the new supervisor reaps orphaned Pi/children and replaces matching run-specific helpers. This abrupt fallback can interrupt a tool result and lose the last status-counter interval; verify and audit the resulting evidence. Do not use it on a different run or PID. Containers remain running. The normal detach command is preferable.
3. Inspect `state/rate-limit-outage.json` and the extension ledger. An interrupted outage is **not** automatically recovered; calculate any uncredited outage explicitly and run `uv run wsp-harness extend --run "$R" --seconds S --reason 'measured provider outage / cutover'` before adoption. Avoid double-counting existing ledger entries. Adoption archives the interrupted marker under `state/rate-limit-outage-interrupted-*.json` so it remains evidence without falsely suspending child deadlines. Use the same procedure for measured cutover downtime if appropriate.
4. `uv run wsp-harness adopt --run "$R"`; inspect status, `interventions.jsonl`, supervisor log and helper/proxy logs. The new supervisor resumes the latest parent session file with a standard continuation, not the launch prompt. Monitor until normal deadline freeze, then `uv run wsp-harness verify --run "$R"`. On failure do not assume the sandbox was frozen: inspect status/logs and repair or stop deliberately. Do not run two supervisors concurrently.

Legacy launches without the new extension prompt hash still validate every original input hash; the fixed extension prompt comes from the new worktree. Extension code changes at cutover are recorded by the intervention rather than altering the original launch receipt. Abrupt replacement cannot recover counters since the last status write or guarantee a complete interrupted tool call; `verify` exposes mismatched tool-result records. Check remaining Docker resources if a supervisor fails during cutover.

## Tests
`uv run --extra test pytest -q` (offline). Paid/Docker: `WSP_LIVE=1 uv run --extra test pytest -q tests/test_harness_run.py tests/test_harness_supervisor.py tests/test_harness_cli.py tests/test_harness_e2e.py`;
other opt-in tests: `WSP_LIVE_CONTAINER_TEST`, `WSP_LIVE_SUBAGENT_TEST`, `WSP_LIVE_SNAPSHOT_TEST`.

## Rate-limit / subscription-quota policy (ADR-005, investigator requirement 2026-11-11)

When a model call fails with a rate-limit or quota error (429, rate_limit_error, usage limit,
quota, too many requests, overloaded/529, ...), the supervisor opens an outage, keeps retrying
with exponential backoff capped at 15 minutes (so at least one attempt every 30 minutes), with
no attempt limit, and does not freeze at the deadline while the outage is open. This guarantees
retries across at least a full 5-hour subscription window. On the first successful model output
the whole outage (first failure to recovery) is added to the deadline and the agent receives the
fixed extension notice.
