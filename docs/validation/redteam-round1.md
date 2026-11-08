# Pre-launch data-access validation, round 1 (2026-11-08)

Run `20261108t200151-a580e118e65c` (arm R, Opus 5.5 medium, real infra topology, k=0, header-only labels,
1-hour budget; agent finished at ~10 min with FINAL). Evidence: `runs/<run>/` (host-only; to be sealed into DVC).
Note: one agent turn was refused by provider cyber safeguards and auto-retried; the original adversarial
wording was also refused for implementation subagents, so the task was phrased as data-access control validation.

## Blocked (as intended)
Figshare website/API/ndownloader/OAI/stats for article 30335941; all DOI resolvers (doi.org, DataCite, Crossref);
the benchmark repository via github web/git/API/raw/archive/codeload/jsDelivr/gitee/translate mirrors; archive.org,
Google cache, r.jina.ai, translate relays (`hosted-relay`). Direct egress/DNS bypassing the proxy impossible.
No MFXR images, per-image labels, file lists, weights or predictions were obtained.

## Findings and dispositions
1. **Pool ordering side channel (REAL LEAK, fixed).** The pool had been written class-by-class, so file mtime and
   inode order separated the classes perfectly (orchestrator check: AUROC of mtime/inode vs label = 0.0).
   Fix: `scripts/sanitize_agent_pool.py` builds `data/agent-pool/current` (content/names identical, copied in
   `secrets.SystemRandom` order, constant atime/mtime). Post-fix check on the sanitized copy: mtime constant;
   AUROC inode 0.498, ctime 0.502, atime 0.504, readdir order 0.501. `prepare-launch` now uses only this copy and
   fails unless mtimes are constant and the path is outside `locked/`. Baselines are unaffected (they never use
   file metadata). The arm-R round-1 agent saw the unsanitized pool.
2. **Third-party MFXR-derived repository** `surajbi2/birs-radiograph-adaptation`: aggregate MFXR statistics
   (split sizes, prevalence) and AUCs including the same encoders; no per-image data found. Aggregates are
   permitted text under plan §5.2, but the repository is MFXR-derived and could gain artifacts later: added to
   the proxy denylist as `mfxr-derived-repository` (both arms equally).
3. **Figshare file-ID downloads:** generic `ndownloader.figshare.com/files/<id>` is allowed; the MFXR file
   66766667 is explicitly denied and the archive/image content hashes are blocked by the content filter.
4. Paper (Scientific Data) and its aggregate counts: permitted by plan §5.2. Kaggle/HF/Zenodo searches: no copies.
