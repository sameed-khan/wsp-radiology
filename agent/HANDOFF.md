# Handoff: finish preparation, then start the Phase 1 pilot

Checkpoint: 2026-11-08. Repository on the GPU host:
`/home/skhanxx8/projects/wsp-radiology`.
The reviewed implementation, documentation, this handoff and setup-evidence
DVC pointer are committed and published on `origin/master` at
`git@github.com:sameed-khan/wsp-radiology.git`. Use `git log` for the exact
current revision; no public dataset/model bytes or credentials are in Git.

**The project is NOT pilot-ready. No feature extraction, baseline training,
pseudo-label inference, locked-test scoring, or experimental F/G sessions
have been run.** The completed work is acquisition, validated anonymization,
an offline containment fixture, and a small reviewed artifact workflow.
The next session should finish the missing infrastructure and harness, not
launch four 24-hour sessions immediately.

## Read first

1. `docs/decisions.md`: accepted investigator decisions, especially ADR-001.
2. `docs/setup-status.md`: detailed operational checkpoint, evidence and
   non-blocking review notes.
3. `plan.md`: study design, label budgets, leakage controls, arms and gate.
4. `docs/versioning-policy.md` and `docs/storage.md`: Git/DVC/local boundaries.
5. `docs/data-preparation.md`, `src/wsp_prep/`, and `tests/`: implemented CLI.
6. `docs/sandbox.md` and `infra/`: OFFLINE fixture, not a networked sandbox.
7. `research/datasets.md` and `research/mech-interp-toolbox.md`: background;
   distinguish older research claims from actual validated implementation.

## Investigator decisions: do not ask these again

- Docker is approved instead of Podman. Existing rootful Docker is trusted
  host infrastructure; do not describe it as rootless.
- Use the observed **1,484 patient IDs**: 993 train and 491 test, preserving
  the official split. Report the paper's 1,482 discrepancy.
- Investigator checked the source site and confirmed posting on
  **2026-07-18**. Keep the historical API-date discrepancy in provenance;
  do not silently remove it or present investigator attestation as a new
  independent archival verification.
- At k=0, target-supervised methods requiring labels are not applicable.
  Applicable zero-shot methods get no target-label tuning/model selection
  and a preregistered fixed threshold; define exact applicable recipes.
- MURA research use is approved. Do not infer a separate third-party API
  permission or SKELEX derivative-release permission from that approval.
- **F/G: unrestricted experimentation with audited provenance.** F cannot
  directly write model weights; G can. No restricted fitting API is required.
  Authoritative Pi histories, recorder and trusted harness/config must be
  outside agent/subagent write access. Retain complete history, script/code
  snapshots and checkpoint lineage, and audit violations. Protected traces
  record Pi interactions, not every operation inside arbitrary shell code;
  do not claim foolproof per-parameter attribution. ADR-001 is authoritative.
- Use **GPT-6.1-Terra for critical implementation** and
  **GPT-6.1-Sol to independently review all subagent-written code**. Luna was
  allowed for initial acquisition; its defects were repaired by Terra and
  reviewed by Sol. Follow local subagent/skill instructions before delegation.
- Publicly downloadable datasets/base weights must NOT enter DVC. Session
  histories and other generated run evidence belong in reviewed DVC archives.

## What is on disk and validated

### Data

- MFXR source: `data/locked/downloads/MFXR.zip`, SHA-256
  `80f959a9a51ff7c441459bcbbfa174d084d50126685f4ca980c8e84cfd7cadfe`.
- `data/pool` points atomically to the corrected private generation's pool.
  **2,993 PNGs**, all checked metadata-free with mode 0600. The private
  source-to-anonymous mapping is complete; all test entries are excluded
  from the pool. Private generation directories are mode 0700. Idempotent
  reuse was tested. **Resolve the symlink before mounting the pool alone**;
  never mount its enclosing private generation or `data/locked/` into agents.
- Find the current inventory using the resolved pool's sibling directory:
  `POOL=$(readlink -f data/pool)` and
  `INVENTORY="$(dirname "$POOL")/locked/inventory.json"`.
  The old top-level `data/locked/inventory.json` is NOT current. The old pool
  is under `data/locked/quarantine/`; do not accidentally reuse it.
