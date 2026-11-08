# Repository, DVC and local-only storage plan

**Status:** proposed operational layout, aligned with the investigator's
storage instructions and accepted audit decision in `docs/decisions.md`.
This document does not create a commit or implement the future audit system.

## Principle

Git stores the small, reviewable specification needed to reproduce and audit
the study. DVC stores selected experiment-specific evidence and artifacts
that must survive the machine. Publicly redownloadable assets and disposable
recomputable caches remain local and ignored. Credentials go into neither.
A file being Git-ignored does not imply it is disposable: DVC-managed bytes
and live protected audit records are also ignored by Git.

## 1. Commit to Git

| Material | Examples / planned locations |
|---|---|
| Study specification and decisions | `plan.md`, `research/`, `docs/decisions.md`, methods and storage policies |
| Implementation and tests | `src/`, `scripts/`, `tests/`, toolkit, baseline and evaluation code |
| Dependency/build specifications | `pyproject.toml`, `uv.lock`, reviewed Dockerfiles and pinned build inputs |
| Infrastructure definitions | `infra/`, proxy policies, leakage rules, synthetic red-team tests, audit/launcher code |
| Agent definitions and prompt templates | Reviewed `.pi/agents/` and prompt/configuration files; no credentials or run history |
| Public acquisition metadata | `config/public-datasets.json`, `config/mura-source.json`, `config/model-file-sha256.json`; exact URLs, versions, hashes, licenses/attestations and preprocessing recipe |
| Experimental specifications | Budget grids, recipe/hyperparameter settings, seed schedules, analysis/bootstrap rules and frozen prompt hashes |
| Small, disclosure-safe results | Audited aggregate metrics, concise run/audit summaries, selected final figures and manuscript sources |
| Artifact pointers and non-secret DVC configuration | `artifacts/*.dvc`, `dvc.yaml`/`dvc.lock` if used, `.dvc/config`, `.dvcignore`, ignore rules |

Do not commit target patient/image identifiers, labels, source-to-anonymous
joins, patient-level predictions or sensitive paths inside an otherwise
small manifest. Put the private manifest in DVC and commit only its pointer,
format/version, hash and a safe summary. Control-repository contents are not
automatically mounted into experimental agents.

## 2. Preserve with DVC in the existing B2 remote

Use immutable run/evidence identifiers. Keep DVC pointer files in Git and
artifact bytes ignored by Git. Do not independently rclone a second unrelated
copy of every artifact; DVC is the indexing/versioning authority. Rclone can
be used to verify/recover its B2 objects, as in the setup restore check.

| Material | Retention rule |
|---|---|
| Complete experimental Pi session/tool histories | Preserve all branches/events, not merely final assistant messages; review/redact credentials before archival and record redaction metadata without secret values |
| Host-side execution, proxy and intervention evidence | Preserve required complete records and separately captured output where Pi's visible output is truncated; logs have protected live storage before sealing |
| Run-specific code and workspace history | Archive code snapshots/diffs needed to establish what actually ran; record the baseline Git revision and executed-file/checkpoint hashes |
| Randomized data-control manifests | Archive the canonical anonymization map, generation receipt, reviewed patient mapping and exact per-run label allocation before depending on them; these are generated study artifacts, not another copy of the public dataset |
| Non-reproducible API outputs | LLM pseudo-labels, image-inspection responses, experiment transcripts and external-service responses that affected decisions |
| Generated models and interpretability artifacts | Final heads, adapters, edits/deltas where permitted, trained checkpoints and selected lineage checkpoints; fitted SAEs and other learned artifacts needed to reproduce a final model |
| Evaluation evidence | Per-image/patient predictions, locked evaluation outputs, bootstrap samples/results as needed, calibration/threshold fits and private subgroup/overlap reports |
| Decision-relevant probes | Generated or modified images not reconstructible from preserved public inputs, code and seeds; preserve exact model-input references/hashes |
| Original validation/audit evidence | Reviews, red-team outcomes, environment/run receipts, token/cost/GPU accounting and final audit verdicts |

Store necessary private evidence under appropriately restricted B2 access;
verify access policy before uploading private patient mappings or labels.
A successful upload/restore test does not itself establish bucket privacy.
SKELEX derivatives are private research artifacts pending a separate release
rights decision; DVC storage is not permission to publish checkpoints or deltas.

Avoid duplicating whole public image/model assets inside trace archives.
Where session records embed public image bytes, design a lossless evidence
export with stable content hashes and explicit reconstruction references,
while retaining the protected authoritative original locally. Do not silently
strip tool events, replace full traces with summaries, or discard unique
model inputs merely to reduce size. Secret redactions need a documented
export boundary; the raw parent setup conversation is not an archival input.

