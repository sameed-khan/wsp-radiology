# Phase 1 setup status

**Not ready to launch the pilot.** No experiments, pseudo-label API calls,
feature extraction, baseline training, or F/G sessions have been run.
This is an operational checkpoint, not a frozen preregistration.

## Completed

- MFXR archive downloaded from Figshare file 66766667; SHA-256:
  `80f959a9a51ff7c441459bcbbfa174d084d50126685f4ca980c8e84cfd7cadfe`.
  Its MD5 matches the publisher's supplied and computed values.
- All three encoder repositories downloaded at pinned revisions, using
  host-only Hugging Face authentication. File hashes are recorded in
  `data/locked/model-sha256-inventory.json`.
- GRAZPEDWRI-DX (Figshare article 14825193 version 2) and FracAtlas
  (article 22363012 version 7) downloaded, publisher-MD5 checked, and
  extracted. SHA-256 receipts are in `.runtime/external-download.log`.
- MURA v1.1 downloaded from the official Stanford server:
  `https://cs.stanford.edu/group/mlgroup/MURA-v1.1.zip`.
  SHA-256:
  `c703aecceaf472ea9d38510c53a719323525418dd5ef427c05e52add0cfae198`.
  No publisher checksum was located; this is a locally recorded hash,
  not independent publisher verification. No usage-terms file was found
  inside the archive. Resolve applicable terms before training or API use.
- External archive paths were inspected for traversal and symlinks before
  extraction. Extracted image counts: GRAZPEDWRI-DX 20,327;
  FracAtlas 4,085; MURA 40,009 (36,812 train and 3,197 validation).
- Preparation code repaired by GPT-6.1-Terra and independently reviewed by
  GPT-6.1-Sol. Parent independently ran the 13 passing regression tests and
  `uv lock --check`. See `docs/data-preparation.md` for generation layout.
- Offline Docker containment fixture built and independently rerun by the
  parent: all 21 smoke checks passed, including cleanup. Its independent
  Sol review also passed with non-blocking notes. This remains an offline
  fixture, not a networked agent sandbox. See `docs/sandbox.md`.
- NVIDIA Container Toolkit 1.20.1 installed from NVIDIA's official package
  repository. The NVIDIA runtime is registered in `/etc/docker/daemon.json`
  without changing the default runtime. No Docker restart was performed.

## Storage policy

- Git: code, lockfiles, public source/download manifests, protocol and
  prompts, small non-sensitive summaries, and DVC pointer files.
- Ignored local files, **not DVC**: publicly downloadable archives, source
  datasets, base weights, and reproducible feature caches. Current roots:
  `data/`, `models/`, and `features/`.
- DVC: selected non-reproducible run artifacts, session traces, long
  transcripts, generated checkpoints, and randomized run mappings needed
  to reconstruct historical runs. The reviewed packaging helper in
  `scripts/archive_artifacts.py` handles explicitly curated inputs up to
  128 MiB; it is not a full-checkpoint archival solution. See
  `docs/storage.md` for review requirements and commands.
- Preserve existing DVC remote `b2`; do not replace its configuration or
  copy public assets into its object store. Rclone read access was checked.
- Never archive credentials, host authentication files, environment dumps,
  or the raw parent conversation: it contains a credential. Review/redact
  any selected transcript before archival. No raw sessions or parent
  conversation have been uploaded. Six manually reviewed code-review and
  runtime-validation summaries were archived and pushed through DVC to B2.
  Pointer: `artifacts/setup-evidence-20261108.tar.dvc`; archive SHA-256:
  `b2e2a30195e699d469dc683e932623efd8fef58e5ffb232220671cab3a3a8bc7`.
  An independent rclone retrieval of the DVC remote object matched that
  hash and all six per-file manifest hashes. A second test moved aside
  both the local archive and its DVC cache object: `dvc pull` from `b2`
  restored the archive with the same SHA-256. The pointer is committed
  with the reviewed implementation; a fresh-checkout test is separate
  from this successful cold-cache restore. No public assets were uploaded.
  DVC's local credential file was found group/world-readable and restricted
  to mode 0600; the DVC cache, staging and archive directory are mode 0700.
- Locked labels and source-to-anonymous mappings remain host-only.
  Anonymous pool filenames must never be recorded in public manifests
  together with original source names or labels.

## Data preparation state

The initial pool was unapproved because the first implementation omitted
its private mapping and did not fully strip metadata. It is now quarantined
under `data/locked/quarantine/`. The corrected real-data rebuild completed
with exit 0 using the reviewed Terra implementation. The parent verified
all 2,993 PNGs have empty metadata and mode 0600, a mapping/file bijection,
expected counts, test exclusion, private directories at 0700, and idempotent
validated reuse. Receipts: `.runtime/mfxr-rebuild.log` and
`.runtime/mfxr-parent-validation.json` (also included in the DVC archive).
`data/pool` is an atomic generation pointer; a container must bind only its
resolved pool directory, never the enclosing locked directory.
Technical preparation passed. The investigator approved using the observed
1,484 patient IDs and the proposed zero-label rules on 2026-11-08. No label
subsets have yet been released.