- Current generation's `prefix-map-proposal.json` is still unreviewed.
  Next: materialize the approved prefix grouping as a reviewed map, validate
  full coverage/splits/labels, and implement the seeded patient sampler.
  Approval of the grouping is recorded, but no labeled subsets exist yet.
- External archives: `data/external/downloads/`; extracted data:
  `data/external/extracted/`. Image counts: GRAZPEDWRI-DX **20,327**,
  FracAtlas **4,085**, MURA **40,009**. Public manifests in `config/` record
  sources/hashes. MURA is a direct official Stanford archive, not yet handled
  by the Figshare-only `download-external` command.
- Parent validation receipts: `.runtime/mfxr-parent-validation.json` and
  `.runtime/mfxr-rebuild.log`. These are local ignored evidence, not a new
  public source manifest. No current acquisition/preparation job is active.

### Models and environment

- Base weights are at `models/skhoha/SKELEX`,
  `models/google/medsiglip-448`, and
  `models/facebook/dinov3-vitl16-pretrain-lvd1689m`.
  Exact revisions are pinned in `src/wsp_prep/core.py`; full file hashes:
  `config/model-file-sha256.json`.
- Host-only Hugging Face login is cached. Do not print credentials or mount
  the host token store into experimental containers. Gated access succeeded
  for all three encoders. Reauthenticate locally only if needed.
- Existing `.venv` contains preparation/test/model-download dependencies.
  **Torch/Transformers training infrastructure was not installed/validated.**
  `wsp-prep doctor` reporting Torch unavailable is not a failed NVIDIA driver.
- Investigator rebooted successfully. Host and a network-disabled Docker
  container both ran `nvidia-smi` successfully: **RTX A5000, 24,564 MiB,
  driver 580.178.04**. This does not establish PyTorch GPU compute correctness.
- NVIDIA Container Toolkit **1.20.1** is installed and registered in Docker.
  Existing WinApps and FHIR containers were left alone and running. Do not
  restart Docker, unload drivers, alter host networking, or reboot without
  renewed coordination; the investigator connects remotely.
- Configured Pi model catalog includes `anthropic/claude-opus-5-5`.
  No inference/auth-readiness test succeeded yet: documentation's
  `pi auth check --json --no-refresh` did not match the installed parser.
  Verify the actual supported CLI/SDK, without printing tokens or assuming
  catalog presence proves usable API authentication.

### DVC

- Existing default remote `b2` points to
  `s3://sk-research-data/wsp-radiology-data` with its configured B2 endpoint.
  Preserve that setup; host rclone remote is also `b2:`.
- Git pointer: `artifacts/setup-evidence-20261108.tar.dvc`.
  Archive SHA-256:
  `b2e2a30195e699d469dc683e932623efd8fef58e5ffb232220671cab3a3a8bc7`.
  Contains six selected review/validation summaries, NOT raw sessions,
  public assets, target mappings or credentials. DVC push, independent
  rclone retrieval/per-file verification, and a real cold-cache DVC pull
  all passed. Cold-cache receipt: `.runtime/dvc-restore-check/receipt.json`.
- `.dvc/config.local` credentials are restricted to 0600; local DVC cache
  and artifact/staging directories to 0700. Never commit credential files.
- Random anonymization mappings are still local-only. **Before depending
  on them for experiments, securely DVC-archive the canonical generated
  mappings/receipts and verify bucket access restrictions and restore.**
  Successful round-trip alone did not establish that the bucket is private.
- The current archive helper has a **128 MiB / 100-file limit**. Implement
  and review large-checkpoint and complete-history export/storage separately.
- The raw parent setup conversation contains a credential. **Do not ingest,
  copy, publish, or blindly DVC-archive it or entire Pi/runtime directories.**
  Do not carry any credential values into a handoff or future prompt.

## First commands in the next session

Use the project root. These commands inspect/reuse existing work; do not
redownload everything or run `prepare --rebuild` by default.

