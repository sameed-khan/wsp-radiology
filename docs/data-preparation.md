# Phase-1 preparation receipt

The preparation CLI is `wsp-prep` (install with `uv sync --extra test --extra models`; command examples assume the repository root). Data and weights are stored under ignored `data/` and `models/`; nothing here stages or registers them with DVC. Run `wsp-prep download` to verify the MFXR archive SHA-256 and MD5 before atomic installation. Run `wsp-prep prepare` to read the archive in place without `extractall`, build a private source inventory, and emit PNG pixel-only training files under `data/pool/` using random names. Add `--root /path/to/repo` before the command when running elsewhere. The official test images, raw image hashes, labels, source names, patient-prefix proposal, and mapping are kept private under `data/locked/`.

MFXR filename prefixes are described as anonymized patient IDs and suffixes as view/augmented derivatives in the paper's Data Records: [Scientific Data, DOI 10.1038/s41597-026-07547-y](https://www.nature.com/articles/s41597-026-07547-y). The inventory reports the observed prefix count rather than asserting the paper's 1,482 count. The generated prefix mapping is explicitly **unreviewed**; the map validator requires a separately reviewed map and rejects cross-split patient leakage or conflicting labels. The investigator has approved using the observed 1,484 IDs; materializing that reviewed map and implementing the patient sampler remain next-session work. Source images can include augmented crops; tooling does not interpret suffixes as independent original radiographs.

Public auxiliary data are described in `config/public-datasets.json`; `wsp-prep download-external` verifies article version, file IDs/names, MD5, and configured byte counts before atomic download to ignored `data/external/downloads/`. GRAZPEDWRI-DX and FracAtlas are CC BY 4.0. These publicly redownloadable data and the three pinned Hugging Face repositories must not be added to DVC. `wsp-prep models` downloads exact pinned revisions using cached Hugging Face auth and writes a private SHA-256 inventory.

MURA's current official data page points to [Stanford Redivis](https://stanford.redivis.com/datasets/cv1a-apytk3j44). The doctor command checks page reachability only; it does not accept terms or download from mirrors. The investigator has confirmed research use is permitted; see `config/mura-source.json` and `docs/decisions.md`. No extra permission for third-party API use is inferred.

This tooling is acquisition/preparation only. It does not sample labels, train models, run experiments, or establish pilot readiness.

## Repair status and controlled rebuild

The initial pool and old top-level `data/locked/inventory.json` are obsolete: they lack the source-to-anonymous mapping and were not transactionally produced. The corrected real-data generation has since been rebuilt and independently validated, including all 2,993 metadata-free pool files, mapping bijection, locked-test exclusion, permissions and idempotent reuse. The old pool is quarantined. The investigator approved the observed 1,484 IDs despite the paper's 1,482 count; the generated proposal still must be materialized as a reviewed map before a sampler uses it. This tool never marks the proposal reviewed. No pilot has started.

The following reviewed rebuild already completed on this machine. Do not rerun it unnecessarily; normal `uv run wsp-prep prepare` validates and reuses the existing generation. For an intentional future rebuild (never concurrent with another preparation):

```sh
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
  uv run wsp-prep prepare --rebuild
```

This takes an exclusive preparation lock, moves the unvalidated legacy pool under private `data/locked/quarantine/` without deleting it, builds and verifies a private generation, then atomically publishes `data/pool` as a symlink to that generation's pool. A failed rebuild leaves any previously published generation intact; quarantined legacy data remains private. A normal `uv run wsp-prep prepare` validates all pool file hashes and exact mapping before reuse, and fails rather than replacing invalid data; explicitly use `--rebuild` to replace it. Old generations remain private. The current inventory and unreviewed proposal are in `data/pool/../locked/` only after resolving the symlink (e.g. `readlink -f data/pool` then use its sibling `locked`); the legacy top-level inventory is not the current receipt. The official test data remain only in the private archive and inventory, never in the pool. Mount the resolved pool directory, not its symlink or its private parent, into any future isolated workspace.

Validate an investigator-reviewed map against the current private generation inventory with `uv run wsp-prep validate-map /private/reviewed-map.json --inventory /private/current-generation/data/locked/inventory.json`. Exact prefix coverage, labels, splits, nonblank IDs, and patient consistency are required. Map validation alone is not investigator approval of the 1,484-versus-1,482 discrepancy.

TLS verification remains enabled and honors the configured trust environment. The command above explicitly uses the system CA bundle; never disable verification. All external/model acquisition jobs completed before handoff. No acquisition or preparation jobs are intentionally left running.