The current `scripts/archive_artifacts.py` is a reviewed, explicit-selection
helper limited to 100 files and 128 MiB. It is suitable for small evidence
bundles, not full ViT checkpoints or unrestricted long-session archives.
Large-run packaging/direct DVC directory tracking and complete history
export still require implementation and review before pilot launch.

### Planned artifact layout

```text
artifacts/
  setup-evidence-20261108.tar.dvc       # existing Git-tracked pointer candidate
  preparation-<id>.tar.dvc             # private generated maps and receipts
  run-<id>-history.tar.dvc             # complete reviewed event/export bundle
  run-<id>-outputs.dvc                 # large generated artifact directory
  run-<id>-evaluation.tar.dvc          # predictions and private audit results
```

Pointers are public only if their names/metadata do not disclose private
information. The bytes they reference are not committed to Git. Do not
overwrite a sealed historical run in place; produce a new artifact revision
with explicit lineage. B2 lifecycle pruning must not remove DVC objects still
referenced by retained study revisions; no automatic pruning is enabled here.

## 3. Ignore from both Git and DVC

### Reacquirable or recomputable assets

- `data/locked/downloads/`: the public MFXR source archive, even though local
  permissions and agent isolation keep it locked during experiments.
- `data/external/downloads/` and `data/external/extracted/`: public external
  datasets. Retain source versions, hashes and retrieval recipes in Git.
- `models/`: publicly downloadable base checkpoints and their Hub cache.
- Reconstructed anonymized image pools: regenerate from the public archive,
  preserved private mapping and versioned preprocessing. Do not throw away
  the mapping and assume a new random renaming recreates the old run.
- `features/` and equivalent reproducible activation/embedding caches:
  regenerate from the exact preserved model, inputs, code and settings.
- `.venv/`, Python/test/build caches, downloaded package layers and Docker
  build cache: recreate from reviewed dependency specifications.
- Failed partial downloads and disposable temporary files.

A derived artifact that cannot reliably be regenerated and was needed for
an experimental decision belongs in DVC, not in the disposable-cache bucket.
Do not delete or garbage-collect data currently needed by an active run.

### Secrets and machine-specific configuration — never version

- `.env`, API keys, OAuth tokens, Hugging Face token stores, SSH/private keys,
  rclone credentials, `.dvc/config.local`, cloud credential files and
  credential-bearing Docker/registry configuration.
- TLS MITM CA **private keys** and other service secrets. Version the CA
  generation recipe; keep keys in restricted local service storage.
- Secret-bearing raw parent conversations or unreviewed exports. Do not
  upload these to DVC just because they are already Git-ignored.
- Host-specific runtime state, PID files, sockets, absolute-path overrides
  and temporary staging such as `artifact-staging/`.

Use filesystem access controls and approved host credential storage rather
than Git/DVC for secrets. If a credential is exposed, rotate it; deleting a
file or rewriting a commit is not a substitute.

## 4. Protected live state is not disposable

Authoritative live session/audit records reside outside agent write access,
under the trusted recorder's control. Git-ignore them, but retain them until
the complete reviewed archive is sealed, DVC-pushed, restore-verified and
accepted under the retention policy. Archive selected evidence from
`.runtime/` or Pi storage through an explicit export; never blindly add an
entire runtime or home/session directory to DVC. Subagent workers must not
write the authoritative recorder's files either.

Do not expose private manifests or locked evaluation results to an agent
just because both its workspace and those files are under a Git-ignored root.
Mount only explicit run inputs and output directories.

## 5. Proposed Git commit boundaries

No commits are created by this plan. After final review, use these coherent
boundaries; do not bundle future unimplemented controls as completed work:

1. **Preparation and acquisition:** Python package, lockfile, tests, public
   manifests, preparation instructions and relevant ignore rules.
2. **Offline containment fixture:** existing Docker fixture/smoke test and
   its explicit limitations; not a claim of networked sandbox readiness.
3. **Artifact retention:** reviewed packaging helper/tests, storage policy,
   DVC configuration/ignore rules and existing setup-evidence pointer.
4. **Protocol and decision record:** accepted audit decision, study plan
   amendment, setup checkpoint, README links and concise review limitations.

Some ignore-rule changes span the first and third commits and should be
split by purpose. Preserve the existing plan/research history. A future
launch freeze should identify the exact Git revision plus every required
DVC pointer/hash and container image digest; it is separate from these
setup commits.