```sh
cd /home/skhanxx8/projects/wsp-radiology
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Only if the environment needs reconstruction:
uv sync --frozen --extra test --extra models

.venv/bin/python -m pytest -q          # expected: 25 passing tests
uv lock --check
uv run wsp-prep download              # verifies existing MFXR bytes
uv run wsp-prep prepare               # verifies/reuses current generation
uv run wsp-prep doctor                # network/auth presence, not proof of API use
nvidia-smi

# Optional offline containment regression; creates/cleans its own project.
# It is NOT a real agent launch or leakage red team.
mkdir -p -m 700 .runtime
python3 infra/smoke.py > .runtime/offline-smoke-next.json

# Restore setup evidence if missing; no public data comes from DVC.
dvc pull -r b2 artifacts/setup-evidence-20261108.tar.dvc
sha256sum artifacts/setup-evidence-20261108.tar
```

System CA environment variables resolved Python download verification on
this host. Never disable TLS verification to get a download working.
The smoke test previously passed all **21** checks twice, including cleanup.

## Implementation order: finish readiness before F/G

1. **Restore context and close small review notes.** See the P2 list in
   `docs/setup-status.md`. Do not redo the initial unapproved anonymization.
   Implement the reviewed patient map and sampler. Preserve actual sampled
   IDs/labels privately; F/G use the same samples as baseline resample 1.
2. **ML environment and encoder adapters.** Have Terra pin compatible Torch,
   Transformers and baseline/toolkit dependencies; Sol reviews. Verify a tiny
   CUDA computation and local-only model forward passes. SKELEX is ViT-MAE
   with default masking: disable masking and define deterministic feature
   extraction explicitly. Respect each encoder's preprocessing; MedSigLIP
   uses 448 px and DINOv3 has register tokens. Extract pool-only frozen
   features; never expose locked test features or labels to agents.
3. **Complete the networked sandbox.** `infra/` only demonstrates offline
   isolation. Implement/test TLS-intercepting proxy-only egress, CA trust,
   URL and content filtering, safe DNS/private-address handling, secret-safe
   host logs and hosted-fetch tool restrictions. Fix watcher semantics so
   legitimate pool-derived crops/probes do not falsely invalidate sessions.
   Test the actual GPU-enabled topology, not only the offline fixture.
4. **Trusted Pi recorder and agent lifecycle.** Implement ADR-001 outside
   agent write access; test attempted log/harness alteration and complete
   event retention. Add deadlines, checkpoint freezing, workspace snapshots,
   provenance audit, resource accounting and interventions. Verify Opus 5.5
   configuration and credential isolation. No host secrets/Docker socket
   inside agent workspaces. Create nearly identical F/G definitions/prompts.
5. **Toolkit, arms and locked evaluation.** Implement/test A–E/H, supervised
   validation restricted to k patients, exact k=0 applicability, patient-level
   bootstrap/evaluation and prescribed shared samples. Resolve how to handle
   unavailable other-fracture subgroup annotations without inventing labels.
   Define recipe/model-selection rules before scoring; do not silently
   substitute tiny-feature demos for fine-tuning, SSL or transfer arms.
6. **Data/source and resource audits.** Record external inputs and compare
   test pHashes with external datasets before scoring. Resolve how to give
   F/G equal GPU shares on this non-MIG A5000; do not claim an unenforced
   12-GB hard partition. Complete the approved-container leakage red team.
   Report audit limitations rather than declaring blanket security proof.
7. **Run the preregistered comparator grid**, archive generated artifacts,
   verify restore, and audit results. No test-feedback tuning of agent runs.
   Preserve SKELEX modifications privately pending release-rights review;
   a weight delta is not automatically safe to publish under no-derivatives.
8. **Freeze launch inputs and then start F/G.** Identify Git revision,
   prompt/config/model/container hashes, sample manifests and DVC pointers.
   Verify all launch gates. Run paired F/G at k=10 together, then k=50,
   with one resample and 24 hours per session, as specified in the plan.
   Apply locked evaluation and the Phase 1→2 gate only after audits.

Do not start Phase 2 downloads/training or declare Phase 1 ready merely
because acquisition and GPU visibility succeeded. Follow the study plan and
ask the investigator about genuine unresolved scientific choices.
