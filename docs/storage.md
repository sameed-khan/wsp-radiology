# Reviewed run artifacts and DVC handoff

The full Git/DVC/local-only plan and proposed commit boundaries are in
[versioning-policy.md](versioning-policy.md). The protected-history audit
decision is in [decisions.md](decisions.md). This page describes the current
bounded helper, not a completed full-session or large-checkpoint exporter.

Publicly downloadable datasets, base weights, and derived features must **never**
enter DVC. Re-download those assets instead. Only non-reproducible, generated
run reports, logs, transcripts, mappings, and checkpoints belong in this handoff.
Do not package public datasets, base weights, features, raw runtime/session
trees, credentials, or the parent conversation (which contains a credential).
Never point a copier at an entire session or runtime tree. Mappings must be
curated by a trusted parent separately; this tool does not ingest target labels.

Create `artifact-staging/` as a private, manually curated workspace, then copy
only individually selected files into it. Inspect **every byte**, including
transcripts and binary checkpoints, before acknowledging review. The name and
content checks catch only some common patterns; they do not prove redaction or
absence of arbitrary passwords, encoded secrets, public assets, or labels.
The category and generated-origin identifier are operator declarations, not
verified provenance. Do not put secrets into filenames or origin identifiers.
Keep staging and the output on trusted local storage; do not allow concurrent
writers during packaging. The tool accepts regular files only, forbids symlinks
and traversal, limits selections to 100 files and 128 MiB total, and never
recursively collects a directory. Inspect the manifest and SHA-256 receipt.

Example, after separately curating and reviewing two *generated* files:

```sh
mkdir -p -m 700 artifact-staging artifacts
# Manually copy and review selected source-review receipt and runtime test report:
# artifact-staging/review-receipt.txt and artifact-staging/test-report.txt
python3 scripts/archive_artifacts.py --archive run-001.tar --reviewed \
  --file reports:review-receipt.txt:source-review \
  --file reports:test-report.txt:runtime-test
# After inspecting the manifest, install the archive and register it locally:
python3 scripts/archive_artifacts.py --archive run-001.tar --reviewed --write --dvc-add \
  --file reports:review-receipt.txt:source-review \
  --file reports:test-report.txt:runtime-test
# Separately, after checking remote configuration and approval:
dvc push -r b2 -- artifacts/run-001.tar.dvc
```

Alternatively `--push` together with `--write --dvc-add` explicitly pushes to the
existing `b2` remote. No configuration or credentials are managed here. DVC
output is suppressed by the script to avoid credential disclosure; investigate
errors privately. Record the printed whole-archive SHA-256 receipt separately.
The archive contains `manifest.json` with per-file SHA-256, size, category,
and generated origin. Identical selections produce identical archive bytes.
Installation is atomic and private (mode 0600); existing archives are refused
unless `--overwrite` is explicitly specified. Avoid overwriting historical
artifacts: choose a new name instead. DVC failure leaves the installed archive
in place; retry DVC commands manually after private diagnosis.

To verify a restore, in an appropriately configured trusted checkout use
`dvc pull -r b2 -- artifacts/run-001.tar.dvc`, then compare
`sha256sum artifacts/run-001.tar` with the independently recorded receipt.
Inspect the archive listing and manifest with `tar -tf artifacts/run-001.tar`
and `tar -xOf artifacts/run-001.tar manifest.json`; check extracted files against
the manifest hashes in a private directory. Never extract untrusted archives.
Track the `.dvc` pointer and `artifacts/.gitignore`, not archive bytes or staging.