The source has 4,586 images with the expected official class/split counts,
but **1,484 distinct patient prefixes** (993 train; 491 test), rather than
1,482 reported patients. Prefixes have no whitespace/non-digit anomalies,
and none crosses the official split or class boundary. The paper's Data
Records explicitly identifies prefixes as anonymized patient identifiers.
The investigator approved these 1,484 IDs and reported checking the site
and confirming a 2026-07-18 posting date. Preserve the conflicting historical
API field as a documented discrepancy; the date confirmation is investigator
attestation, not a new independent archival verification by the assistant.

## Remote reboot checkpoint

Read-only checks found plain ext4 root storage with no apparent boot-time
encryption unlock; SSH/socket and NetworkManager enabled at boot; and a
system-wide wired connection configured to auto-connect. The wired address
is DHCP-assigned, so its persistence and remote routing are not guaranteed.
GRUB selects its first entry with no configured menu delay; Secure Boot is
not enabled. The new installed kernel has NVIDIA module 580.178.04.

The investigator rebooted successfully on 2026-11-08. The assistant then
verified that host `nvidia-smi` reports driver 580.178.04 and the RTX A5000
with 24,564 MiB, resolving the earlier module/userspace mismatch. Docker
reports the NVIDIA runtime, and a disposable, network-disabled container
with `--gpus all` successfully ran `nvidia-smi` against the same card.
This is GPU visibility validation, not a PyTorch training/compute test.
WinApps and the FHIR container were running after the reboot; neither restart
policy was changed. No further interruption or network change was performed.

## Remaining work and decisions

1. Carry the approved 1,484-ID grouping into the sampler and protocol,
   report the paper's 1,482 discrepancy, and record the investigator's
   confirmation of the July 2026 posting date without suppressing the
   conflicting historical API metadata.
2. Implement the approved zero-label rules: target-supervised methods are
   not applicable at k=0; valid zero-shot methods receive no target-label
   tuning and use a preregistered fixed threshold.
3. Implement the approved unrestricted F/G design with protected,
   host-owned Pi history and audit records; no restricted fitting/editing
   service. Prevent agent/subagent writes to the recorder, harness and
   authoritative history, and audit checkpoint/script lineage. This is
   audited provenance, not proof of every parameter's origin. See
   `docs/decisions.md` ADR-001 and `docs/versioning-policy.md`.
4. The investigator confirmed MURA research use is permitted; record that
   authorization in acquisition metadata. SKELEX derivative-release policy
   remains separate: do not assume distributing weight differences satisfies
   no-derivatives. No MURA-specific third-party API approval was inferred.
5. Complete networked TLS proxy, URL/content filtering, origin-aware
   workspace monitoring, approved agent tools, and the actual red-team test.
   Offline containment is not a substitute. A global image matcher would
   also flag permitted pool derivatives, so watcher semantics need care.
6. Extend the bounded artifact helper or establish a reviewed DVC handoff
   for large generated checkpoints. Small-summary DVC upload and B2 restore
   validation passed; raw transcript archival remains review-gated.
7. Host and Docker GPU visibility now pass. Install and validate the ML
   environment, extract frozen features, implement/test
   toolkit and arms A–E/H, and run the preregistered baseline grid.
8. Implement locked patient-level evaluation, paired resampling, resource
   accounting, F/G lifecycle and output/provenance audit. Resolve unavailable
   subgroup annotations rather than inventing control-fracture labels.
9. Author/review F/G agent definitions and launch prompts, freeze approved
   protocol and manifests, and only then declare readiness for F/G launch.

The configured model catalog includes `anthropic/claude-opus-5-5`.
No inference request was made to test it. The documented `pi auth check`
CLI did not match the installed command parser, so API-auth readiness is
not established by that check; no credential was printed or refreshed.

## Non-blocking review notes retained for follow-up

Sol approved the delivered slices with notes, not a claim of full readiness:

- Preparation: explicit rebuild does not recover a dangling pool pointer;
  map validation should independently reject malformed split/label domains;
  the custom pixel limit should be checked before decoding. The approved
  fixed-checksum real archive and published generation passed actual checks.
- Offline smoke: cleanup exceptions should still emit a recovery report;
  the runtime read-only probe should distinguish EROFS from ordinary UID
  permission errors (the separate Docker configuration assertion passes).
- Artifact packaging: USTAR-incompatible long basenames can pass inspection
  but fail writing safely; the helper is bounded to 128 MiB and trusted,
  nonconcurrent staging. Fresh-checkout directory instructions were fixed.

The investigator-approved F/G provenance decision is explicitly recorded
in `plan.md` and `docs/decisions.md`. The plan is not yet launch-frozen.
