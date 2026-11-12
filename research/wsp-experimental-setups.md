# Experimental setups for testing weight-space programming (WSP) in radiology AI

**Status:** synthesis of the brainstorm (`01`, `02`), the search brief (`00`), eight dataset/backbone search shards (`10`–`17`), the study plan (`plan.md`) and the Phase 1 pilot results (`results/phase1-results.md`).
**Snapshot date:** 2026-11-12. **Training cutoff of the study agent (Claude Opus 5.5):** 2026-07-01.
**Method:** no new web searches were run for this document. Every dataset, link, date and count is copied from the input files. Where the inputs disagree or mark something as uncertain, this document says so. It does not settle those disagreements.

**Terms used throughout**

- **Arm F:** an Opus agent with all tools. It may train, fine-tune and calibrate the model, but it may not write weights directly.
- **Arm G:** the same agent and tools, plus *interpretability-derived direct weight edits*. Examples are ablation, rescaling, rank-1 or closed-form edits, inserted circuits, and weight arithmetic.
- **WSP:** weight-space programming, meaning arm G's direct, logged, interpretability-guided weight edits.
- **Regimes:**
  - R0: no target data;
  - R1: unlabeled target data only;
  - R2: k labeled target patients;
  - R3: abundant target labels (oracle).
- **Hypotheses H1–H7 and Null** (from `01` §0):

  | Code | WSP may help because of… |
  |---|---|
  | H1 | no or few target labels |
  | H2 | locality and low churn |
  | H3 | auditability and change control |
  | H4 | composition without data |
  | H5 | exact, known transforms |
  | H6 | removal |
  | H7 | compute and time |
  | Null | settings where F ≈ G is expected (calibration controls) |

- **Setup IDs:** S1–S44 come from `01`. S45–S56 come from `02`.
- **Dataset IDs (D01…):** each refers to a row in the master catalog (§5).

---

## 1. Executive summary

**What we found.**

- **The core finding:** genuinely new, labeled radiology data that first became public after 2026-07-01 exists, but it is scarce and mostly small.
- **What the shards found:** 45 post-cutoff entries (§5.1).
  - About 17 are *Tier A with labels*: new images **and** labels, first public after the cutoff. 12 have open or registration access; 5 are restricted or provisional. Four more Tier A image releases have no usable labels yet.
  - Most of the rest are *Tier B*: new labels, tasks, linkages, QA or synthetic images built on pre-cutoff scans. Examples are ImageCAS-X, VinDr-Ground-VQA, the MIMIC extensions, TopBrain TA36, MAMA-MIAAI, OpenBrain and HoloDATA.
  - Several entries are restricted, provisional, announced-only or unlabeled.
- **About 40 more resources are borderline** (Tier C, January–June 2026, or date-unresolved; 43 rows in §5.2). Some of the best shift datasets are in this group: TAIX-Ray, MRIxFields2026, LUMINA, PU2756, BDCXR-3257 and AMPLIFAI. The shards rejected or could not verify about 30 further leads (§5.3).
- **No Tier A dataset is large enough to resolve ΔAUROC ≈ 0.01.** CancerVerse may be the exception. RSNA Knee may also be, but it is scored through a hidden Kaggle test.
- **Clear gaps** (no qualifying dataset found):
  - multi-site diagnostic chest X-ray (CXR) with known size and labels (Naija-CXR is the only candidate, and its counts and schema are unverified);
  - pediatric data from a low- or middle-income country (LMIC);
  - multi-vendor mammography;
  - paired reconstruction-kernel CT;
  - multi-vendor cardiac MRI;
  - labeled PET or new-tracer data;
  - image + EHR (electronic health record) cohorts;
  - large image–report corpora for report generation.

**How the design handles the scarcity: a tiered contamination policy (§4).**

| Tier | Definition | Permitted use |
|---|---|---|
| A | Images and labels first public after the cutoff | Confirmatory sealed tests |
| B1 | New labels on old images that the old public labels cannot predict | Tests, with a label-leak audit |
| B2 | Re-expressed old labels, e.g. QA built from old boxes | Training, mechanistic, or secondary tests only |
| C | Released January–June 2026 | Secondary, sensitivity-flagged results only |
| D | Pre-cutoff | Source or training data only; never test |

- The policy separates two contamination channels:
  - the **agent's memory** of the target data and its published results;
  - the **backbone's pretraining overlap** with the target data.
- Starting from **post-cutoff backbones** removes a third channel: the agent's prior knowledge of the starting model's internals and published probes. Candidates are NeuroVFM, nnFoundation, NV-Reason-CT, UltraSAM3, SonoBase, HoloCT, BrainFedFM and Brain2Vec.

**Headline recommended portfolio (§9).**

- **Gate:** a known-transform positive control.
  - S12: input-pipeline inversion.
  - S15: an HU-window stem circuit (HU = Hounsfield units, the CT intensity scale).
  - Purpose: prove that the edit tooling can implement a known fix.
- **Phase 2 core:** six setups across ≥3 modalities, chosen because WSP has a plausible channel *beyond the labels* in each.

  | Setup | Problem | Dataset | Main hypotheses |
  |---|---|---|---|
  | S7/S8/S16 | Cross-hospital, cross-device fetal ultrasound | FUSEP | H1 |
  | S1/S52 (+S14) | Cross-country CXR transfer | Naija-CXR, after verification | H1, domain gap |
  | S30/S56 | Adult → pediatric CT segmentation | TotalSegmentator v3 additions | H1, H2 |
  | S24/S25 (+S11 overlay) | Add a class without forgetting | ImageCAS-X, TopBrain TA36 or CancerVerse | H2, H3 |
  | S45 | Backbone version upgrade (DINOv2 → DINOv3, or → a post-cutoff FM) | — | H4, H5 |
  | S13 | Null control | — | Null |

- **Stretch set:** CancerVerse multi-site/temporal shift; COBRA2026 CBCT vendor shift; MOPG-7 clinic onboarding with S26/S27/S39; generalist VLM → grounded CXR on VinDr-Ground-VQA; RSNA Knee report-label noise and multilingual reports (S51/S48), which reuses the planned Phase 2 data.

**The pilot changes the design.**

- In Phase 1, arm G **never used** its permission to edit weights.
- When edits were mandated (G2), the interpretability-derived head ablation **lowered** test AUROC by 0.019. Weight-averaging and task-vector amplification raised it by 0.018.
- Agent run-to-run variance was larger than any WSP effect.
- So every setup here:
  - mandates edits;
  - scores edits by reverting them;
  - compares them with random edits;
  - runs replicates.
- Every setup reports where WSP *should* help through information or constraints that labels cannot provide: unlabeled target statistics, a locality constraint, a known transform, or composition without data.

---

## 2. Pilot lessons that shape the design

The source is `results/phase1-results.md`, covering the MFXR pediatric Monteggia fracture task with a SKELEX start, k ∈ {10, 50}, and one resample per cell.

1. **Arm G ignored its permission.** The original G runs kept **no direct edits** at either k. So the formal Phase 1 gate (G > F, +0.159 at k=10 and +0.024 at k=50) measured run-to-run agent variation, not WSP. → *Arm G must be edit-mandated.* An optional "G-permitted" arm can measure whether agents choose to edit.
2. **Mandated edits did not help robustly.**
   - G2 − F = +0.060 at k=10 (wide CI, driven by a poor F run) and −0.002 at k=50.
   - G2 underperformed unconstrained G at both k.
   - The interpretability-derived head ablation cost −0.019 AUROC.
   - Soup + task-vector amplification gained +0.018.

   → *Report edit contribution per edit type.* Weight arithmetic and mechanistic edits must be distinguished (§3, P11).
3. **Agent variance dominates.** One resample per cell cannot separate WSP from agent luck. → *≥3 (ideally 5) independent agent replicates per arm × setup × regime* (P8).
4. **Agents' own validation estimates were badly optimistic.** For example, F at k=10 reported LOPO 0.92 against a test AUROC of 0.599. → *Never use agent-reported validation as evidence. Score only on sealed tests.*
5. **Agents stopped early.** Every session ended voluntarily after about 1–9 working hours of a 24-hour budget. → *Fixed working time* (P7): no early FINAL, or report time used as an outcome and compare at matched time.
6. **Transductive tricks inflate results.** G at k=50 used label-free test-time crop-group smoothing across test images, worth +0.015. → *Per-image independent scoring* (P6).
7. **Label scarcity, not representation, was the bottleneck.** The LLM-pseudo-label arm (D-ft) beat every agent run (0.911 at k=10). The scripted SAE/difference-of-means arm E was weak (≤0.71). → *WSP must be compared against the strongest non-WSP practice*, including LLM pseudo-labelling where allowed. Setups should give WSP an information channel other than labels (H1–H7).
8. **Data hygiene mattered more than method.**
   - A pool file-ordering side channel leaked labels and was caught before launch.
   - Seven test images had pHash matches to MURA that were false positives.
   - The release had 1,484 patient IDs against 1,482 in the paper.
   - Subgroup analysis (other-fracture controls) was impossible because no annotations existed.

   → *Anonymize files and ordering, audit duplicates (with manual inspection of pHash hits), and preregister subgroup annotations* (P3–P5).
9. **Provenance logs were incomplete** (calibration config, teacher ancestry). → A trusted harness records lineage. Every edit is logged as structured metadata (P12).
10. **Infrastructure noise** (rate-limit outages, stalls) changed effective time between arms. G2 ran under different conditions. → Run F and G for the same cell **concurrently** under the same quotas, and credit outages symmetrically.
11. **Small single-site tests give wide CIs.** MFXR has 1,593 test images and 491 patients. → A power analysis per setup is required. Many Tier A datasets below are pilot-only for this reason.

---

## 3. Cross-cutting design principles

These consolidate `01` §1, the shard "design guardrails" and the pilot lessons. They apply to every setup in §7 unless a setup states an exception.

### 3.1 Starting point and arms

- **P1. Same byte-identical starting checkpoint.** Each setup fixes a "deployed" model. This is usually a foundation model plus a source-site fine-tune that **we** train, not the agents. Both arms start from it: same file, same SHA-256. Results are reported relative to this checkpoint. Specialist models (for example RAD-DINO as a ceiling for DINOv3) are references, never a different start for one arm (`17` §F).
- **P2. Arm definitions.**

  | Arm | Definition |
  |---|---|
  | F | All tools and any training, but no direct weight writes. Strong baselines are part of F's playbook (P10). |
  | G (edit-mandated) | F's tools plus ≥1 kept, logged, interpretability-derived direct edit. |
  | G-permitted (optional) | The pilot-style arm; measures whether agents choose WSP. |
  | E | Edits only, no gradient steps. Needed for locked-model and no-GPU claims (S11, S53, H7). |
  | M | Mechanical WSP scripts with no agent (see below). |
  | Oracle (R3) | Not given to agents. |

  Arm M scripts: BN/LN statistic re-estimation, task arithmetic/TIES/DARE, ROME/MEMIT-style rank-1 edits, LEACE-type erasure, activation-steering bakes, fixed-rule pruning, X-Edit-style null-space edits. If agent G cannot beat M, the "agent + interpretability" claim fails.
- **P3. Definitional boundary, preregistered per setup.** BN re-estimation, temperature scaling, positional-embedding interpolation, I3D inflation and plain task arithmetic are already standard practice. For each setup, the preregistration states whether each belongs to F, to G only, or to the shared mechanical baseline. S39 needs this most explicitly.

### 3.2 Data hygiene and sealing

- **P4. Patient-level splits and near-duplicate removal.**
  - Use perceptual hash plus embedding cosine across train, dev and test, and against every Tier D source dataset either arm may download.
  - Manually inspect hits (pilot: pHash false positives).
  - Publish the dedup audit before agents run.
  - Many Tier A releases lack patient IDs (FUSEP, MOPG-7, DentalOPG-1550, Naija-CXR, VinDr-Ground-VQA). For these, patient grouping must be reconstructed or the limitation declared.
- **P5. Sealed tests with technical enforcement.** The plan §5.2 stack is reused:
  - a container with a single proxy exit;
  - a full-URL denylist;
  - content hashing (SHA-256 and perceptual) of downloads and the workspace;
  - fetch-provider restrictions;
  - a red-team test.

  Agents get only the k-label dev pool and, per regime, unlabeled target data. Files are renamed and stripped of folder structure and ordering (pilot side channel). The denylist covers the target dataset, its mirrors, its benchmark code, published predictions, and weights trained on it. Example: the TopAneu TA36 docker is trained on post-cutoff labels.
- **P6. Per-image (or per-study) independent scoring.**
  - No transductive or test-batch effects. BN runs in eval mode with frozen statistics.
  - No test-time hyperparameter selection.
  - One submitted model, plus an optional preregistered fallback scored separately.
  - TTA-style setups (S8) allow adaptation only on a separate unlabeled target pool, frozen before test.
- **P7. Fixed working time.**
  - Each session has a fixed wall-clock and GPU budget.
  - Early FINAL is either disallowed (sessions run to deadline) or the time used is recorded and the comparison is made at matched elapsed time.
  - F and G for the same cell run concurrently with identical GPU share and rate limits. Outages are credited symmetrically.

### 3.3 Statistics

- **P8. Replicates and power.**
  - ≥3 (ideally 5) independent agent runs per arm × setup × regime, with different k-shot resamples.
  - CIs come from bootstrap over test patients, nested in replicates.
  - Report between-run variance.
  - Size test sets so that the 95% CI on ΔAUROC is ≤ ±0.01–0.015. This typically needs ≥1,000–3,000 test studies with ≥150–300 positives. Segmentation needs ≥50–100 test volumes per target site.
  - Report the minimum detectable effect.
  - Datasets below these sizes are labelled **pilot/mechanistic** in §7.
- **P9. Preregistration and decision rule.** Each setup registers its primary metric, guardrails, k grid, regimes and the margins below *before* any run.

  **Default decision rule (adapt the margin per metric):**
  - **WSP helps (performance)** when all of these hold:
    - (a) G − F ≥ margin (ΔAUROC/ΔDice/ΔmAP ≥ 0.02), with the replicate-nested CI excluding 0;
    - (b) edit contribution (G − G-with-edits-reverted) ≥ 0.01 with CI > 0;
    - (c) G beats the matched random-edit control;
    - (d) guardrails (source retention, worst-group, calibration) are no worse than F by more than the non-inferiority margin (default 0.005–0.01).
  - **WSP helps (locality)** when G is non-inferior to F on the primary metric (within 0.01) **and** has ≥50% less churn or diff footprint, or a better blinded auditability rating.
  - **WSP doesn't help** when the G − F CI lies within ±margin, or edit contribution ≤ 0, or random edits match the interpretability-guided edits.
  - **WSP harms** when G − F is negative beyond the margin, or the guardrails fail.

### 3.4 Parity and controls

- **P10. Compute, label, token and data parity.**
  - Equal GPU-hours, wall-clock, agent token/turn budget, label budget, unlabeled pool and external data allowances.
  - Also run a **low-compute regime** (1 GPU-hour or CPU-only) where retraining is barely possible (H7).
  - F's playbook must be strong: LP, LP-FT, LoRA, BitFit, BN adaptation/TENT/SHOT, pseudo-labelling (including Opus image reading, the pilot's strongest arm D-ft, if preregistered as allowed; §10 item 18), mixup, MONAI/TorchIO intensity and artifact augmentation, class-balanced losses, temperature scaling, continued SSL, replay/LwF/EWC, distillation and noise-robust losses.
- **P11. Edit-contribution ablation and random-edit control.**
  - For every final G model, revert each logged edit individually and all together, keep G's training, and re-score.
  - A random-edit control applies edits at the same tensors with the same norms, but random directions or units.
  - Report weight-arithmetic edits (soups, task-vector scaling) separately from mechanistic edits (ablation, rank-1, inserted circuits, projections). The pilot showed they behave differently.
- **P12. Provenance and audit.**
  - A trusted harness records the checkpoint lineage.
  - Each edit is logged with: target tensor, operation, magnitude, interpretability evidence and rationale.
  - An independent read-only auditor checks that F made no direct edits and that G's edits are what was claimed.
  - Change logs use a normalized format so that blinded reviewers (a radiologist and a regulatory reviewer) can rate auditability (S11).

### 3.5 Metrics

- **P13. Multi-axis scorecard.**
  - (a) target performance: AUROC/AUPRC, Dice/HD95/NSD, mAP, FROC/CPM, MAE, PSNR/SSIM, RadGraph-F1/GREEN, macro-F1;
  - (b) source/retained performance;
  - (c) worst-site and worst-subgroup performance;
  - (d) calibration: ECE, Brier, threshold sensitivity/specificity;
  - (e) **churn**: the fraction of reference-set predictions that flip relative to the starting checkpoint;
  - (f) diff footprint: number and fraction of changed parameters, ‖Δθ‖;
  - (g) time-to-fix and compute;
  - (h) blinded auditability and reversibility ratings;
  - (i) stability: the failure rate (runs worse than the start), which is critical for S8.

  Gains in AUROC are reported separately from gains in threshold choice or calibration (plan §8.3).

### 3.6 Practice and compliance

- **P14. Practitioner realism note.** Each setup states whether a practitioner would actually solve the problem this way. For S12, the realistic fix is the preprocessing.
- **P15. Licence compliance.**
  - Some datasets and checkpoints are no-derivatives or non-commercial: SKELEX (CC BY-NC-ND), CancerVerse (CC BY-NC-ND), CheXagent (CC BY-NC-ND), and NeuroVFM, Mammo-FM and DINOv3 (custom terms).
  - For these, publish edits or weight diffs and do not redistribute modified checkpoints. Obtain legal review before deriving models from ND data.
- **P16. Negative results are results.** A finding that WSP gives ≤0.01 almost everywhere but wins on churn or auditability is useful guidance for practitioners. The portfolio includes null-leaning setups (S13, S29, S34, S21) to calibrate claims.

---

## 4. Contamination and eligibility policy

### 4.1 Two contamination channels, plus one design option

1. **Agent memorization.** Opus 5.5 may have seen pre-cutoff images, labels, benchmark splits, leaderboards and published per-image results. This is controlled by the dataset **release tier** below and by the proxy denylist (P5).
2. **Backbone pretraining overlap.** The starting model may have trained on the test images. For example, RAD-DINO was pretrained on MIMIC-CXR, CheXpert, NIH-CXR, PadChest and BRAX. UltraSAM3 used 37 public ultrasound sets. NV-Reason-CT used CT-RATE and CancerVerse. This channel is independent of release date. It is controlled by a **source-to-target overlap matrix** built from each backbone's disclosed pretraining list (§6), plus dedup (P4). Missing disclosure counts as uncertainty, not as clean.
3. **Agent knowledge of the backbone's internals (design option).** A WSP agent may know published probes, SAE features or editing results for pre-cutoff backbones such as DINOv3, MedCLIP (MedSAE) or Mammo-CLIP (Mammo-SAE).
   - Starting from a **post-cutoff backbone** removes this prior. Candidates: NeuroVFM (2026-07-10), UltraSAM3 (2026-07-30), SonoBase (2026-08-21), nnFoundation (2026-09), NV-Reason-CT (2026-09-23), Brain2Vec (2026-10), BrainFedFM (2026), MRI_BreastSeg (2026-10), HoloCT-4B/8B (2026-11-04).
   - Running the same setup with a pre- and a post-cutoff backbone tests whether G's advantage depends on literature knowledge.
   - Caveats:
     - fresh backbones still pretrain on old public data (overlap channel 2);
     - several have unclear or non-commercial licences;
     - 3D and VLM models are often not fine-tunable on 24 GB.

### 4.2 Tiers

| Tier | Definition | Allowed roles | Examples |
|---|---|---|---|
| **A** | Images **and** labels first publicly available on or after 2026-07-01 (data-file date, not paper date) | Sealed confirmatory test; target dev pool; unlabeled target pool | MFXR, Naija-CXR, FUSEP, MOPG-7, DentalOPG-1550, CancerVerse, COBRA2026, TopAneu batch 2 (centers 1/2/4), TotalSegmentator CT/MRI v3 *additions*, RSNA Knee 2026 |
| A-r | Tier A but restricted, DUA or safeguarded access | As A, once access is granted | XQA-Chest (CUH), longitudinal liver-metastasis CT, BoneLoss-PAN769, CLEAR-EC (non-radiology) |
| A-p | Tier A but the first-access date is provisional | As A only after date confirmation; otherwise treat as C | LUCQUE (PARADIM model-to-data) |
| A-u | Post-cutoff images without usable labels yet | Unlabeled target pool (R1), or a test after **new local annotation** | CMB V25 additions, TAIR first tranche, EPFL/Open-H-RF raw RF |
| **B1** | New post-cutoff labels or tasks on pre-cutoff images, where the **new label is not predictable from old public labels** of those images | Test allowed, with a label-leak audit (old labels denylisted; check correlation between old and new labels) | TopBrain TA36 new infraclinoid classes; Spinal-MM trabecular masks; MAMA-MIAAI whole-breast masks; ImageCAS-X 18-segment tree labels (partly predictable from old lumen masks: audit) |
| **B2** | Post-cutoff labels that **re-express old labels or reports**: QA from old boxes, NLP linkage, model-generated masks | Training data, mechanistic studies and secondary tests only; never the sole confirmatory test | VinDr-Ground-VQA, MIMIC-Ext-CXR-QBA, MIMIC-CXR-DB, CheXmask-U, OpenBrain, HoloDATA, REFLACX discrepancy tables |
| B-syn | Post-cutoff synthetic images from generators trained on pre-cutoff data | Augmentation or audit only; never a test | SECURED, CompDiff |
| **C** | Data first public 2026-01-01 → 2026-06-30 | Secondary or sensitivity analyses, flagged; replication of Tier A results; source data | TAIX-Ray, MRIxFields2026, LUMINA, PU2756, BDCXR-3257, AMPLIFAI, RadM-Bench |
| **D** | Pre-cutoff | **Source/training/pretraining data only, never a test** | CheXpert, MIMIC-CXR, PadChest, VinDr-CXR, MURA, GRAZPEDWRI-DX, M&Ms, AMOS, LIDC, autoPET, etc. |

### 4.3 Rules

1. **The confirmatory test set of every setup must be Tier A (or A-r / A-p once confirmed), or B1 with an audit.** If no such dataset exists, the setup is run only as a **Tier C/D mechanistic study**, labelled as contaminated, or it waits (§9.4).
2. **Mixed releases are split by provenance.**
   - TotalSegmentator v3: only the images added in v3, isolated by ID diff, are Tier A. The 1,228 CT and 616 MRI v2 images are Tier D.
   - TopAneu: centers 1/2/4 batch 2 (250 scans) are Tier A. The 68 center-5 scans re-use INSTED/OpenNeuro and are Tier D. Batch 1 (2026-06-15) is Tier C.
   - XQA-Chest: the CUH 650 cohort is A-r. The 735 re-annotated MIMIC studies are B2.
   - radiology-conflict: only the 22 languages added 2026-07-06 are post-cutoff, and their underlying 100 images are of unknown age.
3. **Paper date ≠ data date.** Known traps:
   - TAIX-Ray: paper post-cutoff, files February 2026.
   - AMPLIFAI: files June 2026, paper August.
   - PU2756: Figshare 2026-06-15, paper 2026-07-04.
   - BreastDCEDL and AMYPAD: 2026 papers on 2025 or v202306 data.
   - Longitudinal melanoma CT: 2025 data.
4. **Freeze snapshots.** Pin version and SHA-256 for the following:
   - CancerVerse: v3.0 → v3.5 → v3.5.1 changed counts and time offsets.
   - DentalOPG-1550: v2 vs v3 box counts.
   - TotalSegmentator v3.
   - Open-H-RF: staged release.
   - Kaggle/RSNA files.
5. **Denylist all public copies of Tier A/B targets and their label sources**, as in the plan (MFXR). For B1, also denylist the old labels of the same images, for example the old ImageCAS labels when using ImageCAS-X.
6. **Hidden-test resources are preferred** where they exist. RSNA Knee is scored by Kaggle late submission. The COBRA validation/test labels will not be released until 2032, so they are unusable. The TopAneu center-3 test is organizer-held.
7. **Synthetic, manifest-only and announcement-only records are never counted as test data.** These are SECURED, CompDiff, SonoCorpus, MetaStructAtlas (preview), BIG-MRI and VLM3D (PDF).

---

## 5. Dataset catalog

**Conventions.**

- **"Src"** is the input file that reported the entry (`10`–`16`, or `plan`).
- **Tier** follows §4.2.
- **Readiness codes:**
  - **RN:** runnable now (open download);
  - **RA:** needs access, DUA or credentials;
  - **RV:** needs verification (schema, date or counts);
  - **RX:** needs new annotation;
  - **NR:** not runnable now.
- **"Setups"** lists the S-numbers the shards (or this synthesis) attach to the dataset.
- Counts and links are as given in the shards. "?" marks something the shard could not verify.

### 5.1 Master table: post-cutoff datasets and extensions (Tier A, A-r, A-p, A-u, B1, B2, B-syn, conditional)

| ID | Name and link(s) | Release date (evidence) · Tier | Modality / anatomy | Task / labels | Size | Sites / vendors / metadata | Access / licence | Test-set status | Contamination notes | Setups | Ready | Src |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D01 | **MFXR** (Monteggia fracture X-ray) [paper](https://www.nature.com/articles/s41597-026-07547-y), [data](https://doi.org/10.6084/m9.figshare.30335941) | 2026-07-18 (plan) · **A** | Pediatric forearm radiographs | Binary Monteggia vs control (controls include other fractures); orthopedist label + 2nd-surgeon verification | 4,586 images; 1,482 patients (paper) vs 1,484 IDs (release); official split 993/491 patients | 1 hospital (Shenzhen Children's), China | CC BY 4.0 | Official patient-level test split (1,593 images, ~63% positive), sealed by us | **Already used in Phase 1** (our pilot outputs are not agent-visible, but the study team has seen results). Benchmark code repo denylisted. pHash checks vs MURA gave false positives only | S22, S23, S30, S10, S12, S13, S54, S41 | RN | plan, pilot |
| D02 | **Naija-CXR** [Zenodo v1.1](https://doi.org/10.5281/zenodo.21781842), [API](https://zenodo.org/api/records/21781842) | 2026-08-04 (Zenodo API publication_date; archive attached) · **A** (RV) | Frontal CXR + reportedly radiologist reports + expert annotations | Classification / report / VLM; **label ontology, granularity and counts not stated** | ? (single 389.3 MB ZIP) | Nigerian hospital source(s) (RSFUTH Dutse among creators); site count, devices and dates not documented; demographics "where available" | Open download; metadata CC BY 4.0 **but** prose says non-commercial research/education only (conflict) | No official split; labels released | No stated overlap; dedup against public CXR and Nigerian benchmarks required | S1, S7, S52, S14, S8, S13, S31, S35, S36, S41, S28, S12 | RV | 10 |
| D03 | **XQA-Chest** [ReShare record](https://reshare.ukdataservice.ac.uk/858610/), [README](https://reshare.ukdataservice.ac.uk/858610/11/README.md), [DOI](https://doi.org/10.5255/UKDA-SN-858610), [paper](https://arxiv.org/html/2607.26333) | 2026-08-26 (repository record) · **A-r** (CUH cohort); **B2** (735 MIMIC re-annotations, inclusion unconfirmed) | Frontal CXR (AP/PA) | XQA-RR: 14 CheXpert-style findings; separate image-derived and report-derived expert labels (neg/uncertain/pos; report adds "not mentioned"); optional boxes. XQA-IQA: 4-point expert usability on original + controlled degradations | RR: 650 studies with paired reports (CUH). IQA: 323 references + 1,571 degraded variants. (+735 MIMIC per paper) | 1 UK trust (Cambridge), acquired 2019–2021; vendor and demographics not exposed | UK Data Service safeguarded access; End User Licence | Labels released to approved users; no hidden test; **underpowered** for ≤0.01 AUROC | CUH images new; MIMIC subset overlaps pre-cutoff MIMIC | S51, S13, S8, S38, S40, S41, S35, S31, S43 | RA | 10 |
| D04 | **CheXmask-U** [PhysioNet v1.0.0](https://www.physionet.org/content/chexmask-u/1.0.0/), [DOI](https://doi.org/10.13026/6vn3-3j51), [preprint](https://arxiv.org/abs/2512.10715) | Sep 2026 (PhysioNet page gives 2026-09-02) · **B2** | CXR (annotations only) | Lung/heart masks, landmarks, per-node uncertainty, RCA quality estimates (not disease labels) | 657,566 images' annotations (NIH 112,120; CheXpert 187,825; MIMIC-JPG 243,334; PadChest 96,287; VinDr 18,000); **no images** | Inherited: US, Spain, Vietnam | PhysioNet; source images under each parent's terms; licence unverified | No hidden test; RCA is a proxy | **Complete image overlap** with 5 pre-cutoff sets; mask model trained on overlapping sources | S8, S11, S32, S41, S51 | RA | 10 |
| D05 | **MIMIC-Ext-CXR-QBA** [PhysioNet v1.0.1](https://physionet.org/content/mimic-ext-cxr-qba/1.0.1/), [DOI](https://doi.org/10.13026/hne5-7t85), [ICLR 2026](https://openreview.net/forum?id=LrmyW9JLYq) | 2026-08-25 (PhysioNet) · **B2** | MIMIC frontal/lateral CXR | Scene graphs, regions, boxes, hierarchical VQA; 310 region types, 237 finding entities | 42,172,827 QA pairs from 227,827 reports / ~377,110 images (subsets: 31.2M pretrain, 7.5M fine-tune); no images | 1 US system (BIDMC); MIMIC metadata | Credentialed PhysioNet + DUA | Published splits; automatic answers are not gold | Wholly derived from pre-cutoff MIMIC | S24, S47, S17, S43 | RA | 10 |
| D06 | **MIMIC-CXR-DB** [PhysioNet v1.0](https://physionet.org/content/mimic-cxr-ext-mimic-cxr-db/1.0/), [DOI](https://doi.org/10.13026/gy0s-e371) | 2026-10-01 · **B2** (linkage) | CXR IDs + EHR linkage | Report-derived findings, admission diagnoses, demographics, labs; NLP/NER (not expert-validated) | 377,095 radiographs considered; 227,827 studies; 146,333 images linked to admissions | 1 Boston site; timestamps (date-shifted), view, DICOM fields, demographics | Credentialed + DUA | No sealed test | All images pre-cutoff MIMIC | S9, S13, S53, S28, S44, S51 | RA | 10 |
| D07 | **MOPG-7** [Mendeley v1](https://data.mendeley.com/datasets/t66ytdrhf2/1), [v2](https://data.mendeley.com/datasets/t66ytdrhf2/2) | 2026-09-16 (v1; v2 2026-09-17) · **A** | Dental panoramic (OPG) | Detection, 7 categories (missing teeth, crown, root canal, caries, wisdom teeth, broken-down teeth, healthy); YOLO/COCO | 2,095 images; 9,834 expert-validated boxes; patients ? | 4 Bangladesh centers (1,433 / 533 / 114 / 15 images); vendor ?; `image_metadata.csv`, `split_assignments.csv` (fields to verify) | Public Mendeley; licence not apparent | Released train/val/test splits; confirm patient-level | Possible relation to other Bangladesh dental releases; dedup with D08 | S1, S7, S14, S26, S27, S39, S21, S32, S34, S52 | RN (licence check) | 10 |
| D08 | **DentalOPG-1550** [v1](https://data.mendeley.com/datasets/rtt726b26d/1), [v2](https://data.mendeley.com/datasets/rtt726b26d/2), [v3](https://data.mendeley.com/datasets/rtt726b26d/3) | v1 2026-09-01 (raw images); annotated v2 2026-09-29, v3 2026-10-02 · **A** | Dental OPG | YOLOv8 boxes, 14 categories (caries, periodontitis, apical abscess, impactions, restorations, teeth, normal…) | 1,550 raw; v3 1,525 annotated / 14,497 objects (1,068/303/154 split); v2 reported 10,141 boxes (version conflict) | 1 diagnostic centre; country unverified (reviewer in Bogura, Bangladesh); no vendor or demographics | Public Mendeley; licence not stated; v3 images auto-oriented and stretched to 640×640 | Released split; 154-image test is small | Unknown overlap with local releases; dedup with D07 | S10, S14, S22, S34, S21, S41 | RN (licence check) | 10 |
| D09 | **BoneLoss-PAN769** [Zenodo v1](https://doi.org/10.5281/zenodo.21114193), [v2](https://doi.org/10.5281/zenodo.21939261), [versions API](https://zenodo.org/api/records/21939261/versions), [code](https://github.com/thiagoavieira/boneloss-inference) | v1 2026-07-01, v2 2026-08-14 (record only) · **A-r** | Dental OPG | Crown instance polygons (18,809) + 769 alveolar-ridge polylines | 769 radiographs (ages 14–81, ~60% female) | InReDD, Brazil; Morita Veraviewepocs; age/sex in metadata | Metadata CC BY 4.0 but `restricted`, **no files**; request via [InReDD portal](https://inredd.com.br/en/solutions/open-data) | None documented | Extends InReDD collection | S25, S32, S28 | NR / RA | 10 |
| D10 | **SECURED synthetic female CXR** [Zenodo](https://zenodo.org/records/21112411), [API](https://zenodo.org/api/records/21112411) | 2026-07-01 · **B-syn** | Synthetic 256² CXR | None documented | ? (70.1 MB) | Generator trained on ChestX-ray14 | CC BY 4.0 (metadata) | None | Derived from pre-cutoff data; may reproduce training content | S28, S32 (augmentation only) | RN (low value) | 10 |
| D11 | **CompDiff synthetic CXR** [natural 62,094](https://doi.org/10.5281/zenodo.23339629), [balanced 415,072](https://doi.org/10.5281/zenodo.23339643), [paper](https://arxiv.org/abs/2603.16551), [weights](https://huggingface.co/mahmoudibra98/compdiff-chest-xray) | 2026-10-27 · **B-syn** | Synthetic PA CXR 512² | Conditioning prompt, 14 CheXpert labels, sex/race/age group (inherited, not annotations) | 62,094 + 415,072 images (18 GB + 121.9 GB) | Generator trained on MIMIC | Open Zenodo; licence + MIMIC terms to confirm | Training corpora only | MIMIC-derived prompts and labels; memorization risk | S28, S32 (with a real sealed test) | RN (augment only) | 10 |
| D12 | **CancerVerse** [HF dataset](https://huggingface.co/datasets/BodyMaps/CancerVerse), [MICCAI 2026](https://papers.miccai.org/miccai-2026/paper/0562_paper.pdf) | v3.0 first public **July 2026** (day not stated; v1/v2 internal); v3.5 Sep; v3.5.1 Oct (time-offset fix) · **A** | 3D CT chest/abdomen/pelvis | Voxel tumor masks for 13 cancer types; patient-level confirmation; reports, pathology, clinical variables | HF: 24,422 scans / 14,599 patients (paper: 24,168 / 13,863); 12,529 annotated scans; 8,799 verified healthy; 1–32 scans per cancer patient; ~3 TB | Multiple hospitals, Switzerland + Turkey (count ?); 2010–2025; per-scan slice thickness/spacing/kernel when available; demographics linked | HF public, academic; **CC BY-NC-ND 4.0** (legal review for derived models) | Paper split 11,091/2,772 patients; labels **released** (seal ourselves) | No known overlap with old benchmarks, but not exhaustively audited; **NV-Reason-CT pretrained on CancerVerse** | S1, S5, S7, S8, S9, S13, S15, S19, S22, S23, S24, S25, S28, S34, S39, S44, S54, S55, S56 | RN (licence) | 11 |
| D13 | **COBRA2026** raw CBCT projections [Zenodo](https://zenodo.org/records/21322350), [API](https://zenodo.org/api/records/21322350), [paper](https://arxiv.org/html/2607.20037), [challenge](https://cobra2026.grand-challenge.org/) | 2026-07-13 (Zenodo; training release) · **A** | Pelvic radiotherapy CBCT projections + recon + registered planning CT | Reconstruction / correction (no diagnostic labels); masks/FOV | 867 cases (692 / 52 / 123); ~950 GB (train ~750 GB) | 6 European centers (DE, NL, FR, AT); **Elekta + Varian**; planning CT on Philips/Siemens/Toshiba/Canon; per-case center ID and acquisition XML/YAML; age/sex partial | Open, no registration; **CC BY-NC 4.0** | Val/test downloads dated **2032** (effectively hidden); use train for our splits | New collection; planning CT is deformably registered (not perfect truth) | S5, S7, S8, S12, S15, S26, S27, S39, S40, S49 | RN (patch subset) | 11, 16 |
| D14 | **CBCT-IQ** phantom benchmark [Zenodo](https://zenodo.org/records/20124496), [arXiv](https://arxiv.org/abs/2607.29253) | 2026-07-29 (Zenodo files) · **A** (phantom) | 2D CBCT slices, thorax and pelvis phantoms | 4-level overall + ROI image-quality scores from 3 experts | 36 volumes, 1,764 annotated slices; no patients | 1 Siemens ARTIS pheno C-arm; 60/90/125 kV; 4 pulse widths; 3 recon types | Open; CC BY 4.0 | Released; split by volume and acquisition | Strong within-source dependence | S12, S40, S49 | RN | 11 |
| D15 | **ImageCAS-X** [Zenodo](https://zenodo.org/records/21887809), [paper](https://arxiv.org/html/2608.30404), [project](https://kitbransby.github.io/ImageCAS-X/) | 2026-08-11 (labels + weights) · **B1** (partly predictable from old lumen labels: audit) | CCTA, coronary | Lumen masks, 18-segment tree labels, centerlines, meshes; scan-level disease, dominance, image quality | 800 patients (560 / 80 / 160; test re-annotated independently) | 1 center (Guangdong), Siemens 128-slice dual-source | Labels CC BY 4.0; images from ImageCAS/Kaggle under their terms | Released test labels | **Complete image overlap** with 2023-era ImageCAS; denylist old labels | S24, S25, S32, S33, S56, S15 | RA (images via Kaggle) | 11 |
| D16 | **TotalSegmentator CT v3** [Zenodo](https://zenodo.org/records/22688904), [code](https://github.com/wasserth/TotalSegmentator) | 2026-09-10 (v3.0.0) · **A** for v3 additions (+291 pediatric); D for the 1,228 v2 images | Whole-body CT | 117 structure masks (v3 also refines old labels) | 1,939 images (from 1,228); 291 pediatric added; patients ? | "Wide range" of scanners and institutions; counts and per-image metadata not stated | Open 37.4 GB; **licence field not visible: verify** | No hidden test | v2 images fully pre-cutoff; isolate additions by ID diff; TotalSegmentator models trained on v2 | S2, S7, S8, S15, S18, S24, S25, S30, S33, S41, S56 | RN (licence) | 11 |
| D17 | **Longitudinal abdominal CT, liver + metastasis masks** [Zenodo](https://zenodo.org/records/23349228) | 2026-10-13 · **A-r** | Contrast-enhanced abdominal CT | Liver + metastasis masks; registration, tracking, response | 118 exams / 54 patients (T0/T1/T2) | Single source (site not clearly named); metadata CSV with acquisition/dose, sex, quality, timepoint (days from baseline) | Files **restricted**; CC BY 4.0 | No hidden split | Record ID 23349228 (landing) vs 23349229 (file link): verify | S5, S9, S24, S25, S40, S44, S55, S56 | RA | 11 |
| D18 | **Spinal-Multiple-Myeloma-SEG trabecular extension** [Zenodo](https://zenodo.org/records/21628233), [TCIA](https://www.cancerimagingarchive.net/collection/spinal-multiple-myeloma-seg/), [paper](https://doi.org/10.59275/j.melba.2026-d741) | 2026-07-27 (masks only) · **B1** | Dual-energy low-dose spine CT | Trabecular-bone masks L1–L5 (L6) | 71 of 72 exams; 67 patients | TCIA collection; sites and vendors unverified | Masks on Zenodo (CC BY 4.0 indicated); CT via TCIA terms | Released | 100% image overlap with TCIA cohort | S2, S8, S24, S25, S33, S49, S56 | RN | 11 |
| D19 | **LUCQUE** Québec LDCT screening [arXiv](https://arxiv.org/abs/2611.12817), [PARADIM](https://paradim.science/actifs-sous-gestion/) | arXiv 2026-11-09; **first data-access date unverified** · **A-p** | Low-dose chest CT | Voxel nodule + cyst masks; Lung-RADS characteristics | 1,678 baseline studies / participants; 1,776 nodules, 60 cysts (PARADIM page lists 3,000 participants: reconcile) | Québec, Canada; sites and vendors ?; demographics + imaging parameters in paper | **Model-to-data only** (no image export); terms ? | Evaluation via platform | No known overlap with LIDC/NLST | S1, S5, S8, S10, S34, S41, S49, **S53**, S46 | RA / RV | 11, 15 |
| D20 | **Processed patch-level lung nodule CT** [Zenodo](https://doi.org/10.5281/zenodo.22926100) | 2026-09-23 · **B2** (low priority) | 2.5D 64×64×3 CT patches | Non-nodule / benign / malignant | Counts unverified | Inherits LUNA16 / LIDC-IDRI / LNDb | Open; licence to check | Packaged labels | **Exact source overlap**; severe contamination | S5, S22, S34 | RN (not recommended) | 11 |
| D21 | **CTSpinoPelvic1K v7** [Zenodo](https://zenodo.org/records/22242745) | v7 2026-09-02; which fields are new is unclear · **B (conditional)** | CT spine/pelvis | New annotation / mapping labels | 802 old TCIA CT records | Inherited | Licence to verify | ? | Old TCIA images | S25, S33 | RV | 11 |
| D22 | **MOOSE / TotalSegmentator masks for CPTAC/CMB CT** [Zenodo](https://zenodo.org/records/23825859) | 2026-11-02 · **B2 (AI-derived)** | CT | AI-derived anatomy masks / radiomics | Counts ? | Pre-existing TCIA cohorts | ? | ? | Patient-level overlap to inspect | S51, S25 | RV | 11 |
| D23 | **TopAneu 2026, Batch 2** [data page](https://topaneu-26.grand-challenge.org/data/), [SwitchDrive](https://drive.switch.ch/index.php/s/O36U43RkChkNcHd) | Batch 2 2026-07-31 · **A** for 250 clinical scans (center 1 MRA 199; center 2 CTA 47; center 4 CTA 4); **D** for 68 center-5 scans (INSTED/OpenNeuro); Batch 1 (2026-06-15) = C | 3D TOF-MRA + CTA, intracranial arteries | Aneurysm location (multiclass), type (saccular / dissecting / fusiform), JSON locations; vessel masks are organizer predictions (silver) | Full bundle 415 scans / 408 patients; batch 2 adds 318 | CHUV, HUG (CH), Mie-Chuo (JP), public center 5; center 3 (UMC Utrecht) held for test; center ID per scan; vendor ? | Non-commercial research, attribution | Center-3 test organizer-held | TopBrain labels feed TopAneu vessel predictions (not independent); 7 center-4 longitudinal patients (order not chronological) | S7, S8, S10, S18, S22, S26, S34, S55, S56, S6 | RN | 12 |
| D24 | **TopBrain TA36 label release** [Zenodo v3](https://zenodo.org/records/21972006), [challenge](https://topbrain2026.grand-challenge.org/) | 2026-08-17 · **B1** (new 36-class schema incl. 2 new infraclinoid classes) | CTA + MRA, Circle of Willis | 40 CTA / 42 MRA class maps + modality-agnostic 36-class map | 50 volumes (25 CTA–MRA pairs), ~1.96 GB | Sites and vendors not specified | Non-commercial; attribution | Training release; challenge test hidden | Images = TopCoW 2025; labels 1–12, 15 carried over; **TA36 docker (2026-08-15) trained on these labels** | S24, S25, S2, S18, S33, S26, S22 | RN | 12, 16 |
| D25 | **TotalSegmentator MRI v3** [Zenodo](https://zenodo.org/records/22688334) | 2026-09-10 (v3.0.0) · **A** for v3 additions; D for 616 v2 images | Whole-body + regional MRI | 50 structures (provenance / review not fully specified) | 1,296 images (+680: 246 whole-body, 249 pediatric, 170 previously failed; 15 unreconciled) | Heterogeneous clinical + IDC sources; `meta.csv` | Open; **CC BY 4.0** | No hidden test | IDC sources may predate cutoff; dataset trains the linked model | S6, S7, S18, S25, S30, S32, S50, S56 | RN | 12 |
| D26 | **MAMA-MIAAI "Here We Go Again"** [PhysioNet](https://physionet.org/content/mama-miaai-herewegoagain/1.0.0/), [DOI](https://doi.org/10.13026/w6wc-jh81), [model](https://github.com/FloXyPython/MRI_BreastSeg), [repo](https://github.com/FloXyPython/MAMA-MIAAI) | 2026-10-07 · **B1** (new masks + bias-corrected images on old scans) | Breast DCE-MRI | Whole-breast segmentation: 94 manual + 1,506 auto masks; bias-field-corrected volumes | 1,506 cases (DUKE 291, ISPY1 171, ISPY2 980, NACT 64); ~30 manual holdout | Multi-center, heterogeneous; cohort and timepoint recoverable | PhysioNet registration; CC BY-NC 4.0 | All manual masks released | Raw MRI = MAMA-MIA (pre-cutoff) | S6, S8, S14, S15, S50, S51, S33 | RA (registration) | 12 |
| D27 | **OpenBrain** [HF](https://huggingface.co/datasets/lanqz7766/OpenBrain), [arXiv](https://arxiv.org/abs/2611.05348), [code](https://github.com/lanqz7766/openbrain) | HF lastModified 2026-11-06 (first public snapshot) · **B2** (model-generated labels) | T1w brain MRI | 110-region generated parcellations (96-label eval space), committee parcellations, brain masks, 7 QC/risk fields | 35,838 scans/sessions from 607 OpenNeuro datasets | Age/sex/scanner/field strength when present | Public, ungated; **CC0** | No hidden test; paper's IXI / BrainLat / Mindboggle evaluation external | All raw scans public pre-cutoff | S7, S25, S32, S39, S51, S6, S41 | RN | 12 |
| D28 | **CFB-GBM v2.0** [MELBA](https://www.melba-journal.org/papers/2026:038.html), [TCIA](https://www.cancerimagingarchive.net/collection/cfb-gbm/) | MELBA 2026-09-21; **TCIA upload date unverified** · **B1 (conditional)** | Multiparametric brain MRI + planning CT/RTDOSE | GBM GTV masks (35% → 97% complete), brain masks, radiomics, **RANO 2.0** response pairs | 264 patients, t0/t1/t2 | 1 French center; Siemens 1.5T/3T; time-difference metadata | TCIA terms to confirm | No hidden test | Same 264 MRI cases in v1 (pre-cutoff) | S6, S9, S33, S46, S55, S50 | RV | 12 |
| D29 | **OpticNerveSeg** [Sci Data](https://www.nature.com/articles/s41597-026-08538-9) | Article 2026-11-05; **no artifact URL found** · **B1 (conditional)** | HCP MRI | Optic nerve / chiasm / tract masks | 151 subjects | HCP | ? | ? | HCP raw scans pre-cutoff | S25 | NR | 12 |
| D30 | **FUSEP** fetal US [GitHub](https://github.com/ahuteam/FUSEP), [arXiv](https://arxiv.org/abs/2608.04766), [Drive archive](https://drive.google.com/file/d/1HwY0p5Hw6eiZdgRAUTVy2sDSVqzr2vp8/view?usp=drive_link) | 2026-09-09 (first README commit with working full-data link) · **A** | B-mode fetal US, first trimester (CRL, NT views, 11–14 weeks) | Detection: 45,820 expert boxes, 14 anatomical structures | 4,017 images; patients not reported | 3 hospitals (Shenzhen, Chengdu, Kunming), 3 brands (Samsung, SonoScape, GE); domain labels and splits | Drive link; code Apache-2.0; data terms "research purposes" (not explicit) | Released per-hospital splits; no hidden test | No prior source claimed; repo model zoo must be denylisted; **FADA (C) annotates FUSEP images** | S7, S8, S16, S26, S27, S32, S39, S45, S2(analog), S34, S42 | RN | 13 |
| D31 | **Open-H-RF** [HF](https://huggingface.co/datasets/nvidia/Open-H-RF), [GitHub](https://github.com/open-h/Open-H-RF), [catalogue](https://open-h.github.io/Open-H-RF/), [arXiv](https://arxiv.org/abs/2610.13616) | Sep 2026 earliest (staged; v1.0 snapshot Oct) · **A-u (mixed)** | Pre-beamformed US channel / RF (zea HDF5), many anatomies | Beamforming / recon / RF representation; subset-specific labels | 19,471 files, 39.07 TB, 33 subdirectories | 29 contributing organizations; subset cards | CC BY 4.0 top-level; check subsets | No global test | Community aggregation; some subsets may be pre-cutoff | S16, S40, S39, S49 | RN (subset only) | 13 |
| D32 | **EPFL Multi-Anatomical Ultrafast US RF** [Zenodo](https://doi.org/10.5281/zenodo.22936172), [EPFL portal](https://datasets.epfl.ch/epfl_ge11ld_ultrafast_ultrasound/), [record](https://zenodo.org/records/22936172) | 2026-09-24 · **A-u** (no diagnostic labels) | Ultrafast plane-wave RF (GE 11L-D / Verasonics) | Beamforming / compounding benchmark | 20,431 acquisitions (16 volunteers + phantom); ~4 TB | 1 setup, Switzerland | CC BY 4.0 | None (a 2026 paper used volunteers 005/008/017 as test) | Paper subsets benchmark-exposed | S16, S40, S49 | RN (subset) | 13 |
| D33 | **BUS-Large** [KTH record](https://doi.org/10.71775/kth.frfd6-ymw69), [catalogue](https://researchdata.se/en/catalogue/dataset/oai-datarepository-kth-se-frfd6-ymw69), [MedIA paper](https://www.sciencedirect.com/science/article/pii/S1361841526001982) | Catalogue 2026-07-15 (file availability unverified) · **B2 / conditional** | Breast US static images | Harmonized diagnosis, lesion masks, BI-RADS | >21,000 images from 21 datasets | Multi-country (from sources) | CC BY 4.0 listed but **restricted / non-public** | ? | **Re-aggregates 21 public BUS datasets** | S16, S4, S22 | RA | 13 |
| D34 | **OMAMA-DB multiview (HYFOWN)** [Dataverse](https://doi.org/10.7910/DVN/HYFOWN), [project](https://mpsych.org/omama/); older [KXJCIU](https://doi.org/10.7910/DVN/KXJCIU) | Record 2026-08-20 · **conditional** (A if patients are new; else D) | 2D mammography, 4 views | IndexCancer / PreIndexCancer / NonCancer; DeepSight scores; lesion boxes | 4,138 studies / 16,552 images (1,957 cancer) | Not stated; DICOM headers provided | MIT listed; access request (guestbook) | No hidden test | Possible subset of 2024 OMAMA (165,368 images / 157,810 patients) | S4, S9, S21, S44, S54 | RA / RV | 13 |
| D35 | **SonoCorpus manifest** [Zenodo](https://doi.org/10.5281/zenodo.22770825), [SonoBase](https://github.com/AlfredQin/sonobase) | 2026-09-18 · **manifest only** (B) | 53 public US datasets | Inventory, splits, checksums, licences (no pixels) | Describes 456,963 images / 1,626,085 masks | 17 countries (sources) | CC BY 4.0 manifest | SonoBase benchmark / external splits public | Entire corpus pre-cutoff | S7, S16, S32 (split construction, overlap audits) | RN (tool) | 13 |
| D36 | **Cancer Moonshot Biobank (CMB) radiology additions, IDC V25** [IDC notes](https://learn.canceridc.dev/data/data-release-notes), [TCIA CMB](https://www.cancerimagingarchive.net/research/cmb/) (+ collection pages: [LCA](https://www.cancerimagingarchive.net/collection/cmb-lca/), [CRC](https://www.cancerimagingarchive.net/collection/cmb-crc/), [BRCA](https://www.cancerimagingarchive.net/collection/cmb-brca/), [MML](https://www.cancerimagingarchive.net/collection/cmb-mml/), [PCA](https://www.cancerimagingarchive.net/collection/cmb-pca/), [MEL](https://www.cancerimagingarchive.net/collection/cmb-mel/), [GEC](https://www.cancerimagingarchive.net/collection/cmb-gec/), [OV](https://www.cancerimagingarchive.net/collection/cmb-ov/), [AML](https://www.cancerimagingarchive.net/collection/cmb-aml/), [VS-MC-RC](https://www.cancerimagingarchive.net/collection/vestibular-schwannoma-mc-rc/)) | October 2026 (IDC V25) · **A-u** (new series, no image-level labels) | CT, DX, MR, PT, NM, US, XA, MG, CR, RF (varies by collection) | No new image-level labels; cohort-level diagnosis; clinical/genomic data separate (dbGaP) | 246 patients with new series (84 new to IDC), 3,512 series, 401,190 instances | US multi-site NCORP; vendor and site per image need audit | TCIA/IDC CC BY 4.0 (images); clinical data credentialed | No test | New UIDs, but **same-patient overlap** with older collections | S20, S8, S18, S49, S50, S39 | RX | 14 |
| D37 | **TAIR cerebrovascular multimodal** [TAIR](https://tair.kitware.com/clinical-data/), [AWS](https://registry.opendata.aws/arpa-h-air/), [Kitware notice](https://www.kitware.com/kitware-and-unc-chapel-hill-release-new-imaging-dataset-through-arpa-h-air-program/) | "Current release 11.3.2026" (2026-11-03); first installment · **A-u** (annotations planned December 2026) | CTA, MRA volumes + interventional fluoroscopy video (MP4) | Planned: 100 segmented/centerlined models, 50 (or 150) annotated fluoroscopy sets | First tranche: 500 CTA/MRA studies + 150 fluoroscopy videos (planned total 2,500 + 1,500) | Multi-center (UNC, Kitware, Pittsburgh among collaborators); details ? | CC BY 4.0 | None | **Fluoroscopy availability contradictory** ("coming December 2026") | S20, S49, S8, S56, S18 | RV / RX | 14 |
| D38 | **HoloDATA v1** (with HoloCT) [release](https://github.com/alibaba-damo-academy/HoloCT/releases/tag/holodata-v1), [repo](https://github.com/alibaba-damo-academy/HoloCT), [arXiv](https://arxiv.org/abs/2611.06471) | 2026-11-07 · **B2** (metadata, splits, some annotations) | 3D CT | Seg / lesion-screening metadata; AMOS-, DeepTumorVQA- and BIMCV-grounded annotations; splits | Not a 195,921-scan download; images from source sets | 73 public datasets + 6 clinical cohorts (not released) | No single licence; inherits sources | Splits for several sets | **Very high** overlap (CT-RATE, AMOS, INSPECT, Merlin, LIDC…) | S56, S45, S11, S25, S51 | RA (sources) | 14 |
| D39 | **MetaStructAtlas / MetaStructVQA** [HF](https://huggingface.co/datasets/withtst/MetaStructAtlas), [commit](https://huggingface.co/datasets/withtst/MetaStructAtlas/commit/b1cb1896ee7ab0716be5343ee3c394bbb486cb20), [paper](https://arxiv.org/abs/2609.03690), [repo](https://github.com/withtst/MetaStructVQAbenchmark) | Preview commit 2026-11-10; **full release planned after acceptance** · announced only | Whole-body 18F-FDG PET + CT | Organ masks, report-derived descriptions, grounded VQA | Public: **3 JSON examples**. Planned: 490 patients, 50,470 masks, ~100k QA (100,565 vs 100,241 conflict) | 1 Shanghai center, Siemens Biograph 64, 2021–2024 | Preview Apache-2.0 | Planned 323/81/86 | — | S20, S17, S23, S56 (when released) | NR | 14 |
| D40 | **VinDr-Ground-VQA** [Zenodo v1.0](https://zenodo.org/records/24073784), [GitHub](https://github.com/Yifan-wang-maybe/VinDr-Ground-VQA), [parent VinDr-CXR](https://physionet.org/content/vindr-cxr/1.0.0/) | 2026-11-09 (Zenodo + GitHub; internal August freeze ≠ release) · **B2** | PA CXR (VinDr subset) | Grounded VQA on 22 findings: yes/no, localization, open; evidence boxes; controlled co-occurrence sets | 8,434 images; 102,072 QA (81,656 / 9,652 / 10,764); patients ? | VinDr: 2 Vietnamese hospitals; 7 vendors in parent (subset breakdown ?) | QA + boxes MIT; **pixels via credentialed PhysioNet** | All splits public; build fresh holdout | Derived from pre-cutoff VinDr labels; ROI check used an external model API | S47, S14, S17, S37, S24, S43 | RA (credentials) | 15 |
| D41 | **radiology-conflict (22-language extension)** [HF](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict), [history](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict/commits/main), [API](https://huggingface.co/api/datasets/multilingual-vlm-conflict/radiology-conflict) | Languages added 2026-07-06 (English base 2026-06-30 = C) · **B2 (text only)** | Mixed radiology images (e.g. head CT, renal US) + text | Image-consistent vs conflicting caption/answer; laterality/pathology conflict fields | 100 underlying cases × 23 configs | Provenance unknown | **No licence declared** | Only a `train` split | Image source unknown; translation method undocumented | S48, S47, S37 | RN (rights unclear; pilot) | 15 |
| D42 | **HUAC Portuguese labeled CXR reports** [v6](https://huggingface.co/datasets/guilhermenf/huac_labeled_chest_xray_reports_v6), [c5-v1](https://huggingface.co/datasets/guilhermenf/huac_labeled_chest_xray_reports_c5_v1); raw base [here](https://huggingface.co/datasets/guilhermenf/huac_chest_xray_reports) | 2026-07-10 (v6), 2026-07-12 (c5-v1); raw base 2026-05-10 = C · **A/B text (conditional)** | Portuguese CXR report text (no images) | Fields c1–c5, j1–j4, `label`; **codebook unavailable** | v6 254 rows (190/64); c5-v1 227 rows (170/57) | HUAC hospital, Brazil (1 site); reports dated 2026-01-01 → 2026-05-07 (base card) | v6 gated, c5-v1 public; no licence field | Public splits | Row overlap with raw base unaudited | S48, S51, S38 | RV | 15 |
| D43 | **REFLACX diagnostic-discrepancy tables** [Zenodo](https://zenodo.org/records/24128748) | 2026-11-11 · **B2** | CXR reading (eye tracking, derived tables) | Perceptual / cognitive / satisfaction-of-search / normal discrepancy outcomes; consensus ROIs | 109 radiographs, 525 sessions, 358 case-finding rows | From REFLACX / MIMIC | CC BY 4.0 (derived); images under MIMIC terms | Public image-level splits | Entirely old images | S10 (error families) | RA | 15 |
| D44 | **RSNA Knee Abnormality Detection 2026** [RSNA page](https://www.rsna.org/artificial-intelligence/ai-image-challenge/knee-mri-ai-challenge), [launch](https://www.rsna.org/news/2026/august/ai-challenge-knee-mri), [Kaggle](https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/overview) | Launch 2026-08-05 (file timestamp unverified) · **A** (likely) | Knee MRI + reports in **12 languages** | 12-label abnormality classification (plan); expert-radiologist evaluation labels | >5,000 exams. Plan: 58 expert-labeled studies, 4,349 with reports only, ~1,322 hidden test | **16 vs 19 sites (official pages conflict)**; 5 continents; per-study site/vendor metadata unverified | Kaggle competition rules; RSNA approved third-party API use (plan) | **Hidden test**, Kaggle late submission | Overlap unknown; plan denylists published LLM labels (1st/7th place), NTejas labels, released 3rd/6th place weights (`16` found no released winner weights: verify) | S1, S7, S48, S51, S45, S19, S50, S44, S47, S43 | RA (Kaggle; plan Phase 2) | 16, plan |
| D45 | **CLEAR-EC** corneal endothelium (ophthalmic, not radiology) [challenge](https://clear-ec.grand-challenge.org/), [Zenodo](https://zenodo.org/records/21270595) | 2026-07-09 (record) · **A-r**, not radiology | Specular microscopy | Regression: cell density, CV, hexagonality | ? | Eye banks ? | Restricted; **zero files** (page claims public) | Hidden test | ? | S7, S8 (out of scope) | NR | 16 |

**Tally (D01–D45).**

| Category | Count | Entries |
|---|---|---|
| Tier A with labels, open or registration access | 12 | D01, D02 (RV), D07, D08, D12, D13 (reconstruction references), D14 (phantom), D16 (v3 additions), D23 (centers 1/2/4), D25 (v3 additions), D30, D44 (Kaggle) |
| A-r | 4 | D03, D09, D17, D45 (non-radiology) |
| A-p | 1 | D19 |
| A-u | 4 | D31, D32, D36, D37 |
| B1 | 6 | D15, D18, D24, D26, D28 (conditional), D29 (conditional) |
| B2 | 10 | D04, D05, D06, D20, D22, D27, D33, D38, D40, D43 |
| B-syn | 2 | D10, D11 |
| Text-only extensions | 2 | D41, D42 |
| Manifest or announcement only | 2 | D35, D39 |
| Conditional, provenance unresolved | 2 | D21, D34 |
| **Total** | **45** | |

### 5.2 Borderline datasets: Tier C (first public January–June 2026) and date-unresolved near-cutoff

One line each. These may be used only for flagged secondary analyses, replication or source data (§4.3).

| ID | Name / link | First-data date (evidence) | Content (one line) | Use / reason it is borderline | Src |
|---|---|---|---|---|---|
| C01 | [TAIX-Ray](https://huggingface.co/datasets/TLAIM/TAIX-Ray) ([DOI](https://doi.org/10.57967/hf/7823), [paper](https://www.nature.com/articles/s41597-026-07271-7)) | HF uploads 2026-02-05 → 02-08 | 215,381 bedside AP ICU CXR, 47,724 patients, Aachen, 18 Siemens Mobilett MIRA units, 2010–2023, ordinal findings, patient-level split, CC BY 4.0 | Best temporal / bedside set (S9/S31/S40), but pre-cutoff files | 10 |
| C02 | [MIMIC-CXR-Ext-ILS](https://physionet.org/content/mimic-cxr-ext-ils/1.0.0/) ([DOI](https://doi.org/10.13026/8ejy-4t06)) | 2026-03-25 | 91,301 auto masks + 1,065,621 instruction–answer pairs on 191,563 MIMIC images (7 findings) | Training resource for S24/S47/S10 | 10 |
| C03 | [BDCXR-3257](https://figshare.com/articles/dataset/_b_BDCXR-3257_b_A_Comprehensive_Chest_Radiography_Dataset_with_Multi-Etiological_Pneumonia_Labels_from_a_Clinical_Setting/32086362) ([API](https://api.figshare.com/v2/articles/32086362)) | 2026-04-30 | 3,257 pediatric CXR, Dhaka; normal / viral / bacterial pneumonia; κ>0.95; CC BY 4.0 | Only LMIC pediatric CXR found (S22/S30/S52); pre-cutoff | 10 |
| C04 | [DMCH-PneumoX](https://doi.org/10.57760/sciencedb.30436) | 2026-03-16 (catalog) | Dhaka Medical College pneumonia CXR; counts, licence and labels unverified | Lead only | 10 |
| C05 | [Nigeria community AI-X-ray screening](https://doi.org/10.6084/m9.figshare.32687448.v1) | 2026-06-16 | 1.4 MB Excel workbook, **no images** | Not an image set | 10 |
| C06 | [FMCEB-CXR](https://doi.org/10.5281/zenodo.20750284) | 2026-06-19 | 5,517 Nigerian radiology reports, 14 NLP labels, no images | Text-only S38/S48 source | 10 |
| C07 | [Pediatric mixed-dentition OPG (FaceBase)](https://doi.org/10.25550/b1-vdgg) | 2026-01-01 (catalog; unverified) | ~5,000 pediatric OPGs, ages 4–16 | Lead; S30 dental | 10 |
| C08 | [AMPLIFAI](https://um-ihc-ca2i.github.io/amplifai-challenge/data.html) ([HF](https://huggingface.co/datasets/UM-IHC-CA2i/AMPLIFAI), [paper](https://arxiv.org/abs/2608.14778)) | Training batches 2026-06-05/19/26 | Multiphase liver CT, LI-RADS, lesion + feature masks; 764 / 668 / 590 count conflict; CC BY-NC-SA; hidden test | S46/S50/S33 fallback; harmonized from 4 public sources | 11 |
| C09 | [ReXGroundingCT](https://huggingface.co/datasets/rajpurkarlab/ReXGroundingCT) ([paper](https://doi.org/10.1056/aidbp2501220)) | Paper 2026-06-18; file date unverified | 3,142 chest CT, 8,028 finding masks, 14 categories; 100 hidden cases; CT-RATE overlap | S47/S56 fallback | 11 |
| C10 | [Lung tumor CT (ScienceDB)](https://doi.org/10.57760/sciencedb.29318) ([descriptor](https://doi.org/10.1038/s41597-026-07963-0)) | 2026-03-07 | 1,179 cases (730 early + 449 advanced), tumor masks, Anhui | S25/S56 fallback | 11 |
| C11 | [TotalSegmentator liver_lesions](https://zenodo.org/records/20272572) | 2026-05-18 | 842 CT, liver-lesion masks | S24/S25/S56 fallback | 11 |
| C12 | [PatchChestCT](https://zenodo.org/records/19707049) ([paper](https://www.nature.com/articles/s41597-026-07793-0)) | 2026-04-23 | Patch masks on 2,201 noncontrast chest CTs, 9 abnormalities | S24/S34 fallback | 11 |
| C13 | [LIDC-annot-NLST501](https://www.cancerimagingarchive.net/analysis-result/lidc-annot-nlst501/) | **Ambiguous**: 2026-02-06 record vs 2026-08-05 TCIA update | 501 NLST patients, multi-reader nodule / lesion annotations, 4 vendors; 410 patients shared with Ardila 2019 | Plan's Phase 3 candidate: **treat as C** unless deposit history proves otherwise | 11, plan |
| C14 | [LUNOVO26 debug set](https://doi.org/10.5281/zenodo.19449567) | 2026-04-07 | 5 LIDC-derived debugging cases | Low utility | 11 |
| C15 | [MRIxFields2026](https://github.com/AHMED996552/MRIxFields2026) ([Synapse](https://www.synapse.org/Synapse:syn72060672/datasets/)) | 2026-04-10 | Paired travelling-volunteer brain MRI at 0.1 / 1.5 / 3 / 5 / 7 T, 5 scanner models | Best S6/S12/S49 field-strength set; pre-cutoff | 12 |
| C16 | [DoseRAD2026](https://doserad2026.grand-challenge.org/data/) ([Zenodo](https://doi.org/10.5281/zenodo.19347848)) | April 2026 | 122 patients, CT + 0.35T MR-Linac MRI, dose maps; 864 GB; test private until 2030 | S49 low-field / dose regression | 12 |
| C17 | [FOMO300K](https://huggingface.co/datasets/FOMO-MRI/FOMO300K) ([FOMO26](https://fomo26.github.io/)) | HF update 2026-04-03 | 306,207 brain MRI scans, 920 sources | MRI pretraining source | 12 |
| C18 | [MosaicMRI](https://mosaicmri.ai/) ([arXiv](https://arxiv.org/abs/2604.11762)) | **Unresolved** (paper April; site updated 2026-08-31) | 3,096 raw MSK k-space volumes, 854 patients, 1.5T Siemens; gated | S7/S49 watch item | 12 |
| C19 | [AMYPAD-PNHS MRI](https://www.nature.com/articles/s41597-026-07988-5) ([data](https://amypad.eu/data/)) | Data v202306 (paper 2026-08-03) → actually **D** | 2,759 participants, 10 cohorts, controlled access | Paper-date trap | 12 |
| C20 | [BreastDCEDL](https://www.nature.com/articles/s41597-026-06589-6) ([Zenodo](https://doi.org/10.5281/zenodo.17274053)) | Zenodo 2025 → actually **D** | 2,070 breast DCE patients | Paper-date trap | 12 |
| C21 | [BIG-MRI proposal](https://doi.org/10.5281/zenodo.19732926) | 2026-04-24 (PDF only) | Planned >3,500 high-risk breast MRI + ~1,900 external | No data released | 12 |
| C22 | [PiCaRad](https://doi.org/10.5281/zenodo.21789140) | 2026-08-04 (PDF only) | Radiomics from PI-CAI / Prostate158 | No feature artifact found; old MRI | 12 |
| C23 | [CMRx4DFlow2026](https://cmrxrecon.github.io/2026/data.html) | **Unresolved** | >400 4D-flow cases, 10+ centers, 4+ vendors, 1.5/3/5 T | S49 / S2 watch item | 12 |
| C24 | [LUMINA](https://www.kaggle.com/datasets/phy710/lumina-mammography-dataset) ([GitHub](https://github.com/NUBagciLab/LUMINA), [paper](https://arxiv.org/abs/2603.14644)) | Kaggle v1 2026-03-10 | 1,824 FFDM / 468 patients, Istanbul, **6 vendors**, pathology + BI-RADS + density; CC BY-NC 4.0 | Only multi-vendor mammo found (S4/S21/S54); underpowered | 13 |
| C25 | [PU2756](https://doi.org/10.6084/m9.figshare.32672274) ([paper](https://www.nature.com/articles/s41597-026-07715-0), [code](https://github.com/Intelligent-Medical-Research-Group/PU2756)) | Figshare 2026-06-15 | 2,756 pulmonary lesion US images / patients, masks + biopsy benign/malignant; CC BY 4.0 | Strong S16/S22 set; pre-cutoff by 16 days | 13 |
| C26 | [DBT-2026](https://www.medrxiv.org/content/10.64898/2026.03.03.25337924v1.full) ([iMerit](https://imerit.net/3d-mammogram-dataset/), [HF sample](https://huggingface.co/datasets/iMerit/3D-MammographyDataset)) | Preprint 2026-03-04; full-data date unverified | 558 patients (558 vs 1,110 exams conflict), DUA | S21/S4 DBT, gated | 13 |
| C27 | [EchoRisk-MICCAI](https://echorisk-miccai.github.io/dataset.html) | 2026-04-17 (registered teams) | 422 patients, 2,159 echo videos, longitudinal q3-month follow-up; **closed to new users** | S9/S55 if already authorized | 13 |
| C28 | [FADA interpretation](https://doi.org/10.5281/zenodo.20104811) ([v2](https://doi.org/10.5281/zenodo.20381238)) | 2026-05-11 | 56,805 fetal-US conversations on 18,935 images from 7 public sets (incl. FUSEP); restricted, no files | S17/S47 if obtained | 13 |
| C29 | [FLARE26 Task 5 MLLM-3D](https://huggingface.co/datasets/FLARE-MedFM/FLARE26-MLLM-3D) | HF update 2026-04-19 | ~1,290 AMOS + 2,000 CT-RATE volumes, report / VQA; gated; CC BY-NC | S19/S56/S45 fallback | 14 |
| C30 | [VLM3D 2026](https://zenodo.org/records/19847782) | 2026-04-28 (PDF) | Chest CT + brain MRI tracks; closed Boston test | Announcement only | 14 |
| C31 | [PSMA-PET-CT-Lesions](https://www.cancerimagingarchive.net/collection/psma-pet-ct-lesions/) | v1/v2 February 2026 (prior autoPET use) | 597 studies / 378 patients, 18F- vs 68Ga-PSMA, 3 scanners | S20/S50 tracer-shift comparator | 14 |
| C32 | [RadM-Bench](https://huggingface.co/datasets/Elizabeth123/RadM-Bench) ([GitHub](https://github.com/ELIZABETH21Wu/RadM-Bench)) | 2026-06-30 | 720 bilingual cases (360 Eurorad EN + 360 Henan ZH), CT / MR / hybrid | S1/S47/S48 pilot | 15 |
| C33 | [SynRad-IR-200](https://zenodo.org/records/20637519) ([v1.2](https://zenodo.org/records/23896461)) | 2026-06-11 (v1.2 November = code only) | 200 synthetic IR referral / urgency reports | S47 text pilot | 15 |
| C34 | [HUAC raw report collection](https://huggingface.co/datasets/guilhermenf/huac_chest_xray_reports) | 2026-05-10 | 223 Portuguese CXR reports | Base for D42 | 15 |
| C35 | [radiology-conflict English base](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict) | 2026-06-30 | 100 cases | Base for D41 | 15 |
| C36 | TopAneu Batch 1 ([data page](https://topaneu-26.grand-challenge.org/data/)) | 2026-06-15 | First 97 scans of the 415-scan bundle (415 − 318) | Pre-cutoff part of D23 | 12 |
| C37 | [ISLES'26 / ATLAS v3.0](https://isles-26.grand-challenge.org/dataset/) ([ATLAS](https://fcon_1000.projects.nitrc.org/indi/retro/atlas.html), [record](https://zenodo.org/records/19886303)) | **Unresolved** (design PDF 2026-04-29) | 1,453 T1 stroke scans + masks; 329 / 498 new scans; site + chronicity CSV | S6/S7/S9/S26 if new cases confirmed post-cutoff | 16 |
| C38 | [LISA 2026](https://zenodo.org/records/19714596) ([GitHub](https://github.com/rousseau/lisa2026)) | Description 2026-04-23; data unverified | Pediatric 0.064T Hyperfine brain MRI, LMIC motivation | Best pediatric / LMIC / low-field lead (S30/S49/S52) | 16 |
| C39 | [TREAT-MMTB](https://treat-mmtb.mi2rl.co/) ([code](https://github.com/mi2rl-challenge/treat-mmtb.miccai2026)) | Participant-gated May–August 2026 | TB CXR, external validation in Korea, Mongolia, Peru, Philippines; 444 masked Task 1 images | Best low-resource CXR lead (S52) | 16 |
| C40 | [ISBI 2026 CSV carotid plaque US](https://biomedicalimaging.org/2026/challenges/) | Unverified | 1,500 paired images, 7 hospitals, 4 machine types | S2/S7/S8 watch item | 16 |
| C41 | [CrossPan](https://huggingface.co/datasets/linkai-peng/CrossPan) ([paper](https://proceedings.mlr.press/v315/peng26a.html)) | HF 2025-12-07 → **D** | 1,386 pancreas MRI, 3 sequences, 8 centers | S7/S50 source (D) | 16 |
| C42 | [Histo-DG-Benchmark](https://zenodo.org/records/19471815) | 2026-04-08 | Histopathology DG scripts (no images) | Out of scope | 16 |
| C43 | [MAGIC-CT](https://zenodo.org/records/18389015) | "Published 2026" (day unknown) | 562 patients, lesion / organ masks, RU / KZ / EN reports; DUA | Date-unresolved lead (S48/S56) | 11 |

### 5.3 Excluded or unverified leads

One line each, with the reason.

| Lead / link | Reason excluded | Src |
|---|---|---|
| [Bangladesh normal CXR](https://data.mendeley.com/datasets/wndbd5r26y/1) | v1 2025-10-01; patient leakage concerns | 10 |
| [Prompt2SegCXR](https://data.mendeley.com/datasets/mk36vt2nzj/1) | v1 2024-12-27; v2 adds no isolable new component | 10 |
| [ChestX6](https://doi.org/10.5281/zenodo.21880301) | Repackages 4 old CXR datasets | 10 |
| CXR-LT 2026 | Old PadChest / NIH images | 10 |
| [PediURF](https://figshare.com/articles/dataset/PediURF_A_Comprehensive_X-ray_Dataset_for_The_Pediatric_Ulna_and_Radius_Fractures_Analysis/29998954) | Data August 2025 | 10 |
| [PediaSHF-DX](https://figshare.com/articles/dataset/A_Benchmark_X-ray_Dataset_for_Pediatric_Supracondylar_Humerus_Fracture_with_Improved_YOLOv11-Based_Detection/29322869) | Data June 2025 | 10 |
| [X-Pan](https://doi.org/10.5281/zenodo.22838356) | Record contains only a PDF | 10 |
| [HarMoE](https://arxiv.org/html/2608.02252) | Model / data "will be released"; not verified | 10 |
| [Longitudinal melanoma CT](https://www.nature.com/articles/s41597-026-07466-y) ([FDAT](https://fdat.uni-tuebingen.de/records/75kj1-64747)) | Data 2025-09-16 | 11 |
| [FDG-PET-CT-Lesions v2](https://www.cancerimagingarchive.net/collection/fdg-pet-ct-lesions/) | 2026-08-17 update is defacing / access only; data from 2022 | 14 |
| [HFH.MIVD interventional vascular](https://aapm2026explorer-production.up.railway.app/detail/paper/1614) | Abstract only; no download | 14 |
| [Guidewire Tip Dataset](https://doi.org/10.5281/zenodo.23404891) | Restricted; zero files | 14 |
| [Thrombectomy DSA time-density](https://doi.org/10.5281/zenodo.23768014) | Restricted; derived curves only | 14 |
| FAP-tracer PET | None verified | 14 |
| Post-cutoff image + EHR cohort | None verified (CMB only partial) | 14 |
| [CT/MRI report-summarization paper](https://arxiv.org/abs/2611.10277) | No data artifact found | 15 |
| [PETARSeg-11K](https://arxiv.org/abs/2510.27680) | Pre-cutoff | 15 |
| RadCoT, translation-only papers | No releasable corpus | 15 |
| Heartbeat (fetal echo) | No public files verified | 13 |
| BUS-CoT | Figshare 2025-12-09 | 13 |
| Zenodo breast-US 21315228 | Code package; no images | 13 |
| TN-Mammo v1.0.1 | No post-cutoff extension found | 13 |
| [MedSeg-TTA](https://arxiv.org/abs/2512.02497) | 2025; existing datasets | 16 |
| [TopCoW](https://topcow24.grand-challenge.org/) source images | 2025 | 16 |
| [CAPTURE pediatric TB](https://pmc.ncbi.nlm.nih.gov/articles/PMC12815126/) | Protocol only | 16 |
| [SPR 2026 Mammography Report Classification](https://www.kaggle.com/competitions/spr-2026-mammography-report-classification), [AMIA 2026](https://www.kaggle.com/competitions/amia-public-challenge-2026/overview), [EHL Paris retrieval](https://www.kaggle.com/competitions/ehl-paris-medical-image-retrieval), [Multimodal Cancer 2026](https://www.kaggle.com/competitions/multimodal-cancer-classification-challenge-2026/data), [Grand X-Ray Slam A](https://www.kaggle.com/competitions/grand-xray-slam-division-a/data) | Kaggle pages are JS-rendered; nothing verified (SPR mammography report classification is a possible S38/S46 text lead) | 16 |
| NeurIPS 2026 Evaluations & Datasets track | No accepted list found by 2026-11-12 | 16 |
| ISBI 2027 challenges | Notifications 2026-11-16 | 16 |
| MICCAI 2026 challenge inventory (44 events) and Grand Challenge 2026 index | Event listing ≠ data release; only COBRA, TopBrain, TopAneu, RSNA verified | 16 |

### 5.4 Tier D legacy pool (source / training only; never test)

The pre-cutoff datasets that the brainstorm and shards name as source data or ceilings are listed below. The inputs give no links for most of them, so none are invented here.

| Domain | Datasets |
|---|---|
| CXR | CheXpert (+ CheXpert Plus), MIMIC-CXR / -JPG, NIH ChestX-ray14, PadChest (+ PadChest-GR), VinDr-CXR, VinDr-PCXR, BRAX, Shenzhen, Montgomery, TBX11K, IU-Xray, ReXGradient, BIMCV-COVID19+, COVIDx, Guangzhou pediatric pneumonia, REFLACX, Chest ImaGenome, JSRT |
| MSK | MURA, FracAtlas, GRAZPEDWRI-DX |
| Mammography | EMBED, VinDr-Mammo, CMMD, CBIS-DDSM, OPTIMAM, RSNA screening, OMAMA KXJCIU (2024), MAMA-MIA |
| CT | LIDC-IDRI, LUNA16, LNDb, NLST, Mayo LDCT, RSNA ICH, CQ500, CT-RATE, RadChestCT, AMOS, CHAOS, BTCV, LiTS, KiTS, TotalSegmentator v2, ImageCAS, INSPECT, Merlin data, AbdomenAtlas, Spinal-MM-SEG CT, RSNA cervical spine |
| MRI | M&Ms-1/2, 6-site prostate (RUNMC, BMC, I2CVB, UCL, BIDMC, HK), PI-CAI, Prostate158, ADNI, OASIS-3, MSSEG, ISBI 2015, SRPBS, MR-ART, BraTS, FeTS, TopCoW, INSTED, OpenNeuro, IXI, Mindboggle-101, iSTAGING, CrossPan, BreastDCEDL |
| PET / US / echo | autoPET (FDG, PSMA), HECKTOR, BUSI, BUS-BRA, UDIAT, EchoNet-Dynamic, EchoNet-Pediatric, CAMUS, SonoCorpus constituents |

---

## 6. Backbone catalog

**Conventions.**

- **Post-cutoff** means the public checkpoint was available after 2026-07-01 (`17` uses bold POST-CUTOFF).
- **24 GB** is a shard estimate, not a measurement:
  - **Yes:** full tuning of the named variant is plausible;
  - **LoRA:** use an adapter, LoRA or a frozen encoder;
  - **Profile:** must be measured;
  - **No:** not feasible.
- **Pretraining disclosure** feeds the overlap matrix in §4.1. Missing disclosure is treated as uncertainty, not as clean.
- **Interpretability** marks a released model-specific SAE (✔SAE), a published SAE method on this model (paper), or generic hooks only.
- The plan's Phase 1/2 encoders (SKELEX, MRI-CORE, OrthoFoundation) come from `plan.md`. They were not verified by the shards.

### 6.1 Natural-image starting points (domain-gap setups S14–S17, S21, S45)

| Model / link | Release · post-cutoff? | Size / input | Licence | Pretraining data (overlap note) | 24 GB | Interpretability | Setups | Src |
|---|---|---|---|---|---|---|---|---|
| **DINOv3** ([model card](https://github.com/facebookresearch/dinov3/blob/main/MODEL_CARD.md), [HF ViT-B/16](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m)) | 2025-08-14 · no | ViT-S 21M / B 86M / L 300M / H+ 840M / 7B; ConvNeXt-T/S/B/L distilled; patch 16 | Meta custom DINOv3 licence (plan calls it "open": check) | LVD-1689M from Instagram posts (web; medical overlap cannot be excluded) | B: Yes; L: batch-1 / checkpointing (Phase 1 ran L at 224 px); H+/7B: LoRA / probe | SAEs on DINOv3 CT/MRI features ([MICCAI 2026](https://papers.miccai.org/miccai-2026/paper/4497_paper.pdf)); hooks | S14, S15, S16, S21, S45, S7, S26, S32 | 10–17 |
| **DINOv2** ([repo](https://github.com/facebookresearch/dinov2)) | 2023 · no | ViT-B/14 etc. | — | Natural images | Yes | Hooks | S45 (v1 → v2 source) | 13, 17 |
| **SigLIP 2** ([card](https://huggingface.co/google/siglip2-so400m-patch14-384), [paper](https://arxiv.org/abs/2502.14786)) | 2025-02 · no | B → So400M/14 @384 | Apache-2.0 (cited checkpoint) | WebLI | B: Yes; So400M: LoRA | Text/image concept directions | S17 | 17 |
| **CLIP / OpenCLIP** ([CLIP](https://github.com/openai/CLIP), [OpenCLIP](https://github.com/mlfoundations/open_clip)) | 2021+ · no | B/32 ~151M; L/14 ~428M | MIT (OpenAI); OpenCLIP per checkpoint | WIT-400M / LAION / DataComp | B: Yes; L: LoRA / full batch-1 | Text-tower probes | S17, S23 | 17 |
| **SAM / SAM 2** ([SAM](https://github.com/facebookresearch/segment-anything), [SAM 2](https://github.com/facebookresearch/segment-anything-2)) | 2023-04 / 2024-07-29 · no | SAM B/L/H 91/308/636M @1024; SAM2 39–224M | Apache-2.0 | SA-1B; SA-V | Small/base: LoRA / full plausible | None medical | S56, S25 | 17 |
| **MAE ViT** ([repo](https://github.com/facebookresearch/mae)) | 2021 · no | B/L/H | CC BY-NC 4.0 | ImageNet-1K | B/L: Yes | None | S14 (control) | 17 |
| **ConvNeXt V2** ([repo](https://github.com/facebookresearch/ConvNeXt-V2)) | 2023 · no | Base ~89M | MIT code; checkpoint terms vary | ImageNet-1K/22K | Yes | Channel probes | S14, S32; plan Phase 2 (ConvNeXt-T) | 17, plan |
| **Qwen2.5-VL-7B-Instruct** ([announcement](https://qwenlm.github.io/blog/qwen2.5-vl/)) | 2025-01 · no | 7B VLM (image, video, localization) | Qwen terms | Web (undisclosed) | 4-bit QLoRA, batch 1 | Hooks | S47, S48, S37, S17 | 15 |

### 6.2 General medical and modality-specialist encoders

| Model / link | Release · post-cutoff? | Size / input | Licence | Pretraining data (overlap note) | 24 GB | Interpretability | Setups | Src |
|---|---|---|---|---|---|---|---|---|
| **RAD-DINO** ([card](https://huggingface.co/microsoft/rad-dino), [paper](https://www.nature.com/articles/s42256-024-00965-w)) | 2024 · no | ViT-B/14 86.6M; 518 px | MIT (research) | MIMIC-CXR 368,960; CheXpert 223,648; NIH 112,120; PadChest 136,787; BRAX ~41K: **never test on these** | Yes | Hooks | S1, S14 (ceiling), S21, S9, S31, S28, S45 | 10, 17 |
| **CXR-FM** ([checkpoint](https://huggingface.co/microsoft/CXR-FM)) | 2023 · no | — | — | CXR | — | — | S1, S51 | 10 |
| **MedImageInsight** ([model](https://huggingface.co/microsoft/MedImageInsight)) | 2024 · no | — | — | Medical images | — | — | S1, S51 | 10 |
| **BiomedCLIP** ([card](https://huggingface.co/microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224), [paper](https://arxiv.org/abs/2303.00915)) | 2023-01 · no | ViT-B/16 + PubMedBERT; 224 | MIT | PMC-15M figures / captions | Yes (profile both towers) | None released | S17, S23 | 10, 17 |
| **MedSigLIP** ([card](https://developers.google.com/health-ai-developer-foundations/medsiglip/model-card), [HF](https://huggingface.co/google/medsiglip), [paper](https://arxiv.org/abs/2507.05201)) | 2025-07 · no | 400M + 400M; 448 px | HAI-DEF terms | MIMIC-CXR, PMC-OA, knee X-rays, derm / path + private; card warns of contamination | LoRA (plan: 448 px needs LoRA / checkpointing) | None | S17, S14; plan comparator | 17, plan |
| **MedCLIP** ([repo](https://github.com/RyanWangZf/MedCLIP), [paper](https://arxiv.org/abs/2210.10163)) | 2022 · no | ResNet-50 + ClinicalBERT | MIT | MIMIC-CXR, CheXpert | Yes | **✔ MedSAE** | S17, S23 | 17 |
| **MedGemma 1 / 1.5** ([card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card), [4B HF](https://huggingface.co/google/medgemma-4b-it), [1.5 report](https://arxiv.org/abs/2604.05081)) | 2025-07-09; 1.5 2026-04 · no | 4B multimodal, 27B; 1.5 adds CT/MRI volumes, longitudinal CXR | HAI / Gemma terms | Mixed public + private; list incomplete | 4B QLoRA / LoRA; 27B no | Activation-steering study (2606.20852) | S47, S45 (1 → 1.5), S35, S46, S48 | 15, 17 |
| **MerMED-FM** ([card](https://huggingface.co/youngzhou12/MerMED)) | 2025 · no | ViT-B/16 85.8M; 7 modalities | Unclear | Includes Mendeley knee X-rays | Yes | None | S21, S30 (MSK) | 17 |
| **SKELEX** (plan §6.1) | — · no (Phase 1 primary) | ViT-L MAE, MSK radiographs | CC BY-NC-ND 4.0 | Not in shards. **`17` found no verified MSK FM**: verify | Yes at 224 px (bf16 + checkpointing; plan) | Pilot SAE / head ablation | S22, S30, S10 (MFXR) | plan |
| **MRI-CORE** (plan §11) | — | — | Apache 2.0 (plan) | Not in shards | — | — | S1, S7 (RSNA Knee) | plan |
| **OrthoFoundation** (plan §11) | — | — | Verify weight release + licence (plan) | Not in shards | — | — | RSNA Knee | plan |
| **HarMoE** ([paper](https://arxiv.org/html/2608.02252)) | Paper post-cutoff; **weights not released** | ViT-B/16 + M3AE; 873K old CXR | — | MIMIC, CheXpert, NIH, PadChest | — | — | (S1, S45 if released) | 10 |

### 6.3 3D CT / MRI / neuro foundation models

| Model / link | Release · post-cutoff? | Size / input | Licence | Pretraining data (overlap note) | 24 GB | Interpretability | Setups | Src |
|---|---|---|---|---|---|---|---|---|
| **NeuroVFM** ([encoder](https://huggingface.co/mlinslab/neurovfm-encoder), [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13472962/), [code](https://github.com/MLNeurosurg/neurovfm)) | **POST-CUTOFF** (2026-07-10 publication) | 3D ViT-B 85.8M (ViT-S 21.7M); ~1.1 GB inference peak | Weights CC BY-NC-SA 4.0; code MIT | UM-NeuroImages: 566,915 studies / 5.24M CT/MRI volumes, Michigan, pre-2024-06 (internal: public overlap less likely) | Frozen: Yes; LoRA likely; full: profile | Attentive probes | S6, S56, S45, S7 | 17 |
| **nnFoundation CNN / ViT** ([CNN](https://huggingface.co/MIC-DKFZ/nnFoundationCNN), [ViT](https://huggingface.co/MIC-DKFZ/nnFoundationViT), [paper](https://arxiv.org/abs/2609.26924)) | **POST-CUTOFF** (September 2026) | CNN 102M; Primus ViT 674M; 192³ patch, z-score | Unclear: resolve | 2.1M CT/MRI/PET volumes, 125 sources (audit all) | CNN patch FT: Yes; ViT: LoRA | None | S56, S18, S25, S45, S30 | 17 |
| **NV-Reason-CT** ([card](https://huggingface.co/nvidia/NV-Reason-CT), [blog](https://developer.nvidia.com/blog/introducing-nv-reason-ct-open-3d-ct-vlm-for-radiologist-chain-of-thought-reasoning/), [repo](https://github.com/NVIDIA-Medtech/NV-Reason-CT)) | **POST-CUTOFF** (2026-09-23) | 4.69B (Primus 3D ViT + Qwen3.5-4B); 2 mm, 384 mm crop | OpenMDW-1.1 (research only) | CT-RATE, **CancerVerse**, internal NIH: never test on CancerVerse with it | Full: No; QLoRA: Profile | None | S19, S47, S56 (comparator) | 17 |
| **HoloCT-4B / 8B** ([4B](https://huggingface.co/Alibaba-DAMO-Academy/HoloCT-4B), [8B](https://huggingface.co/Alibaba-DAMO-Academy/HoloCT-8B), [arXiv](https://arxiv.org/abs/2611.06471), [code](https://github.com/alibaba-damo-academy/HoloCT)) | **POST-CUTOFF** (2026-11-04) | 8B = 9.04B BF16 (~18.1 GB weights); Qwen3-VL + Med3DVLM + VISTA3D encoders | MIT (weights) | 195,921 CT from 73 public sets + 6 clinical cohorts (very high overlap) | 4B inference / PEFT with tiling: plausible; 8B: tight / unverified | None | S56, S25, S11, S45, S20, S47 | 11, 14 |
| **BrainFedFM** ([arXiv](https://arxiv.org/html/2609.27611), [GitHub](https://github.com/SPIresearch/BrainFedFM)) | **POST-CUTOFF** (2026) | 3D structural brain MRI FM | — | 164,707 T1w scans, 42 sites (federated) | Patch / cached: Yes | None | S6, S7, S39, S53 | 12 |
| **Brain2Vec** ([paper](https://arxiv.org/html/2610.28411), [GitHub](https://github.com/CBICA/Brain2Vec), [HF](https://huggingface.co/cbica/Brain2Vec)) | **POST-CUTOFF** (October 2026) | 3D MAE, 768-D embedding | Open weights (stated) | 74,425 T1w (iSTAGING) | Yes (patch) | None | S6, S9, S25, S33 | 12 |
| **Merlin** ([HF](https://huggingface.co/stanfordmimi/Merlin), [repo](https://github.com/StanfordMIMI/Merlin), [Nature](https://doi.org/10.1038/s41586-026-10181-8), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13082451/)) | **Date-uncertain**: `11` "not confirmed post-cutoff"; `14` pre-cutoff; `17` artifacts "by 2024 era" | 3D CT VLM | Unclear | CT + reports + EHR | Profile / adapter | None | S19, S55, S56 | 11, 14, 17 |
| **Pillar-0 Chest CT** ([HF](https://huggingface.co/YalaLab/Pillar0-ChestCT), [paper](https://arxiv.org/abs/2511.17803)) | 2025-11 · no | Native 3D | Unverified | Incomplete disclosure | Adapter | None | S19, S56; plan Phase 3 candidate | 17, plan |
| **CT-FM** ([repo as given](https://github.com/ibrahimethemhamamci/CT-FM)) | 2025-era · no | 3D CT | — | — | Patch | None | S1, S7, S56 | 11 |
| **CT-CLIP / CT-RATE** ([repo](https://github.com/ibrahimethemhamamci/CT-CLIP), [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13658014/)) | Pre-cutoff | 3D CT image–report | — | CT-RATE (overlap with HoloDATA, FLARE, ReXGroundingCT) | Patch | None | S17, S19, S47 | 11, 14 |
| **M3D / Med3DVLM** ([M3D](https://github.com/BAAI-DCAI/3D-Medical-LLM), [Med3DVLM](https://github.com/mirthAI/Med3DVLM)) | Pre-cutoff | 3D VLMs | Verify | — | Profile | None | S19, S47 | 14 |
| **Universal Model (CLIP-driven)** ([repo](https://github.com/ljwztc/CLIP-Driven-Universal-Model)) | 2023 · no | Universal segmentation | — | Public CT | Patch | None | S24, S25 | 11 |
| **ULS / ULS+** ([paper](https://arxiv.org/abs/2601.02988)) | 2026-01 · no | Lesion segmentation, point prompts | — | — | Patch | None | S55, S24 | 11 |
| **SynthSeg / SynthSeg+** ([repo](https://github.com/BBillot/SynthSeg)) | 2023 · no | Contrast-agnostic brain segmentation | — | Synthetic | Yes | — | S6, S49 baseline | 12 |
| **FOMO25 / AMAES / OpenMind encoders** ([collection](https://huggingface.co/collections/FOMO-MRI/fomo-mri-datasets)) | Pre-cutoff | 3D MRI | Check cards / DUAs | FOMO / OpenMind | Patch | None | S6, S7 | 12 |
| **Brain-SAM** ([medRxiv](https://www.medrxiv.org/content/10.64898/2026.01.30.26345164v2)) | 2026-01 · no (weights unverified) | 3D SAM2-derived | — | — | — | — | S56 | 12 |

### 6.4 Segmentation starting points

| Model / link | Release · post-cutoff? | Size / input | Licence | Pretraining data (overlap note) | 24 GB | Interpretability | Setups | Src |
|---|---|---|---|---|---|---|---|---|
| **nnU-Net v2** ([repo](https://github.com/MIC-DKFZ/nnUNet)) | 2019+ · no | Framework, not one checkpoint | Apache-2.0 | Per task | Patch: Yes | Med-SegLens-style analysis | S2, S3, S18, S24, S25, S56 | 11, 17 |
| **TotalSegmentator** ([repo](https://github.com/wasserth/TotalSegmentator), [MRI card](https://atlas.rsna.org/cards/06a25bb5-e2fe-4561-8417-8298cdb236ee)) | CT 2022; MRI 2025; **v3-era weights unverified** | nnU-Net; CT 117 / MRI 80 (MRI v3 dataset: 50) structures | Code Apache-2.0; weights separate | TotalSegmentator v2 data (direct overlap with v3's old part) | Patch: Yes | Hooks | S18, S25, S30, S45 (v2 → v3), S56, S33 | 11, 12, 17 |
| **MedSAM** ([repo](https://github.com/bowang-lab/MedSAM), [paper](https://www.nature.com/articles/s41467-024-44824-z)) | 2023–24 · no | SAM ViT-B; 2D 1024 | Apache-2.0 | 1.57M pairs, 10 modalities | Batch-1 B / LoRA | None | S25, S56 | 17 |
| **MedSAM2** ([site](https://medsam2.github.io/), [HF](https://huggingface.co/wanglab/MedSAM2), [paper](https://arxiv.org/abs/2504.03600), [repo](https://github.com/bowang-lab/MedSAM2)) | 2025-04 · no | SAM2-based 3D / video | Research and education only | 455K+ 3D pairs, 76K frames | LoRA / prompt | None | S24, S25, S56 | 11, 16, 17 |
| **VISTA3D** ([repo](https://github.com/Project-MONAI/VISTA/tree/main/vista3d), [paper](https://arxiv.org/abs/2406.05285)) | 2024 · no | Promptable 3D CT/MR, 127 labels | Code Apache-2.0; weights NVIDIA OneWay non-commercial | AMOS, BTCV, TotalSegmentator v2… | Patch: Yes | Probes | S56, S18, S25 | 14, 17 |
| **UltraSAM3** ([repo](https://github.com/zhuqh19/UltraSAM3), [HF](https://huggingface.co/zhuqh19/UltraSAM3), [paper](https://arxiv.org/abs/2607.29200)) | **POST-CUTOFF** (2026-07-30) | SAM3-derived, text-promptable US segmentation; size ? | Apache-2.0 card (`13`) vs licence unclear (`17`) | 37 public US datasets (BUSI / BUS-BRA-related…); exclude from test | Adapter: Profile | Text concept prompts | S16 (specialist reference), S56 | 13, 17 |
| **SonoBase** ([HF](https://huggingface.co/AlfredQin/sonobase), [GitHub](https://github.com/AlfredQin/sonobase)) | **POST-CUTOFF** (2026-08-21) | Interactive US segmentation | CC BY-NC 4.0 | SonoCorpus (53 old public sets) | Profile | None | S16, S7 (FUSEP) | 13 |
| **MRI_BreastSeg** ([GitHub](https://github.com/FloXyPython/MRI_BreastSeg)) | **POST-CUTOFF** specialist (October 2026) | 3D U-Net | — | MAMA-MIA + private cohorts (trained on MAMA-MIAAI masks) | Yes | None | S15, S14 (MRI ceiling) | 12 |
| **TopAneu TA36 docker** ([Zenodo](https://zenodo.org/records/21959166)) | **POST-CUTOFF** (2026-08-15) | Vessel segmenter | — | **Trained on post-cutoff TA36 labels**: upper bound only, never a start | — | — | S24/S25 reference | 16 |
| TopBrain / TopCoW 2025 checkpoints | Pre-cutoff (verify release) | 3D vessel | — | TopCoW | Patch | — | S24, S25 (clean start) | 16 |

### 6.5 Ultrasound, mammography, echo, and report / VLM models

| Model / link | Release · post-cutoff? | Size / input | Licence | Pretraining data (overlap note) | 24 GB | Interpretability | Setups | Src |
|---|---|---|---|---|---|---|---|---|
| **USFM** ([repo](https://github.com/openmedlab/USFM)) | 2024 · no | US ViT | Code CC BY-NC 4.0 | ~2M multi-organ US (claimed) | Yes | None | S16, S7 | 13 |
| **USF-MAE** ([repo](https://github.com/Yusufii9/USF-MAE)) | 2025-10 · no | US MAE | Weight licence not explicit | 370k images, 46 public sets | Yes | None | S16 | 13 |
| **BUVFM** ([code](https://github.com/SCU-MILAB/AIBUS-CODE), [HF](https://huggingface.co/xenosscu/BUVFM)) | 2026-05-11 · no (Tier C-era) | Breast-US video | Unclear | 423k frames / 84k sequences | Frame sampling | None | S16, S9 | 13 |
| **EchoPrime** ([repo](https://github.com/echonet/EchoPrime)) | 2024-10 · no | Echo video VLM | Check | — | Frozen / sampled | None | S9, S55 (EchoRisk) | 13 |
| **FADA-SKD-4B** ([HF](https://huggingface.co/mshz88/FADA-SKD-4B)) | 2026-05 · no | Qwen3.5-VL-4B adapter | Apache-2.0 card + base licence | FADA annotations | QLoRA | None | S17, S47 (fetal) | 13 |
| **BreastGPT** ([page](https://yangyy-liu.github.io/BreastGPT.io/)) | **Post-cutoff or uncertain** (EMNLP 2026) | 8B | ModelScope terms ? | 1.86M instruction pairs, 17 sources | QLoRA | None | S47, S4 | 13 |
| **Mammo-CLIP / Mammo-FM** ([repo](https://github.com/batmanlab/Mammo-CLIP), [paper](https://arxiv.org/abs/2405.12255), [HF Mammo-FM](https://huggingface.co/batmanLab/Mammo-FM)) | 2024; HF repo 2026-04-10 · no | Two-tower CLIP | **Conflict:** `13` says custom academic-only (no clinical, commercial or redistribution use); `17` says CC BY 4.0 per paper / repo | Private UPMC + RSNA / VinDr | Adapter | **Mammo-SAE** (paper) | S4, S21, S54 | 13, 17 |
| **CheXagent** ([project](https://stanford-aimi.github.io/chexagent.html), [repo](https://github.com/Stanford-AIMI/CheXagent), [8B HF](https://huggingface.co/StanfordAIMI/CheXagent-8b), [paper](https://arxiv.org/abs/2401.12208)) | 2023-12 / 2024-01 · no | 8B + 2–3B variants | CC BY-NC-ND 4.0 | Public + private CXR | 2–3B adapter; 8B QLoRA marginal | None | S35, S36, S37, S47 | 10, 15, 17 |
| **MAIRA-2** ([card](https://huggingface.co/microsoft/maira-2), [paper](https://arxiv.org/abs/2406.04449)) | 2024 · no | 7B Vicuna + RAD-DINO-MAIRA-2 | MSR licence | Public + private CXR | Frozen tower + QLoRA | None | S35, S36, S37, S29 | 17 |
| **LLaVA-Med v1.5** ([HF](https://huggingface.co/microsoft/llava-med-v1.5-mistral-7b), [repo](https://github.com/microsoft/LLaVA-Med)) | 2024-05-13 · no | 7B Mistral | Research terms | PMC-15M | QLoRA | None | S29, S47 | 17 |
| RadVLM, LLaVA-Rad, CheXOne(-3B), NV-Reason-CXR-3B | Pre-cutoff (links not given in inputs) | Report VLMs | — | MIMIC-CXR | 3B: LoRA | SAE steering features (AACL 2026 paper) | S35–S37 activation-steering baselines | 17 |

### 6.6 Prior work: SAEs, model editing and weight composition in medical imaging

| Work / link | What it does | Weight edit or activation intervention? | Relevance / limitation |
|---|---|---|---|
| **SAE-Rad** ([arXiv 2410.03334](https://arxiv.org/abs/2410.03334), 2024) | SAE features on a radiology ViT for interpretable report generation | Representation / explanation | Earliest radiology SAE; no persistent edits |
| **Radiology MLLM with SAEs** ([arXiv 2507.12950](https://arxiv.org/abs/2507.12950), 2025) | SAE analysis of a radiology multimodal LLM | Analysis | No WSP edits shown |
| **Mammo-SAE** ([arXiv 2507.15227](https://arxiv.org/abs/2507.15227), 2025) | Patch-level SAE on Mammo-CLIP features | Analysis / probing | S4/S21 feature source; validate semantics causally |
| **MedSAE** ([paper](https://arxiv.org/abs/2510.26411), [code](https://github.com/EIDOSLAB/MedSAE), 2025) | SAEs on MedCLIP latents, automated feature naming | Analysis | Most explicit released SAE; automated names are not ground truth |
| **SAEs for medical image representation** ([MICCAI 2026](https://papers.miccai.org/miccai-2026/paper/4497_paper.pdf)) | SAEs on BiomedParse and DINOv3, 909,873 CT/MRI slices | Analysis | Direct S14/S15 method |
| **Med-SegLens** ([arXiv 2602.10508](https://arxiv.org/abs/2602.10508), 2026) | SAE latent alignment / model diffing for SegFormer and U-Net across datasets | Analysis / diffing | Segmentation feature alignment (S2, S33, S39) |
| **Universal Boosts, Specific Suppressors** ([AACL 2026](https://aclanthology.org/2026.aacl-long.102/), [arXiv](https://arxiv.org/abs/2605.24977)) | Causal SAE features + decoding-time steering in RadVLM, LLaVA-Rad, CheXOne | **Activation steering, no weight update** | S35–S37 baseline; suppressors are backbone-specific |
| **CXR pneumonia activation steering** ([arXiv 2606.20852](https://arxiv.org/abs/2606.20852)) | CAA on MedGemma-4B, NV-Reason-CXR-3B, CheXOne-3B; gain on 1 of 3 | Activation steering | Null / control evidence; calibration warning |
| **Med-LEGO** ([arXiv 2503.01164](https://arxiv.org/abs/2503.01164), 2025) | SVD-LoRA modules in ViT Q/V, merged without data (0.18% params) | **Weight / adapter composition** | Mechanical baseline for S39/S45; not interpretability-guided |
| **X-Edit** ([MICCAI 2026](https://papers.miccai.org/miccai-2026/1164-Paper1503.html)) | Closed-form null-space parameter updates to medical ViTs, causal-trace localization, 6 datasets | **Direct weight edit** | Closest precedent for S10/S11/S46; finite-anchor guarantee; no cross-site evaluation |
| **M³Bench** ([arXiv 2607.05310](https://arxiv.org/abs/2607.05310), [site](https://biomed-ai-lab-u-michgan.github.io/M3Bench/)) | 10-task medical VLM editing benchmark: reliability, locality, generality, temporality | Benchmark of weight editing | Metric template for S46/S47/S51 |

**Implication.**

- No input reports a published, durable, interpretability-guided *weight* edit that improves medical-imaging performance under distribution shift.
- X-Edit is the only direct medical weight-editing method, and it does not evaluate cross-site shift.
- Most SAE "control" work steers activations at inference.
- So the portfolio's shift setups (S1/S7/S8/S16/S30) test something that has not been demonstrated.
- The maintenance and locality setups (S10/S11/S24/S46) have a mechanical precedent (X-Edit, ROME/MEMIT-style). That precedent is usable as arm M.

---

## 7. Experimental setup catalog (S1–S56)

**How to read an entry.**

- **Problem:** the practitioner situation.
- **WSP hypothesis:** why edits might beat fine-tuning (H-codes).
- **Instantiation(s):** backbone × dataset (D/C IDs from §5), preferring Tier A/B. When no post-cutoff dataset exists, the entry says so and names the fallback.
- **F / G:** what each arm does. Arms E, M, random-edit and edit-reversion controls always apply (§3, P2 and P11), so they are not repeated.
- **Metrics:** primary, then guardrails.
- **Helps / doesn't:** the concrete outcome patterns, using the §3 P9 default margins unless stated.
- **24 GB:** feasibility on one 24 GB GPU.
- **Ready:** readiness code (§5).
- **Confounds:** what to control.

**Note on "spurious shortcut" framings.**

- Following the investigator's preference, no setup is framed as shortcut removal.
- Five setups came close in the brainstorm. They are **reframed** here:
  - **S7:** site invariance → *unseen-site generalization*, scored only on unseen-site performance;
  - **S10:** error-family patching → *post-market defect correction*;
  - **S28:** demographic recoverability → *capability removal from a released embedding*, deprioritized;
  - **S31:** view subgroups → *worst-acquisition-group performance*;
  - **S42:** trojans → *supply-chain security*.
- No setup is dropped. Confound pre-audits (for example a site-from-image probe) are kept only as **data hygiene** (P4), not as the object of study.

---

### Theme 1. Distribution shift: site, scanner, vendor, protocol, population

#### S1. Cross-institution / cross-country transfer with tiered target labels (H1)

- **Problem.** A classifier built at hospital A loses performance at hospital B. Causes include scanners, processing LUTs, patient mix and geography. This is the most common deployment failure.
- **WSP hypothesis.** Site differences live in a few dominant feature directions. Directions estimated from *unlabeled* A-vs-B embeddings can be projected out, or normalization statistics re-centred. This uses unlabeled target data that k-shot fine-tuning ignores (H1).
- **Instantiations.**
  1. **Primary:** RAD-DINO (or CXR-FM / MedImageInsight), fine-tuned on CheXpert/MIMIC (D) for findings that match Naija-CXR's schema → **Naija-CXR (D02, A)**, R0–R2. RAD-DINO's pretraining sources exclude Nigerian data.
  2. CT: nnFoundation-CNN or CT-FM tumor detector trained on Swiss hospitals → Turkish hospitals in **CancerVerse (D12)**, if site IDs are recoverable.
  3. MRI: RSNA Knee (D44), slice encoder (DINOv3-B or MRI-CORE) + study pooling, site- or language-held-out. Only valid if per-study site metadata exist.
  4. Dental: MOPG-7 (D07) clinic 1 → clinic 2.
  5. *Fallback:* the Tier C pilot RadM-Bench (C32) EN → ZH. Tier D (PadChest, VinDr) only as extra sources.
- **F / G.**
  - F: LP-FT/LoRA on k target labels, BN/LN adaptation, augmentation, Opus pseudo-labels on the unlabeled pool.
  - G: F plus site-direction projection in residual streams, head rescaling, and a rank-1 classifier edit toward target class means estimated from pseudo-labels.
- **Metrics.** Target macro-AUROC/AUPRC per finding. Guardrails: source AUROC retention (≤0.005 drop), worst-finding AUROC, ECE, churn.
- **Helps / doesn't.**
  - Helps: G − F ≥ 0.02 at R1/R2 (k ≤ 25), with edit contribution ≥ 0.01 and source drop ≤ 0.005.
  - Doesn't help: G ≈ F at all k, or the gain vanishes when edits are reverted (i.e. it came from training).
- **24 GB.** Yes (ViT-B; streamed data).
- **Ready.** **RV.**
  - Naija-CXR counts, label schema, split and licence (CC BY vs non-commercial) must be verified first.
  - The size is unknown, so power may be inadequate.
  - CancerVerse is RN (licence review).
- **Confounds.**
  - Label-definition mismatch masquerades as covariate shift. Harmonize first; see S43.
  - Prevalence shift (Nigeria vs US).
  - Dedup follow-ups.
  - Fixed preprocessing for both arms.

#### S2. Multi-vendor segmentation (cardiac MRI in the brainstorm) (H1, H2)

- **Problem.** Segmenters trained on vendors A+B fail on vendors C/D. Contrast and intensity profiles differ.
- **WSP hypothesis.** Vendor effects concentrate in stem and normalization layers, while decoder shape priors transfer. A probe-guided stem rescale plus a normalization-statistic transplant should leave the decoder intact.
- **Instantiations.**
  - **No post-cutoff multi-vendor cardiac MRI dataset exists** (CMRx4DFlow2026, C23, is reconstruction-only and date-unresolved).
  - Analogous Tier A vendor shifts:
    1. **FUSEP (D30):** Samsung → SonoScape/GE fetal-US detection, with DINOv3-B or USFM;
    2. **COBRA2026 (D13):** Elekta ↔ Varian CBCT reconstruction;
    3. **TopAneu (D23):** center/modality shift for vessel and aneurysm segmentation;
    4. TotalSegmentator CT v3 additions (D16), where the metadata expose scanners.
  - *Fallback (D):* M&Ms-1/2 with nnU-Net, as a contaminated mechanistic study only.
- **F / G.**
  - F: fine-tuning, intensity augmentation, BN adaptation.
  - G: F plus probe-guided stem-channel rescaling, norm-stat transplant, channel ablation. The decoder is frozen by construction.
- **Metrics.** Target Dice / mAP / HU-MAE (per instantiation). Guardrails: source performance, HD95, churn.
- **Helps / doesn't.**
  - Helps: G closes ≥ 0.02 Dice/mAP more than F at k ∈ {1, 3, 5}, with the edit gain confined to stem/norm tensors.
  - Doesn't help: BN re-estimation alone (arm M) matches G.
- **24 GB.** Yes, patch-based.
- **Ready.** RN for the FUSEP / COBRA analogues. NR for cardiac MRI under Tier A.
- **Confounds.** The same nnU-Net plan and spacing for both arms. FUSEP has no patient IDs.

#### S3. Multi-site prostate MRI: protocol and coil shift

- **Problem.** Endorectal coil vs none, T2 protocols, 1.5T vs 3T.
- **WSP hypothesis.** As S2, plus a geometric (coil deformation) component. This tests whether edits handle more than intensity.
- **Instantiations.**
  - **No post-cutoff prostate MRI** with images or masks was found (PiCaRad, C22, is PDF only).
  - *Fallback (D):* the 6-site prostate data plus PI-CAI, leave-one-site-out, as a contaminated mechanistic study only.
  - *Closest Tier A protocol-shift substitute:* TotalSegmentator MRI v3 additions (D25), using sequences and sources from `meta.csv`.
- **F / G.** As S2.
- **Metrics.** Held-out-site Dice. Worst-site Dice is co-primary.
- **Helps / doesn't.** As S2. Report per site.
- **24 GB.** Yes.
- **Ready.** **NR** under Tier A; D-only.
- **Confounds.** Small sites (30–80 volumes); public leaderboards are known to the agent.

#### S4. Mammography vendor and image-processing shift (H1, H5)

- **Problem.** Screening models trained on one vendor's "for presentation" images degrade on other vendors.
- **WSP hypothesis.** Vendor processing is a largely global, monotone intensity/texture transform. It may be correctable with a stem or normalization edit.
- **Instantiations.**
  - **No adequately powered post-cutoff multi-vendor mammography set exists.**
  - Options:
    1. **LUMINA (C24, Tier C):** 6 vendors, 468 patients. Mammo-FM/Mammo-CLIP (Mammo-SAE features) or DINOv3; vendor A → held-out vendor. Pilot only.
    2. **OMAMA HYFOWN (D34):** conditional on proving new patients.
    3. Tier D EMBED / VinDr-Mammo / CMMD as sources.
- **F / G.**
  - F: LP-FT/LoRA, vendor-aware intensity augmentation, temperature scaling.
  - G: F plus vendor-probe-guided stem/normalization edits; Mammo-SAE-derived feature rescaling.
- **Metrics.** Patient/exam AUROC; sensitivity at 90% specificity. Guardrails: worst-vendor AUROC, calibration, churn.
- **Helps / doesn't.** As P9. Expected to be a **pilot**: 468 patients cannot resolve 0.02.
- **24 GB.** Yes for patches / frozen encoder. Do not resize away lesion detail without a fair-resolution control.
- **Ready.** RN (Tier C, Kaggle, CC BY-NC); RA/RV for OMAMA.
- **Confounds.**
  - Fixed view fusion.
  - Mammo-FM licence conflict (academic-only vs CC BY).
  - Mammo-CLIP saw RSNA / VinDr.

#### S5. CT reconstruction kernel / slice thickness / CBCT shift (H5)

- **Problem.** Sharp vs soft kernels and thin vs thick slices change texture. CBCT differs from diagnostic CT.
- **WSP hypothesis.** Kernel differences are mostly frequency-domain. An analytically motivated first-layer filter edit (attenuating high-frequency response) approximately inverts them.
- **Instantiations.**
  - **No post-cutoff paired-kernel CT exists.**
  - Tier A options:
    1. **CancerVerse (D12):** kernel- and slice-thickness-stratified shift using per-scan metadata, where available. Train on soft-kernel scans, test on sharp. Tumor detection or segmentation with nnFoundation-CNN or nnU-Net.
    2. **COBRA2026 (D13):** diagnostic/planning CT → CBCT reconstruction, with **paired** planning CT as a (deformed) reference.
    3. Longitudinal liver CT (D17): dose and acquisition metadata (A-r).
  - B1: Spinal-MM (D18) dual-energy.
  - *Fallback (D):* LIDC / NLST paired kernels. LUCQUE (D19, A-p) if confirmed.
- **F / G.**
  - F: fine-tuning, kernel augmentation, LoRA.
  - G: F plus probe-localized high-frequency stem-filter edits, or an inserted fixed low-pass/sharpen circuit.
- **Metrics.** Target AUROC/Dice (or HU-MAE/SSIM for COBRA). **Paired consistency** where pairs exist. Guardrails: source performance, churn.
- **Helps / doesn't.**
  - Helps: G's edit recovers ≥ 50% of the kernel-induced drop with ≤ 1% of parameters changed, and beats F at k ≤ 10.
  - Doesn't help: augmentation (F) matches G.
- **24 GB.** Yes, patch / 2D. Not the full 950 GB COBRA or full-volume runs.
- **Ready.** CancerVerse RN (kernel-metadata completeness to verify; licence); COBRA RN.
- **Confounds.**
  - Kernel is confounded with site and scanner in CancerVerse; a pre-audit is needed.
  - COBRA planning CT is not same-time truth.

#### S6. MRI field-strength / scanner-upgrade shift (H1, H5)

- **Problem.** A site upgrades from 1.5T to 3T or changes vendor. Segmentation and volumetrics shift.
- **WSP hypothesis.** As S2, plus systematic volume bias that a bias/affine output edit can correct exactly.
- **Instantiations.**
  1. **TotalSegmentator MRI v3 additions (D25):** split by field strength or vendor from `meta.csv` (completeness to verify). Start: TotalSegmentator MRI v2 or nnFoundation.
  2. **OpenBrain (D27, B2):** scanner and field-strength fields where present. Start: **NeuroVFM / BrainFedFM / Brain2Vec** (post-cutoff), with source-dataset-disjoint tests.
  3. CFB-GBM v2 (D28, conditional): Siemens 1.5T vs 3T.
  4. TopAneu (D23) MRA centers.
  - *Best paired data is Tier C:* **MRIxFields2026 (C15)**, travelling volunteers at 0.1–7T; secondary analysis only.
- **F / G.**
  - F: fine-tuning/LoRA, intensity augmentation, SynthSeg-style contrast randomization.
  - G: F plus field-strength-probe-guided stem/normalization edits; output-bias edit for volumes.
- **Metrics.** Dice or lesion F1. **Volume bias (Bland–Altman)** on paired subjects (C15 only). Guardrails: source Dice, churn.
- **Helps / doesn't.**
  - Helps: G removes volume bias with a closed-form edit at k ≤ 5, where F needs more labels.
  - Doesn't help: SynthSeg-style augmentation (F) already removes the bias.
- **24 GB.** Yes (patches, cached features).
- **Ready.** D25 / D27 RN; C15 RA (Synapse).
- **Confounds.** No Tier A paired subjects, so causal claims rest on Tier C. Field strength is confounded with site in D25/D27.

#### S7. Zero-target-data domain generalization (multi-source → unseen site) (H1 at R0)

*Reframed:* the target is unseen-site performance, not "removing site information".

- **Problem.** The developer does not know where the model will be deployed. They have several labelled training sites.
- **WSP hypothesis.** With site labels on the training data, the agent can find site-encoding units or directions and build invariance by construction. The comparators are GroupDRO, IRM, CORAL and augmentation.
- **Instantiations.**
  1. **FUSEP (D30):** train on 2 hospitals/devices, test on the 3rd (rotate).
  2. **MOPG-7 (D07):** train on clinics 1–3, test on clinic 4 or DentalOPG-1550 (D08).
  3. **TopAneu (D23):** centers 1/2/4 → organizer-held center 3, if the challenge allows evaluation; otherwise rotate.
  4. **COBRA2026 (D13):** 5 centers → 1.
  5. **CancerVerse (D12):** hospitals.
  6. OpenBrain (D27): 607 sources → held-out sources with sealed manual labels.
  7. RSNA Knee (D44): sites, if exposed.
- **F / G.**
  - F: any DG method.
  - G: F plus site-direction ablation and probe-guided head pruning.
- **Metrics.** Mean and **worst** unseen-site mAP/Dice/AUROC. Guardrail: in-distribution performance.
- **Helps / doesn't.**
  - Helps: worst-unseen-site gain ≥ 0.02 over the best DG method.
  - Doesn't help: G ≈ GroupDRO/CORAL, or site-invariance edits lower unseen-site performance. The latter would be informative: site information is useful.
- **24 GB.** Yes.
- **Ready.** RN (FUSEP, MOPG-7, COBRA, TopAneu, CancerVerse).
- **Confounds.**
  - No access to unseen-site data, not even unlabeled.
  - FUSEP and MOPG-7 lack patient IDs.
  - In FUSEP, hospital is confounded with device.

#### S8. Unlabeled-target adaptation: edit vs test-time adaptation (H1)

- **Problem.** At go-live there is a stream of unlabeled target images and no annotation budget.
- **WSP hypothesis.** One-shot statistic/feature edits computed from the unlabeled pool are more stable than gradient TTA (TENT, SHOT, self-training), which is known to fail often.
- **Instantiations.** Any S1–S7 instantiation at R1 only. Best-powered or cleanest:
  - **FUSEP (D30)**, cross-hospital;
  - **TotalSegmentator CT v3 pediatric additions (D16)** as the unlabeled target for an adult model;
  - **COBRA2026 (D13)** held-out vendor;
  - **CMB V25 (D36)** new series as an *unlabeled* pool, with a test only after new annotation;
  - Naija-CXR (D02).
- **F / G.**
  - F: TENT/SHOT/pseudo-label self-training, BN re-estimation, Opus pseudo-labels.
  - G: edits computed from unlabeled statistics (projection, norm transplant, prototype rank-1), plus TTA if desired.
  - The model is frozen before test (P6).
- **Metrics.** Target metric, plus **stability**: variance across ≥5 runs and the failure rate (runs below the start checkpoint).
- **Helps / doesn't.**
  - Helps: equal mean with ≥ 50% lower failure rate, or higher mean at equal stability.
  - Doesn't help: arm M (BN re-estimation) is as stable as G.
- **24 GB.** Yes.
- **Ready.** RN (D30, D16, D13); RX for D36.
- **Confounds.** Same unlabeled pool for both arms; no online test-time updating.

---

### Theme 2. Post-deployment maintenance and change control

#### S9. Temporal-drift hotfix with a small post-drift sample (H2, H7)

- **Problem.** Months after deployment, performance slips (new fleet, protocol, case mix). There are 50–200 new labels and no budget for full revalidation.
- **WSP hypothesis.** A localized fix gives the same post-drift gain with less churn on unaffected cases.
- **Instantiations.**
  1. **CancerVerse (D12):** 2010–2025 acquisition years. Train on early years, then hotfix on later years (tumor detection / screening). Start: nnFoundation-CNN or nnU-Net.
  2. **RSNA Knee (D44):** only if temporal metadata exist (not reported).
  3. Longitudinal liver CT (D17, A-r): T0 → T1/T2 domain.
  4. CFB-GBM v2 (D28): t0 → t1/t2, conditional.
  - *Best data is Tier C:* **TAIX-Ray (C01)**, 2010–2023 ICU CXR with 18 mobile units and ±100-day date shift; RAD-DINO or DINOv3. Report as a flagged secondary analysis.
  - MIMIC-CXR-DB (D06, B2): MIMIC timestamps, contaminated.
- **F / G.**
  - F: LoRA/last-layer fine-tuning on n post-drift labels, augmentation, recalibration.
  - G: F plus probe-guided rescaling of drift-sensitive channels, sparse reversible edits.
  - Budget: 2 GPU-hours.
- **Metrics.**
  - Post-drift AUROC / sensitivity at FP/scan.
  - Co-primaries: pre-drift retention and **churn on a frozen pre-drift reference set**.
  - Diff footprint.
- **Helps / doesn't.**
  - Helps: equal post-drift gain with ≥ 50% less churn, or a better gain at equal churn.
  - Doesn't help: LoRA at matched rank has equal churn.
- **24 GB.** Yes (patch 3D; ViT-B CXR).
- **Ready.** CancerVerse RN (drift must first be shown to exist); TAIX-Ray RN (Tier C).
- **Confounds.**
  - Confirm the drift (measure the drop first).
  - Exclude patients seen in both periods.
  - CancerVerse v3.5.1 corrected time offsets, so freeze the snapshot.

#### S10. Post-market defect correction ("bug ticket" patching) (H2, H3)

*Reframed* from error/shortcut patching to defect correction.

- **Problem.** Radiologists flag 10–30 failures of one kind. The team must patch them without breaking anything else.
- **WSP hypothesis.** The canonical model-editing case: a specific, local and auditable change. X-Edit-style closed-form null-space edits are a ready precedent.
- **Instantiations.**
  - Tier A error families must be **curated** (RX):
    - **MFXR (D01):** a family such as Monteggia with a subtle radial-head displacement. Needs annotation; the pilot found no subgroup labels.
    - **DentalOPG-1550 (D08):** missed apical abscesses.
    - **TopAneu (D23):** missed aneurysms at a rare location.
    - **LUCQUE (D19):** a nodule FP family.
  - B2: **REFLACX discrepancy tables (D43)** give radiologist error-family labels on old MIMIC images (mechanistic). XQA-Chest (D03) image-vs-report disagreements.
- **F / G.**
  - F: hard-example fine-tuning, LoRA, replay.
  - G: F plus X-Edit / ROME-style rank-1 or null-space edits localized by causal tracing.
- **Metrics.** Sensitivity on **held-out family members** (generalization of the fix). Guardrails: overall AUROC, specificity, churn outside the family.
- **Helps / doesn't.**
  - Helps: held-out-family gain ≥ F's, with ≥ 50% less out-of-family churn.
  - Doesn't help: G fixes only the flagged cases (memorizes them) and does not generalize.
- **24 GB.** Yes.
- **Ready.** **RX** (family annotation); D43 RA.
- **Confounds.** The family definition must not be visible as metadata. Both arms get the same flagged cases.

#### S11. Locked-model change control under a parameter-diff budget (PCCP-style) (H3)

- **Problem.** For a cleared device, changes fall under a Predetermined Change Control Plan. Small, bounded, documented diffs are easier to justify.
- **WSP hypothesis.** WSP yields sparse, reversible, explainable diffs. The fair comparison is *budgeted* fine-tuning (sparse FT, rank-1 LoRA, BitFit, last layer).
- **Instantiations.**
  - An **overlay** on S1 / S9 / S24 / S30 instantiations, with a hard cap of ≤ 0.1% and ≤ 0.01% of parameters, or pre-declared modules only.
  - A natural locked model is **HoloCT-4B (post-cutoff)** extended per S56, or nnFoundation-CNN.
  - Each arm submits a PCCP-style change log.
- **F / G.**
  - F: budgeted sparse fine-tuning.
  - G: edits within the same budget.
- **Metrics.** Target gain per changed parameter; **blinded reviewer** auditability and accept/reject (radiologist + regulatory reviewer).
- **Helps / doesn't.**
  - Helps: G wins on performance at equal budget, or on reviewer acceptance at equal performance.
  - Doesn't help: rank-1 LoRA matches G on both.
- **24 GB.** Yes.
- **Ready.** RN as an overlay.
- **Confounds.** Normalize the change-log format; blind reviewers to arm.

#### S12. Input-pipeline changes: photometric inversion, windowing, bit depth, resolution (H5) — **positive control / tool gate**

- **Problem.** A site's DICOM export changes (MONOCHROME1/2, default window, 8- vs 12-bit, pixel spacing) and the model breaks silently.
- **WSP hypothesis.** These changes are exactly invertible in weights:
  - sign-flip the first layer + adjust the bias to undo inversion;
  - interpolate positional embeddings to handle resolution.
- **Instantiations.** Simulated pipeline changes on Tier A data with frozen preprocessing:
  - **Naija-CXR (D02)** or **MFXR (D01)** for X-ray;
  - **CancerVerse (D12)** raw HU for windowing / bit depth;
  - **CBCT-IQ (D14)** for kV / recon-type changes;
  - LUMINA (C24) 12–14-bit DICOM as a Tier C variant.
- **F / G.**
  - F: fine-tuning on k target images.
  - G: analytic weight edits.
- **Metrics.** AUROC recovery vs the start model on the original pipeline; time-to-fix.
- **Helps / doesn't.**
  - **G must recover ≥ 95% at k = 0 within an hour.** If it does not, the tooling is inadequate and the main portfolio should not run.
  - F needing k > 0 is the expected contrast.
- **24 GB.** Yes (CPU-feasible).
- **Ready.** RN.
- **Confounds.** In practice one would fix the preprocessing. This setup measures the edit machinery, not practical need (P14).

#### S13. Prevalence shift and recalibration (screening ↔ diagnostic) — **null control** (Null, H7)

- **Problem.** ED → outpatient deployment breaks calibration and PPV at the threshold.
- **WSP hypothesis / null.** The best fix (bias/temperature) already is a weight edit, so we expect G ≈ F ≈ arm M.
- **Instantiations.**
  - **CancerVerse (D12):** 8,799 verified healthy patients allow screening-prevalence resampling.
  - **MFXR (D01):** 63% positive test, resampled.
  - Naija-CXR (D02).
  - XQA-Chest (D03): image- vs report-label references.
  - Tier C: LUMINA BI-RADS.
- **F / G.**
  - F: EM/BBSE prior estimation + temperature scaling.
  - G: F plus edits.
- **Metrics.** ECE and Brier at target prevalence; sensitivity and PPV at the fixed threshold.
- **Helps / doesn't.** The **expected outcome is no difference.** A G "win" here signals mis-specified parity.
- **24 GB.** Trivial.
- **Ready.** RN.
- **Confounds.** Both arms get the same prevalence-estimation tools.

#### S45. Foundation-model version upgrade (backbone v1 → v2) (H4, H5, H1)

- **Problem.** A site has a head or adapter built on backbone v1. The vendor ships v2.
- **WSP hypothesis.** A closed-form representation map (stitching), fitted on *unlabeled* paired images and baked into weights, ports the head with ~0 labels. F must re-fine-tune.
- **Instantiations.**
  1. **DINOv2-B/14 → DINOv3-B/16** on FUSEP (D30), MOPG-7 (D07) or Naija-CXR (D02). Same 768-d width; the different patch grid needs token alignment for spatial heads.
  2. **TotalSegmentator v2 weights → v3-era model** on TotalSegmentator v3 additions (D16/D25), if v3 weights exist (unverified).
  3. **MedGemma 1 → 1.5** for a CXR task.
  4. A pre-cutoff 3D encoder → **post-cutoff nnFoundation / NeuroVFM** (version jump to an unknown model; §4.1 channel 3).
  5. RSNA Knee (D44): ConvNeXt-T pipeline → DINOv3.
- **F / G.**
  - F: re-fine-tune/LoRA on k labels.
  - G: stitching/Procrustes/least-squares map baked into the first head layer, plus edits.
- **Metrics.** Fraction of v1 → v2 performance recovered at k ∈ {0, 5, 25}; label use; migration time; churn vs the v1 model.
- **Helps / doesn't.**
  - Helps: G at k = 0 ≥ F at k = 25.
  - Doesn't help: a simple linear-probe refit on k = 5 matches G.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** Paired unlabeled images are available to both arms. F may also fit a map; decide by preregistration whether a closed-form map counts as WSP (P3).

#### S46. Clinical guideline or classification revision (H2, H3)

- **Problem.** A deployed classifier or radiology LLM must follow new criteria (LI-RADS, Lung-RADS, RANO 2.0, BI-RADS, a revised fracture or vessel taxonomy) with few examples.
- **WSP hypothesis.** Knowledge edits (ROME/MEMIT-style, X-Edit) change only the cases whose label the revision changes.
- **Instantiations.**
  1. **CFB-GBM v2 (D28, conditional B1):** derived RANO 2.0 response labels vs older response logic.
  2. **TopBrain TA36 (D24):** the new 36-class schema vs the older 40/42-class maps (a taxonomy revision).
  3. **LUCQUE (D19):** Lung-RADS characteristics (A-p).
  4. Simulated revision on Tier A: a deterministic rule change, e.g. moving a threshold in a size-based category on CancerVerse lesions.
  5. Text: **M³Bench**-style edits to MedGemma on revised criteria text.
  - Tier C: AMPLIFAI (C08) LI-RADS; LUMINA BI-RADS.
- **F / G.**
  - F: fine-tuning on relabelled examples.
  - G: knowledge/rank-1 edits.
- **Metrics.** Accuracy on **label-changed** cases. Guardrail: preservation on unchanged cases (locality); temporality per M³Bench.
- **Helps / doesn't.**
  - Helps: equal changed-case accuracy with ≥ 50% fewer unintended flips.
  - Doesn't help: fine-tuning matches on both.
- **24 GB.** Yes (4B VLM via QLoRA).
- **Ready.** RV (D28 date); RN for a simulated revision on D12/D24.
- **Confounds.** Revision rules must be expressible from model outputs. A real guideline text may be in the agent's training data (fine; the target *labels* are new).

#### S54. Triage operating-point / worklist policy change (H2, H3)

- **Problem.** Raise sensitivity for one finding or subgroup without disturbing others.
- **WSP hypothesis.** A local logit/bias edit conditioned on a probe direction changes one operating point auditably.
- **Instantiations.**
  - **CancerVerse (D12):** raise sensitivity for one cancer type at fixed overall FP/scan.
  - **MFXR (D01):** raise pediatric fracture sensitivity.
  - Naija-CXR (D02): one finding.
  - Tier C: LUMINA (sensitivity at fixed specificity).
- **F / G.**
  - F: per-class thresholds, cost-sensitive fine-tuning.
  - G: F plus probe-conditioned bias edits.
- **Metrics.** Target sensitivity at the new operating point. Guardrails: other findings' sensitivity/specificity, churn.
- **Helps / doesn't.**
  - Helps only if G beats **per-class threshold changes** (the obvious F fix) on off-target churn.
  - Expected: null-leaning.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** Separate threshold changes from ranking changes (P13).

---

### Theme 3. Natural-image → medical domain gap

#### S14. DINOv3 → radiograph: closing the gap to a domain FM (H1)

- **Problem.** Natural backbones are the practitioner default. How close can they get to RAD-DINO-class performance?
- **WSP hypothesis.** Edits can:
  - re-weight relevant texture/edge features;
  - suppress colour/semantic channels;
  - rewire the stem for grayscale;
  - steer toward the domain FM's representation without labels, via closed-form maps from DINOv3 to RAD-DINO features on unlabeled images, baked into weights.
- **Instantiations.**
  1. **DINOv3 ViT-B/16 → CXR**, labelled source CheXpert/MIMIC (D), **sealed target Naija-CXR (D02)**. RAD-DINO (pretrained on MIMIC/CheXpert/NIH/PadChest/BRAX, none Nigerian) is the specialist ceiling.
  2. **DINOv3 → dental OPG**, MOPG-7 / DentalOPG-1550 (D07/D08). No dental FM exists, so use RAD-DINO as a "radiograph FM" ceiling. Fully Tier A.
  3. DINOv3 → VinDr-Ground-VQA images/labels (D40, B2) as a secondary test.
  4. DINOv3 → MSK (MFXR, D01) vs SKELEX ceiling (the pilot encoders).
  - k ∈ {10, 50, 200, 1000} + an unlabeled pool.
- **F / G.**
  - F: LP, LP-FT, LoRA, continued SSL on unlabeled radiographs (the strong competitor).
  - G: F plus edits / representation alignment. SAE-on-DINOv3 methods (MICCAI 2026) as tooling.
- **Metrics.** **Fraction of the DINOv3 → RAD-DINO gap closed** at fixed compute; target AUROC/mAP.
- **Helps / doesn't.**
  - Helps: G closes ≥ 20 percentage points more of the gap than F at small compute (preregister X).
  - Doesn't help: continued SSL (F) closes as much.
- **24 GB.** Yes (ViT-B; L at batch 1).
- **Ready.** RV (Naija); RN (dental).
- **Confounds.** Compute parity is essential. Dental images were auto-oriented/stretched to 640² (v3).

#### S15. DINOv3 → CT/MRI slices: HU-windowing stem circuit (H5) — **positive control #2**

- **Problem.** Natural backbones expect 8-bit RGB. CT is 12-bit HU. Practitioners hack in three windows mapped to RGB.
- **WSP hypothesis.** A hand-built piecewise-linear multi-window circuit (clamps and ReLUs in an inserted layer) carries diagnostic dynamic range into the pretrained stem.
- **Instantiations.**
  1. **DINOv3-B on CancerVerse (D12)** raw-HU slices: tumor presence or 2D segmentation with a light decoder.
  2. **TotalSegmentator CT v3 additions (D16):** 2D organ segmentation.
  3. ImageCAS-X (D15): coronary.
  4. MRI variant: **MAMA-MIAAI (D26)** DCE breast (bias-field/intensity), MRI_BreastSeg ceiling.
  - *Fallback (D):* RSNA ICH → CQ500.
- **F / G.**
  - F: standard 3-window RGB + fine-tuning, or a learned 1×1 adapter.
  - G: F plus the inserted window circuit and stem edits.
- **Metrics.** AUROC or Dice at the external split, low k. Same raw HU input for both arms.
- **Helps / doesn't.**
  - Helps: G ≥ the learned adapter at k ≤ 50, with interpretable windows.
  - Doesn't help: the 1×1 adapter learns the same thing.
- **24 GB.** Yes (2D).
- **Ready.** RN.
- **Confounds.** Hold preprocessing fixed. Backbone/task source overlap: NV-Reason-CT saw CancerVerse, but DINOv3 did not.

#### S16. Natural → ultrasound (speckle domain) (H1)

- **Problem.** Ultrasound has speckle, operator dependence and vendor differences. Natural FMs transfer poorly.
- **WSP hypothesis.** Speckle-sensitive high-frequency channels can be found and attenuated. This also tests WSP beyond X-ray/CT.
- **Instantiations.**
  1. **DINOv3-B → FUSEP (D30)** 14-structure detection. Ceilings: USFM / USF-MAE (pre-cutoff) and **SonoBase / UltraSAM3 (post-cutoff)**. Exclude their training sets from test. The inputs do not list UltraSAM3's 37 sets or SonoCorpus' 53, so verify that FUSEP is in neither.
  2. **PU2756 (C25, Tier C):** benign/malignant + Dice. The best US diagnostic set, 16 days pre-cutoff.
  3. Open-H-RF / EPFL RF (D31/D32): RF → B-mode reconstruction transfer (no diagnosis).
  4. BUS-Large (D33): if access is granted.
- **F / G.**
  - F: LP-FT/LoRA, speckle/intensity augmentation, UDA.
  - G: F plus probe/SAE-guided speckle-channel attenuation, inserted adapter circuits.
- **Metrics.** mAP@[.5:.95] (FUSEP); AUROC + Dice (PU2756). Guardrails: source-site performance, ECE, churn.
- **Helps / doesn't.**
  - Helps: G − F ≥ 0.02 mAP at k ≤ 25, plus edit contribution.
  - Doesn't help: speckle augmentation matches G.
- **24 GB.** Yes (640 px detector, AMP).
- **Ready.** FUSEP RN (data terms "research"); PU2756 RN (Tier C).
- **Confounds.** Remove calipers and overlays for both arms. FUSEP patient count is unknown and the FUSEP repo model zoo must be denylisted.

#### S17. CLIP-style VLM → radiology vocabulary editing (H1)

- **Problem.** General CLIP/BiomedCLIP misread radiology terms. Practitioners use them zero-shot.
- **WSP hypothesis.** Rank-1 edits to the text tower or projection re-map term embeddings to image-concept centroids, or build a classifier for a new finding from its text definition.
- **Instantiations.**
  1. OpenCLIP / SigLIP2 / BiomedCLIP / MedCLIP (with **MedSAE**) → **VinDr-Ground-VQA (D40)** 22 findings, zero/1/5-shot, with fresh image-grouped holdout.
  2. **MIMIC-Ext-CXR-QBA (D05)** 237 finding entities for concept estimation (training only).
  3. Naija-CXR (D02) as a Tier A test if its label schema fits.
  - MetaStructAtlas (D39) for PET concepts, when released. FADA (C28) for fetal US.
- **F / G.**
  - F: prompt engineering/tuning, linear probe, CLIP-adapter.
  - G: F plus text/projection rank-1 edits.
- **Metrics.** Macro-AUROC over long-tail findings at k ∈ {0, 1, 5}. **Retrieval on unedited concepts** (locality).
- **Helps / doesn't.**
  - Helps: G ≥ prompt tuning with no locality loss.
  - Doesn't help: a prompt ensemble matches G.
- **24 GB.** Yes.
- **Ready.** RA (PhysioNet credentials for D40/D05).
- **Confounds.** D40 labels re-express old VinDr labels (B2), so it is not confirmatory. Same text prompts for both arms.

---

### Theme 4. Modality transfer and new inputs

#### S18. CT → MRI organ segmentation (H1, H5)

- **Problem.** Plenty of CT labels, few MRI labels.
- **WSP hypothesis.** Decoder shape priors transfer; the stem's appearance mapping does not (contrast inversions). Stem edits with a frozen decoder beat fine-tuning at k ≤ 3.
- **Instantiations.**
  1. **TotalSegmentator CT model → TotalSegmentator MRI v3 additions (D25)**: shared structure names; 50 MRI structures. TotalSegmentator MRI as the reference.
  2. **TopBrain TA36 (D24):** CTA → paired MRA, 25 pairs (B1).
  3. TopAneu (D23): CTA → MRA centers.
  4. nnFoundation-CNN or VISTA3D starts.
  - *Fallback (D):* AMOS, CHAOS.
- **F / G.**
  - F: fine-tuning, CycleGAN/intensity augmentation, MRI SSL.
  - G: F plus stem edits, frozen decoder.
- **Metrics.** Mean Dice over shared organs on the MRI test, at k ∈ {0, 1, 3, 10}. Guardrail: CT Dice if dual-modality.
- **Helps / doesn't.**
  - Helps: G ≥ F + 0.02 Dice at k ≤ 3.
  - Doesn't help: intensity augmentation closes the gap.
- **24 GB.** Yes (patches).
- **Ready.** RN.
- **Confounds.** Identical spacing and label set. The TotalSegmentator MRI model was trained on v2 MRI data, so use only v3 additions for test.

#### S19. 2D → 3D weight inflation and slice-aggregation circuits (H4, H5)

- **Problem.** Most FMs are 2D, while clinical CT/MRI is 3D.
- **WSP hypothesis.** Interpretability-guided inflation (choosing which channels get depth; hand-wiring cross-slice attention) beats naive I3D inflation plus fine-tuning.
- **Instantiations.**
  1. **RAD-DINO / DINOv3 → CancerVerse (D12)** study-level cancer presence. Native-3D ceilings: nnFoundation, NV-Reason-CT (**not** on CancerVerse, which it trained on), HoloCT, Merlin, CT-FM.
  2. **RSNA Knee (D44):** 2D slice encoder + study aggregation (the plan's 2.5D pipeline).
  - Tier C: FLARE26 Task 5 (C29), ReXGroundingCT (C09).
- **F / G.**
  - F: standard centered/uniform inflation, attention pooling.
  - G: interpretability-guided inflation and slice circuits.
- **Metrics.** Study-level AUROC at the external split.
- **Helps / doesn't.**
  - Helps: G > F inflation by ≥ 0.02 at equal compute.
  - Doesn't help: attention pooling matches.
- **24 GB.** Yes (2D encoder + pooling); native 3D comparators need profiling.
- **Ready.** RN (D12); RA (D44).
- **Confounds.** Equal compute.

#### S20. Adding an input modality to a deployed model (CT → PET/CT; CTA → fluoroscopy) (H2, H5)

- **Problem.** A validated CT model must use PET (or procedural video) without losing its CT behaviour.
- **WSP hypothesis.** Insert a PET channel whose stem weights are hand-wired to a known-good detector (SUV threshold or local max). Leave the CT path identical at initialization, so there is no degradation at step 0.
- **Instantiations.**
  - **No labelled post-cutoff PET/CT exists.**
    - **CMB V25 (D36):** new PT/NM series, but needs annotation (RX).
    - **MetaStructAtlas (D39):** 490 FDG PET/CT, unreleased.
    - **TAIR (D37):** CTA/MRA + fluoroscopy; labels promised for December 2026.
  - *Fallback:* PSMA-PET-CT-Lesions (C31, Tier C); autoPET / FDG-PET-CT-Lesions / HECKTOR (D).
  - Start: a HoloCT-4B or nnFoundation CT pathway.
- **F / G.**
  - F: add the channel with zero/random init and fine-tune.
  - G: hand-wired PET stem + probe-guided fusion.
- **Metrics.** Lesion Dice, lesion F1, false-positive volume (bladder/brain uptake). Guardrail: CT-only churn.
- **Helps / doesn't.**
  - Helps: G ≥ F at k ≤ 10 and zero CT-path churn.
  - Doesn't help: zero-init fine-tuning gives the same.
- **24 GB.** Patch-based 3D: plausible.
- **Ready.** **NR** on Tier A until annotation/release; C31 RN as a contaminated pilot.
- **Confounds.** Equal budgets; same channel-add options.

#### S21. Projection-radiography FM → mammography / DBT (or dental) — null-leaning (Null, H1)

- **Problem.** Mammography FMs are limited. Can a CXR FM be repurposed?
- **WSP hypothesis.** Edits repurpose rib/edge features toward calcification and mass morphology. A fair test of cross-modality repurposing, expected to be close.
- **Instantiations.**
  - **No post-cutoff mammography set is adequately powered.**
    - LUMINA (C24) ROI-level: RAD-DINO → LUMINA with a Mammo-CLIP ceiling.
    - DBT-2026 (C26, DUA).
    - OMAMA HYFOWN (D34), conditional.
  - **Tier A substitute:** RAD-DINO → dental OPG (MOPG-7 / DentalOPG-1550, D07/D08), i.e. projection radiography with different anatomy.
- **F / G.** Same ROI extraction. F: LP-FT/LoRA. G: F plus feature-repurposing edits.
- **Metrics.** AUROC / mAP at k ∈ {50, 500}.
- **Helps / doesn't.** Expected null; a G win would be surprising and informative.
- **24 GB.** Yes (ROI).
- **Ready.** RN (dental, LUMINA).
- **Confounds.** ROI-level task to avoid resolution confounds.

#### S50. New contrast agent, tracer or protocol (missing or new channels) (H4, H5)

- **Problem.** A multi-input model meets an abbreviated protocol (missing sequences), a new contrast phase or a new tracer.
- **WSP hypothesis.** Missing-channel edits (re-routing, mean-imputation circuits) and new-channel insertion preserve validated behaviour.
- **Instantiations.**
  1. **RSNA Knee (D44):** drop sequences to simulate an abbreviated protocol.
  2. **MAMA-MIAAI (D26):** DCE timepoint dropout (abbreviated breast MRI).
  3. **CancerVerse (D12):** contrast phases, if available in the metadata.
  4. TotalSegmentator MRI v3 (D25): sequence mix.
  5. CFB-GBM v2 (D28): missing modalities.
  - New tracer: **none post-cutoff**. Tier C PSMA-PET (C31) has 18F vs 68Ga; no FAP data found.
  - Tier C AMPLIFAI multiphase.
- **F / G.**
  - F: modality-dropout training, fine-tuning.
  - G: F plus channel-rerouting edits.
- **Metrics.** Performance with the abbreviated protocol vs full. Guardrail: full-protocol churn.
- **Helps / doesn't.** Helps: G's missing-channel performance ≥ F's dropout-trained model with zero full-protocol churn.
- **24 GB.** Yes (2.5D).
- **Ready.** RA (D44), RA (D26), RN (D12/D25).
- **Confounds.** The simulated missingness pattern must be identical for both arms.

---

### Theme 5. Label scarcity, rare findings, weak labels

#### S22. Rare finding with prior-knowledge injection (H1)

- **Problem.** Critical but rare findings have fewer than 50 positives per institution.
- **WSP hypothesis.** WSP helps only if it injects information *from outside the labels*. Sources:
  - anatomical rules (e.g. the radiocapitellar line);
  - SAE features trained on large unlabeled data;
  - transfer from a related common finding.
- **Instantiations.**
  1. **MFXR (D01):** Monteggia, with the radiocapitellar-line rule. The pilot's Tier A task; extend with knowledge channels.
  2. **DentalOPG-1550 (D08):** rare classes such as apical abscess.
  3. **TopAneu (D23):** rare aneurysm types and locations.
  4. **CancerVerse (D12):** rare cancer types.
  - Tier C: BDCXR-3257 (viral vs bacterial pediatric pneumonia); PU2756.
  - k ∈ {5, 10, 25} positives.
- **F / G.**
  - F: few-shot fine-tuning, transfer from the related finding, synthetic augmentation, Opus pseudo-labels.
  - G: F plus a hand-built landmark-relation circuit or an SAE-feature classifier.
- **Metrics.** AUROC; sensitivity at fixed specificity, on a large sealed test.
- **Helps / doesn't.**
  - Helps: G > F by ≥ 0.02 at k ≤ 10, with the knowledge circuit's ablation removing the gain.
  - Doesn't help: as in the pilot, LLM pseudo-labelling (D-ft) dominates.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** **Both arms get the same knowledge source** (rule text, landmark annotations). Pool across sites to get enough positives; MFXR is single-site.

#### S23. Zero-image-label concept classifiers from text or knowledge (H1, R0)

- **Problem.** A new finding has no labels yet (a new device, an emerging disease).
- **WSP hypothesis.** Build the classifier from SAE features plus text descriptions, or by projecting a VLM text embedding into the image model, with no label gradient.
- **Instantiations.**
  - Simulated emergence by holding a class out of the start model:
    - **CancerVerse (D12):** hold out one cancer type;
    - **MFXR (D01)** at k = 0;
    - **VinDr-Ground-VQA (D40):** hold out one finding (B2);
    - Tier C BDCXR-3257: viral pneumonia.
  - MetaStructAtlas (D39) when released.
- **F / G.**
  - F: zero-shot VLM prompting, report-NLP weak labels, Opus pseudo-labels.
  - G: F plus feature-assembled classifiers.
- **Metrics.** AUROC at k = 0, then the learning curve (k = 5, 25).
- **Helps / doesn't.**
  - Helps: G at k = 0 ≥ F at k = 5.
  - Doesn't help: Opus pseudo-labels dominate (likely, given the pilot).
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** F has report text and Opus image reading, which is a strong baseline.

#### S51. Weak or noisy labels from report NLP or an LLM labeller (H1)

- **Problem.** Training labels extracted from reports contain systematic errors.
- **WSP hypothesis.** Edits along interpretable *error directions* (where report labels disagree with images) beat noise-robust training.
- **Instantiations.**
  1. **RSNA Knee (D44):** 58 gold studies + 4,349 report-only studies (12 languages). Reports → LLM labels → train. **This directly reuses the planned Phase 2 data.**
  2. **XQA-Chest (D03):** *separate image-derived and report-derived expert labels* on the same 650 studies. A unique measurement of label-reference disagreement, underpowered.
  3. **OpenBrain (D27):** QC-tiered generated parcellations vs sealed manual labels.
  4. MAMA-MIAAI (D26): auto vs manual breast masks.
  5. CheXmask-U (D04), MIMIC-CXR-DB (D06): mechanistic only.
- **F / G.**
  - F: noise-robust losses, co-teaching, label cleaning, Opus relabelling.
  - G: F plus edits along probe-identified label-noise directions.
- **Metrics.** Gold-label AUROC/Dice. Guardrails: calibration, churn.
- **Helps / doesn't.**
  - Helps: G > the best noise-robust F by ≥ 0.02 at the same gold budget.
  - Doesn't help: Opus relabelling of reports removes the noise.
- **24 GB.** Yes (2.5D knee; patch 3D brain).
- **Ready.** RA (D44, Kaggle; plan Phase 2); RA (D03); RN (D27).
- **Confounds.** The plan's denylist for RSNA (published LLM labels, NTejas report labels, winner weights) applies.

---

### Theme 6. Continual learning: adding capability without forgetting

#### S24. Adding a new finding / class to a deployed model (H2)

- **Problem.** A product team wants a new output without degrading the cleared outputs.
- **WSP hypothesis.** Add an output unit wired to existing features (SAE/probe directions) with rank-1 edits, so old heads are untouched by construction. F must fight forgetting.
- **Instantiations.**
  1. **CancerVerse (D12):** a locked segmenter trained on some cancer types; add a new type with k ∈ {1, 5, 20} patients.
  2. **ImageCAS-X (D15, B1):** add coronary-segment labels to a general CT model (TotalSegmentator, MedSAM2, nnFoundation).
  3. **TopBrain TA36 (D24, B1):** add the 2 new infraclinoid classes to a pre-cutoff TopCoW/TopBrain or MedSAM2 checkpoint. *Not* the TA36 docker.
  4. CXR: a new localization/VQA capability via MIMIC-Ext-CXR-QBA (D05) / ILS (C02), training only.
  5. Naija-CXR (D02): new findings if its schema allows.
- **F / G.**
  - F: frozen-backbone new head, LoRA, LwF, replay; plus a **no-replay** variant (old data expired).
  - G: F plus feature-to-logit circuits and rank-1 edits.
- **Metrics.** New-class AUROC/Dice. Co-primary: max old-class drop and **old-class churn**.
- **Helps / doesn't.**
  - Helps: G's new-class score ≥ F's, while old-class churn ≈ 0 in the no-replay variant.
  - Doesn't help: a frozen-backbone new head gives the same zero churn (this is likely; the frozen head is the realistic strong F).
- **24 GB.** Yes (patches / crops).
- **Ready.** RN (D12, D24); RA (D15 images via Kaggle).
- **Confounds.**
  - The held-out structure must not be present as implicit background.
  - D15/D24 are label-novel, but their images are old (B1 audit).

#### S25. Adding a new structure to a segmentation model (H2)

- **Problem.** A TotalSegmentator-style model needs a new structure, or must split a parent class, with few labels.
- **WSP hypothesis.** Decoder-unit rewiring carves a sub-class out of a parent.
- **Instantiations.**
  - **TopBrain TA36 (D24)**: the 2 new classes.
  - **ImageCAS-X (D15)**: 18 segments carved from the lumen.
  - **Spinal-MM trabecular (D18)**: trabecular compartment carved from the vertebra.
  - **MAMA-MIAAI (D26)**: whole breast.
  - CancerVerse (D12): tumors as new classes on organ segmenters.
  - HoloCT-4B as a post-cutoff 3D start (S56).
  - OpticNerveSeg (D29) if released.
  - Tier C: TotalSegmentator liver_lesions (C11), lung tumor CT (C10).
- **F / G.**
  - F: new decoder head / LoRA / fine-tuning.
  - G: F plus parent-class decoder rewiring.
- **Metrics.** New-structure Dice/HD95 at k ∈ {1, 5, 20}. Guardrail: old-structure Dice change.
- **Helps / doesn't.**
  - Helps: G at k = 1 ≥ F at k = 5, with zero old-class drop.
  - Doesn't help: a new head on a frozen decoder matches.
- **24 GB.** Yes (patches).
- **Ready.** RN.
- **Confounds.** Retrain the start with the new structure merged into background, or excluded.

#### S26. Sequential site onboarding (continual domain adaptation) (H2, H4)

- **Problem.** A vendor rolls out site by site. Earlier sites must not regress.
- **WSP hypothesis.** Modular, switchable per-site edits (site-keyed norm statistics, small "site patches") beat sequential fine-tuning, which accumulates forgetting.
- **Instantiations.**
  - **MOPG-7 (D07):** 4 clinics.
  - **FUSEP (D30):** 3 hospitals.
  - **COBRA2026 (D13):** 6 centers.
  - **TopAneu (D23):** centers 1 → 2 → 4.
  - CancerVerse hospitals.
  - Tier C: ISLES/ATLAS (C37) if confirmed.
  - Site order fixed within a replicate and randomized across replicates.
- **F / G.**
  - F: sequential fine-tuning, replay, EWC.
  - G: F plus per-site switchable edits.
- **Metrics.** Average performance over seen sites after the final step (backward transfer); forward transfer to the next site.
- **Helps / doesn't.**
  - Helps: G's backward transfer ≥ F + 0.02 at equal forward transfer.
  - Doesn't help: per-site LoRA adapters (also switchable, also F) match.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** MOPG-7 site sizes are very unequal (1,433 / 533 / 114 / 15). Clinic 4 (15 images) is test-only.

---

### Theme 7. Unlearning and capability removal

#### S27. Site / cohort unlearning (consent withdrawal, DUA expiry) (H6)

- **Problem.** A partner site's contribution must be removed.
- **WSP hypothesis.** Site-specific knowledge sits in identifiable units/directions. Ablating them approximates "retrain without site X".
- **Instantiations.** Small enough to retrain a gold standard:
  - **FUSEP (D30)**: 3 hospitals;
  - **MOPG-7 (D07)**: 4 clinics;
  - **COBRA2026 (D13)**: 6 centers, reconstruction;
  - CancerVerse (D12): hospital subsets; retraining is costly.
- **F / G.**
  - F: NegGrad+, fine-tune-on-retain, SCRUB, SalUn.
  - G: F plus targeted ablations.
- **Metrics.** Distance to the retrain distribution (several seeds) on:
  - membership-inference advantage on X;
  - X-site performance;
  - retained performance.
- **Helps / doesn't.**
  - Helps: G is closer to the retrain gold standard than F at ≤ 10% of retrain compute.
  - Doesn't help: G over-forgets (worse than the retrain on X-like data) or under-forgets.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** The reference is a retrain, not zero performance. Hospital is confounded with device in FUSEP.

#### S28. Capability removal: demographic-attribute inference from a released embedding (H6) — deprioritized

*Framed as capability removal, not shortcut removal. Deprioritized given the investigator's preference.*

- **Problem.** A released embedding must not expose age, sex or race, while keeping diagnostic utility.
- **WSP hypothesis.** LEACE/INLP-style erasure baked into weights guarantees removal against linear probes.
- **Instantiations.**
  - **CancerVerse (D12):** linked demographics.
  - **Naija-CXR (D02):** demographics "where available".
  - BoneLoss (D09): age/sex, restricted.
  - Tier C: TAIX-Ray age/sex.
  - B-syn: CompDiff (D11) conditioning as a probe set, never a test.
- **F / G.**
  - F: adversarial training / gradient reversal.
  - G: F plus baked-in erasure.
- **Metrics.** Attribute-probe AUROC (linear, MLP and a small fine-tuning attack) vs diagnostic AUROC, as a Pareto frontier.
- **Helps / doesn't.**
  - Helps: G dominates the frontier.
  - Doesn't help: nonlinear attackers recover the attribute after G's edit.
- **24 GB.** Yes.
- **Ready.** RN (D12).
- **Confounds.** The attacker is blind to arm, with a fixed budget.

#### S29. Memorization / PHI removal in report generators (H6) — null-leaning

- **Problem.** A generator memorized PHI strings that must be removed.
- **WSP hypothesis.** MEMIT-style localization and neuron ablation. LM unlearning via editing is known to be leaky, hence null-leaning.
- **Instantiations.**
  - **Synthetic canaries** inserted at controlled frequencies while fine-tuning a small report VLM (LLaVA-Med, a MAIRA-like model, MedGemma-4B).
  - Base report corpus:
    - Tier D MIMIC (contamination is irrelevant: canaries are synthetic); or
    - Tier A Naija-CXR reports / XQA-Chest reports, if available.
- **F / G.**
  - F: fine-tune-to-forget, DPO, output filters.
  - G: localization + ablation / rank-1 edits.
- **Metrics.** Canary extraction rate (greedy, sampled, prompt attacks). Guardrails: RadGraph-F1/GREEN; non-requested canaries remain (specificity).
- **Helps / doesn't.**
  - Helps: lower extraction at equal factuality.
  - Doesn't help: extraction under prompt attacks persists.
- **24 GB.** Yes (≤ 7B QLoRA).
- **Ready.** RN (synthetic).
- **Confounds.** Never use real PHI.

---

### Theme 8. Subgroup, population, pediatric and geographic transfer

#### S30. Adult → pediatric transfer (H1, H2)

- **Problem.** Models are trained on adults. Pediatric anatomy causes failures, and pediatric data are scarce.
- **WSP hypothesis.** Explicitly model pediatric structures (physes, thymus, size priors) with edits. Knowledge injection under scarcity.
- **Instantiations.**
  1. **TotalSegmentator CT v3 (D16):** adult v2-trained model → **291 new pediatric CTs**, k ∈ {0, 5, 10, 25}, with unlabeled pediatric targets.
  2. **TotalSegmentator MRI v3 (D25):** **249 new pediatric MRIs**.
  3. **MFXR (D01):** adult MURA-trained fracture model → pediatric forearm (the plan's arm H uses MURA as a source).
  - Start options: TotalSegmentator v2 weights, nnFoundation-CNN (post-cutoff), MedSAM2.
  - Tier C: BDCXR-3257 (pediatric CXR, Bangladesh); FaceBase pediatric OPG (lead). LISA (C38) unverified.
- **F / G.**
  - F: scale/intensity augmentation, LoRA, BN adaptation.
  - G: F plus edits to age/size-responsive directions found by probes.
- **Metrics.** Pediatric per-structure Dice/HD95 (CT/MRI) or AUROC (MFXR). **Worst-age-bin** performance. Guardrails: adult retention, churn.
- **Helps / doesn't.**
  - Helps: G ≥ F + 0.02 Dice at k ≤ 10, with adult churn ≤ F's.
  - Doesn't help: scale augmentation closes the gap.
- **24 GB.** Yes (3D patches).
- **Ready.** **RN** (licence check D16; D25 CC BY 4.0).
- **Confounds.**
  - Isolate the v3 additions by ID diff.
  - Pediatric scans may come from different scanners (an age × scanner confound).
  - Age-stratified tests.

#### S31. Acquisition-subgroup gaps: portable AP vs PA, supine vs erect, device class (H2)

*Reframed* as worst-acquisition-group performance.

- **Problem.** ICU portable films and some device classes perform worse.
- **WSP hypothesis.** A correction conditioned on a view-probe direction raises the worst group without moving others.
- **Instantiations.**
  - **XQA-Chest (D03):** AP/PA, small.
  - **Naija-CXR (D02):** if view metadata exist.
  - CancerVerse (D12): contrast phase / kernel as acquisition groups.
  - **Best data is Tier C:** TAIX-Ray (C01, all-AP bedside, 18 units). Tier D: MIMIC/CheXpert ViewPosition.
- **F / G.**
  - F: GroupDRO, reweighting, subgroup fine-tuning.
  - G: F plus probe-conditioned edits.
- **Metrics.** Worst-subgroup AUROC. Guardrails: other subgroups, overall.
- **Helps / doesn't.**
  - Helps: worst-group gain ≥ 0.02 over GroupDRO, with no other group losing > 0.005.
  - Doesn't help: GroupDRO matches.
- **24 GB.** Yes.
- **Ready.** RA (D03); RV (D02); RN (C01).
- **Confounds.** Prevalence differs by view, so report per finding. The same subgroup metadata go to both arms.

#### S52. Geographic, low-resource-setting and pediatric ↔ adult transfer (H1)

- **Problem.** A model built in a high-income country is deployed elsewhere, with different prevalence, equipment and demographics.
- **WSP hypothesis.** As S1, plus prevalence/equipment directions estimated from unlabeled local data.
- **Instantiations.**
  - **Naija-CXR (D02):** US/European-trained CXR → Nigeria. The only Tier A African set found.
  - **MOPG-7 / DentalOPG-1550 (D07/D08):** Bangladesh dental (no high-income-country dental source in the inputs; DINOv3 start).
  - **FUSEP (D30):** three Chinese provinces.
  - **CancerVerse (D12):** Switzerland ↔ Turkey.
  - **MFXR (D01):** Chinese pediatric.
  - **No post-cutoff LMIC pediatric dataset exists.** Tier C BDCXR-3257 (Bangladesh pediatric CXR) is the best fallback. TREAT-MMTB (C39), LISA (C38) and CAPTURE are unverified or protocol-only.
- **F / G.** As S1, plus prevalence estimation (EM/BBSE) in both arms.
- **Metrics.** Target AUROC by finding; calibration under local prevalence; worst-subgroup.
- **Helps / doesn't.** As S1.
- **24 GB.** Yes.
- **Ready.** RV (D02); RN (D07/D30).
- **Confounds.** Disease prevalence vs acquisition: separate them with S13-style recalibration controls.

---

### Theme 9. Compression for edge deployment

#### S32. Interpretability-guided pruning and compression, with robustness after compression (H2, H6, H7)

- **Problem.** Portable X-ray, handheld US and CPU deployment need small models. Pruning hurts minority sites and rare classes disproportionately.
- **WSP hypothesis.** Knowing which heads and neurons serve OOD sites and rare findings allows selective pruning.
- **Instantiations.**
  - **FUSEP (D30):** handheld-US-like detector at matched latency; external hospital as the robustness test.
  - **MOPG-7 (D07):** held-out clinic.
  - **TotalSegmentator MRI v3 (D25)**, **OpenBrain (D27)**: worst-source Dice.
  - ImageCAS-X (D15): topology after pruning.
  - CheXmask-U (D04): quality/uncertainty signals (mechanistic).
- **F / G.**
  - F: structured magnitude pruning, distillation, quantization.
  - G: F plus interpretability-guided pruning, head merging, circuit restoration.
- **Metrics.** **External-site** and **rare-class** performance at matched latency on the same hardware; in-distribution is secondary.
- **Helps / doesn't.**
  - Helps: G retains ≥ 0.02 more external/rare performance at 75% FLOP reduction.
  - Doesn't help: distillation matches.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** Matched latency; equal distillation data.

---

### Theme 10. Segmentation and detection specifics

#### S33. Annotation-protocol (label-convention) shift in segmentation (H5, H2)

- **Problem.** Sites define structures differently. A model must match a new site's convention.
- **WSP hypothesis.** Convention differences are systematic and local (e.g. "include Y in X"). A decoder edit that adds a sub-structure's logit to the parent class implements them with ~0 labels.
- **Instantiations.** Several real post-cutoff convention changes:
  1. **TotalSegmentator v3 refined labels vs v2 labels (D16/D25):** a real label-refinement shift on the same images. The start model was trained on v2.
  2. **ImageCAS-X (D15):** re-annotated lumen vs old ImageCAS labels.
  3. **TopBrain TA36 vs 40/42-class maps (D24).**
  4. **MAMA-MIAAI (D26):** manual vs automatic breast masks.
  5. **CFB-GBM v2 (D28):** GTV / RANO conventions.
  6. Spinal-MM (D18): trabecular vs vertebral body.
  - Tier C: AMPLIFAI (C08) LI-RADS feature masks.
  - Also simulated deterministic relabelling rules.
- **F / G.**
  - F: fine-tune on k ∈ {1, 3} examples.
  - G: decoder logit composition edits, switchable.
- **Metrics.** Dice under the new convention, while the old convention remains available (switchable).
- **Helps / doesn't.**
  - Helps: G at k = 1 ≥ F at k = 3, with the old convention intact.
  - Doesn't help: F with a convention-specific head matches.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.**
  - Two variants: the sub-structure already exists in the model, or it does not.
  - B1: denylist the old labels.

#### S34. Detection under site shift: FROC with false-positive-family suppression (Null-leaning, H2)

- **Problem.** Lesion detectors produce site-specific false-positive families when moved.
- **WSP hypothesis / null.** Score-head edits suppressing an FP pattern vs hard-negative mining. Expected to be close.
- **Instantiations.**
  - **TopAneu (D23):** aneurysm FROC across centers.
  - **CancerVerse (D12):** lesion sensitivity at 0.25/0.5 FP per scan across hospitals.
  - **MOPG-7 / DentalOPG / FUSEP (D07/D08/D30):** mAP.
  - **LUCQUE (D19):** model-to-data FROC, A-p.
  - Tier C: LIDC-annot-NLST501 (C13). Tier B2 processed nodule patches (D20) are not recommended.
- **F / G.**
  - F: hard-negative mining.
  - G: concept-suppression edits from the same FP examples.
- **Metrics.** CPM / FROC sensitivity at 1 and 4 FP/scan on target.
- **Helps / doesn't.** Expected null.
- **24 GB.** Yes (crops).
- **Ready.** RN.
- **Confounds.** The same FP examples go to both arms.

#### S56. 3D foundation-model segmentation extended to a new organ, lesion or modality (H1, H2)

- **Problem.** A recent 3D FM must be extended to a new target.
- **WSP hypothesis.** Probe/SAE-localized edits to the implicated blocks, plus an edited readout, extend capability while immutable old heads preserve validated outputs.
- **Instantiations.**
  - **HoloCT-4B (post-cutoff, MIT) → CancerVerse (D12)** new lesion category, or **TAIR (D37)** vessels when labelled.
  - **nnFoundation-CNN (post-cutoff) → TotalSegmentator CT/MRI v3 additions (D16/D25)** or **TopAneu (D23)**.
  - VISTA3D / MedSAM2 → **ImageCAS-X (D15)**, **TopBrain TA36 (D24)**, **Spinal-MM (D18)**.
  - k ∈ {5, 10, 25}.
- **F / G.**
  - F: few-shot LoRA / head fine-tuning with replay.
  - G: F plus restricted edits and an edited readout.
- **Metrics.** New-class Dice/HD95, detection F1. Guardrails: old-class Dice, churn, changed-parameter count.
- **Helps / doesn't.**
  - Helps: G ≥ F with ≤ 50% churn.
  - Doesn't help: LoRA with replay matches.
- **24 GB.** HoloCT-4B PEFT plausible but unverified; 8B tight. nnFoundation-CNN patches fit; its 674M ViT needs LoRA.
- **Ready.** RN; **profile VRAM first**.
- **Confounds.** HoloCT and nnFoundation pretraining overlaps many public sets (audit). NV-Reason-CT trained on CancerVerse.

---

### Theme 11. Reports, VLMs and radiology text

#### S35. Report-generator cross-site style and content adaptation (H2)

- **Problem.** A MIMIC-trained generator writes in Boston style with Boston priors. A new site wants its own templates and priors with few examples.
- **WSP hypothesis.** Style sits in identifiable directions. A baked steering vector shifts style while preserving clinical content.
- **Instantiations.**
  - **XQA-Chest (D03):** 650 CUH image–report pairs, A-r, small.
  - **Naija-CXR (D02):** if reports are paired.
  - **RSNA Knee (D44):** knee MRI reports in 12 languages (MRI, not CXR).
  - Start: MAIRA-2 / CheXagent / MedGemma-4B (trained on D data).
  - Activation-steering baseline: the AACL 2026 SAE features.
- **F / G.**
  - F: LoRA on k ∈ {20, 100, 500} pairs, DPO.
  - G: F plus baked style directions.
- **Metrics.** Factuality (GREEN, RadGraph-F1, CheXbert-F1) plus style match.
- **Helps / doesn't.**
  - Helps: equal style match with higher factual retention.
  - Doesn't help: LoRA matches both.
- **24 GB.** 7B QLoRA, frozen vision tower.
- **Ready.** RA / RV.
- **Confounds.** Same decoding and metric implementations; radiologist subsample. Small target sets.

#### S36. Hallucinated prior-comparison removal in report generation (H6, H2)

- **Problem.** Generators hallucinate "unchanged from prior" when no prior is given.
- **WSP hypothesis.** A coherent "comparison" concept can be projected out.
- **Instantiations.**
  - MIMIC-trained MAIRA-2/CheXagent (D-trained) evaluated on Tier A single studies without priors: **Naija-CXR (D02)**, **XQA-Chest (D03)**.
  - The behavior is *generated*, so dataset contamination matters little. Contamination of eval images only affects factuality guardrails.
- **F / G.**
  - F: report rewriting + fine-tuning, DPO, constrained decoding.
  - G: F plus direction ablation.
- **Metrics.** Hallucinated-prior phrase rate (pattern + LLM judge). Guardrails: GREEN/RadGraph; correct prior use when priors are given.
- **Helps / doesn't.**
  - Helps: G cuts the rate ≥ 50% more than DPO at equal factuality.
  - Doesn't help: constrained decoding wins.
- **24 GB.** QLoRA.
- **Ready.** RN with D-trained models + Tier A images (RV / RA).
- **Confounds.** Fixed compute; F's rewriting pipeline is permitted.

#### S37. Laterality and negation error correction (H2)

- **Problem.** Left/right swaps and negation errors are high-severity.
- **WSP hypothesis.** Laterality is a clean direction tied to image geometry, so edits can enforce flip-consistency.
- **Instantiations.**
  - **VinDr-Ground-VQA (D40):** boxes give laterality truth; flip pairs.
  - **radiology-conflict (D41):** laterality-conflict fields (100 cases, pilot).
  - Start: Qwen2.5-VL-7B / MedGemma-4B / CheXagent.
- **F / G.**
  - F: flip augmentation + LoRA.
  - G: F plus laterality-direction edits.
- **Metrics.** Laterality accuracy, flip-consistency. Guardrail: overall factuality.
- **Helps / doesn't.** Helps: flip-consistency gain at equal factuality.
- **24 GB.** QLoRA.
- **Ready.** RA (D40 credentials); RN (D41, rights unclear).
- **Confounds.** "L/R" text markers on films. D40 is B2.

#### S38. Cross-institution report-label extractor (H1, H7)

- **Problem.** Report labelers degrade at new institutions (templates, hedging, language).
- **WSP hypothesis.** Rank-1 edits map site-specific hedging to the "uncertain" representation. Text models are cheap to iterate on.
- **Instantiations.**
  - **HUAC Portuguese labeled reports (D42):** conditional on the codebook.
  - **RSNA Knee reports (D44):** gold labels for 58 studies.
  - **XQA-Chest (D03):** report-derived expert labels.
  - Tier C: FMCEB-CXR (Nigerian reports, NLP labels).
  - Start: CheXbert or a small LLM trained on MIMIC labels.
  - The SPR 2026 mammography report classification (Kaggle) is an unverified lead.
- **F / G.**
  - F: LoRA on k ∈ {20, 100}.
  - G: F plus hedging/negation rank-1 edits.
- **Metrics.** Macro-F1 including the uncertain class.
- **Helps / doesn't.**
  - Helps: G at k = 20 ≥ F at k = 100.
  - Doesn't help: Opus zero-shot labelling beats both (likely).
- **24 GB.** Yes.
- **Ready.** RV (D42); RA (D44, D03).
- **Confounds.** Adjudicated targets; fixed schema.

#### S47. Generalist medical VLM → specialist task (H1, H2)

- **Problem.** Adapt a MedGemma-class VLM to a narrow radiology task.
- **WSP hypothesis.** Edits along the model's own concept directions beat LoRA at low k, with better locality.
- **Instantiations.**
  1. **MedGemma-4B / Qwen2.5-VL-7B → VinDr-Ground-VQA (D40)**: grounded CXR VQA at k ∈ {5, 25, 100} images (B2).
  2. **RSNA Knee (D44)** with MedGemma 1.5 (volumes): Tier A.
  3. **HoloCT-4B or NV-Reason-CT** (post-cutoff) → CancerVerse lesion QA (not NV-Reason-CT, which trained on it).
  4. Tier C: RadM-Bench (C32), SynRad-IR-200 (C33).
- **F / G.**
  - F: QLoRA/SFT, prompt tuning.
  - G: F plus probe-derived projector/attention edits.
- **Metrics.** Balanced exact match, answer F1, grounding (box IoU, area-matched occlusion response), calibration. Locality per M³Bench.
- **Helps / doesn't.**
  - Helps: G ≥ F + 0.02 at k ≤ 25 with better locality.
  - Doesn't help: QLoRA matches.
- **24 GB.** 4B QLoRA yes; 7B 4-bit batch 1.
- **Ready.** RA.
- **Confounds.** D40 is not confirmatory (B2). Its ROI-check field used an external API.

#### S48. Multilingual / cross-country report models (H1)

- **Problem.** An English-trained report labeller or summariser is deployed on another language or health system.
- **WSP hypothesis.** Cross-lingual concept directions allow edits that transfer label semantics.
- **Instantiations.**
  1. **RSNA Knee (D44): 12 report languages.** Hold out a language; the strongest Tier A option.
  2. **HUAC (D42):** Portuguese, conditional.
  3. **radiology-conflict (D41):** 22 languages on 100 images, pilot.
  - Tier C: RadM-Bench EN → ZH; FMCEB-CXR.
- **F / G.**
  - F: multilingual LoRA, translation augmentation.
  - G: F plus concept-direction edits.
- **Metrics.** Macro-F1/AUROC on the held-out language; worst-language score; English retention; cross-translation consistency.
- **Helps / doesn't.**
  - Helps: G ≥ F + 0.02 on the held-out language with no English loss.
  - Doesn't help: machine translation to English + the source model wins.
- **24 GB.** Yes.
- **Ready.** RA (D44); RV (D42).
- **Confounds.** Group splits by case across languages. Language may be confounded with site in RSNA Knee.

---

### Theme 12. Merging, composition and restricted-access adaptation

#### S39. Multi-site model merging without data sharing (H4)

- **Problem.** Sites fine-tune a shared FM locally and cannot pool data. One model is wanted that works everywhere.
- **WSP hypothesis.** Interpretability-guided merging (neuron alignment, per-head source choice, conflict resolution) beats task arithmetic / TIES / Fisher.
- **Instantiations.**
  - **FUSEP (D30):** 3 hospital fine-tunes.
  - **MOPG-7 (D07):** 4 clinics.
  - **COBRA2026 (D13):** 6 centers.
  - **CancerVerse (D12):** Swiss vs Turkish hospitals.
  - OpenBrain (D27): source groups.
  - Multi-task variant: a CXR model + a dental model from the same DINOv3.
  - Baselines: Med-LEGO, TIES/DARE.
- **F / G.**
  - F: distillation of the ensemble on a small public calibration set.
  - G: F plus interpretability-guided merging.
  - **Preregister** whether plain task arithmetic is F, G or mechanical (P3).
- **Metrics.** Mean and worst performance over contributing sites + an unseen site.
- **Helps / doesn't.**
  - Helps: G beats TIES and distillation on the worst site by ≥ 0.02.
  - Doesn't help: TIES/Med-LEGO matches. The pilot's soup + task-vector amplification gave +0.018, so a mechanical merge is a strong baseline.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** The boundary definition (P3).

#### S53. Compute- or data-access-restricted adaptation (activations / statistics only) (H1, H7)

- **Problem.** The deployment site can share only activations or aggregate statistics, or run approved code on-premise.
- **WSP hypothesis.** Closed-form, statistics-based edits (computed from shared moments) beat federated or limited fine-tuning.
- **Instantiations.**
  - **LUCQUE (D19):** a natural fit. PARADIM *model-to-data*: images never leave, and both arms submit programs. A-p; runtime rules unknown.
  - Simulated on **CancerVerse (D12)** or **Naija-CXR (D02)**: the agent receives only feature moments / class-conditional statistics.
  - BrainFedFM as a federated-pretrained start.
- **F / G.**
  - F: federated fine-tuning / a submitted adaptation script.
  - G: closed-form statistic edits.
- **Metrics.** Target performance at matched information disclosure.
- **Helps / doesn't.** Helps: G ≥ F at equal disclosure and ≤ 10% of the compute.
- **24 GB.** Depends on the platform.
- **Ready.** RV (D19 terms, dates); RN (simulation).
- **Confounds.** Identical disclosure for both arms.

---

### Theme 13. Acquisition artifacts and new hardware

#### S40. Low dose, noise, motion, contrast phase and exposure artifacts (H1, H5)

- **Problem.** Models trained on clean acquisitions degrade on low-dose CT, motion, a different contrast phase or poor exposure.
- **WSP hypothesis.** Noise/motion sensitivity lives in specific high-frequency channels. Phase differences can be handled with intensity-conditional edits.
- **Instantiations.**
  - **COBRA2026 (D13):** CBCT artifacts with paired planning CT.
  - **CBCT-IQ (D14):** controlled kV / pulse / recon degradations with expert IQA, phantom.
  - **XQA-Chest IQA (D03):** controlled contrast/sharpness degradations of real CXR with expert usability ratings.
  - **Spinal-MM (D18):** low-dose dual-energy.
  - Longitudinal liver CT (D17): dose metadata.
  - EPFL RF (D32): acquisition parameters.
  - Tier C: MRIxFields. Tier D: Mayo LDCT, MR-ART (paired).
- **F / G.**
  - F: artifact augmentation (strong competitor), fine-tuning.
  - G: F plus channel edits.
- **Metrics.** Performance under the artifact condition; paired consistency; a severity curve, not a single point.
- **Helps / doesn't.**
  - Helps: G flattens the severity curve beyond augmentation.
  - Doesn't help: augmentation matches.
- **24 GB.** Yes (2D / patch).
- **Ready.** RN (D13, D14); RA (D03).
- **Confounds.** Prefer paired real data; phantom results do not transfer automatically to patients.

#### S49. New hardware or imaging technology at a site (H1, H5)

- **Problem.** New CBCT systems, low-field MRI, new detectors or AI reconstruction arrive with few paired examples.
- **WSP hypothesis.** Probe-guided stem/normalization edits from a few unpaired examples, plus known-physics circuits.
- **Instantiations.**
  - **COBRA2026 (D13):** Elekta vs Varian, a new CBCT vendor. The best Tier A option.
  - **CBCT-IQ (D14):** C-arm setting changes.
  - **Open-H-RF / EPFL RF (D31/D32):** new beamforming pipelines.
  - **TAIR (D37):** fluoroscopy, pending.
  - Spinal-MM (D18): dual energy.
  - **No post-cutoff photon-counting CT or low-field MRI set was found.** Tier C: MRIxFields 0.1T/5T/7T, DoseRAD 0.35T MR-Linac; LISA 0.064T unverified.
- **F / G.**
  - F: fine-tune / LoRA / physics-aware reconstruction.
  - G: F plus stem/kernel edits.
- **Metrics.** HU-MAE, SSIM; downstream Dice on a curated subset.
- **Helps / doesn't.** As S5.
- **24 GB.** Patches.
- **Ready.** RN (D13, D14).
- **Confounds.** COBRA's planning-CT reference is deformed.

---

### Theme 14. OOD detection and selective prediction

#### S41. Built-in OOD gatekeeper and selective prediction under shift (H1)

- **Problem.** Deployed models receive wrong body parts, pediatric patients or unfamiliar sites. They should abstain.
- **WSP hypothesis.** Internal probe/SAE "unfamiliarity" features can be wired into an abstention head without OOD training data.
- **Instantiations.**
  - A CXR model with:
    - near-OOD = **Naija-CXR (D02)** (new country) and pediatric CXR;
    - far-OOD = **MFXR (D01)**, **DentalOPG (D08)**, CT slices.
  - A TotalSegmentator adult model vs **v3 pediatric (D16)**.
  - Quality-based abstention: **XQA-IQA (D03)** non-diagnostic images; CheXmask-U RCA (D04); OpenBrain QC (D27).
- **F / G.**
  - F: energy / MSP / Mahalanobis, outlier exposure.
  - G: F plus an edited-in abstention circuit.
- **Metrics.** OOD AUROC (near/far separately); AURC; selective risk at 90% coverage on the shifted site.
- **Helps / doesn't.**
  - Helps: G's near-OOD AUROC ≥ Mahalanobis + 0.03.
  - Doesn't help: Mahalanobis matches.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** OOD classes unseen by both arms; equal outlier exposure.

---

### Theme 15. Other practitioner situations

#### S42. Supply-chain backdoor removal in downloaded models (H6)

*Framed as security, not shortcut removal.*

- **Problem.** A downloaded checkpoint may carry a trigger.
- **WSP hypothesis.** Trigger circuits are localized, so detection plus surgical ablation works.
- **Instantiations.**
  - We plant backdoors of varying stealth in models trained on **Naija-CXR (D02)**, **FUSEP (D30)** or CancerVerse slices.
  - Some models contain no backdoor (false-alarm control).
- **F / G.**
  - F: fine-pruning, retraining on clean data.
  - G: F plus Neural-Cleanse-style localization and ablation.
- **Metrics.** Attack success rate after the fix vs clean performance; detection rate; false-alarm rate.
- **Helps / doesn't.**
  - Helps: lower attack success at equal clean performance.
  - Doesn't help: fine-pruning matches.
- **24 GB.** Yes.
- **Ready.** RN.
- **Confounds.** Several trigger types; arm-blind evaluation.

#### S43. Label-taxonomy harmonization across datasets (H1, H5)

- **Problem.** NIH, CheXpert, PadChest and VinDr define findings differently. Deploying across taxonomies requires mapping.
- **WSP hypothesis.** Rewire output heads as linear combinations of existing concept units with few labels.
- **Instantiations.**
  - CheXpert-taxonomy model → **Naija-CXR (D02)** schema; **XQA-Chest (D03)** 14 categories; **VinDr-Ground-VQA (D40)** 22 findings; MIMIC-QBA (D05) 237 entities.
  - **RSNA Knee (D44):** 12 labels vs a source knee taxonomy.
  - Segmentation analogue: TopBrain 36 vs 40/42 classes (D24).
- **F / G.**
  - F: new head on k ∈ {0, 20, 100}.
  - G: F plus head rewiring.
- **Metrics.** Macro-AUROC under the target taxonomy. Separate concept mismatch from image shift by evaluating on source images relabelled to the target taxonomy, where possible.
- **Helps / doesn't.** Helps: G at k = 0–20 ≥ F at k = 100.
- **24 GB.** Yes.
- **Ready.** RV / RA.
- **Confounds.** Adjudicated targets.

#### S44. Adding multi-view or prior-comparison capability via circuit insertion (H4, H5)

- **Problem.** Single-image models ignore lateral views, CC+MLO pairs and priors.
- **WSP hypothesis.** A hand-wired difference or view-fusion circuit adds the capability without paired training.
- **Instantiations.**
  - **CancerVerse (D12):** prior scans (median 3 scans/299 days).
  - **Longitudinal liver CT (D17)**, A-r.
  - **RSNA Knee (D44):** multi-sequence as multi-view.
  - OMAMA HYFOWN (D34): 4-view, conditional.
  - Tier C: LUMINA CC/MLO. B2: MIMIC-CXR-DB sequences.
- **F / G.**
  - F: train a fusion module.
  - G: hand-wired circuit + edits.
- **Metrics.** Change-classification AUROC at low k.
- **Helps / doesn't.** Helps: G at k ≤ 10 ≥ F at k = 50.
- **24 GB.** Yes.
- **Ready.** RN (D12).
- **Confounds.** Identical registration for both arms.

#### S55. Longitudinal / prior-comparison change detection (H4, H5)

- **Problem.** Treatment response and interval change need paired-study reasoning.
- **WSP hypothesis.** A temporal-difference circuit inserted into a single-timepoint lesion model preserves lesion identity across scans.
- **Instantiations.**
  - **CancerVerse (D12):** prediagnosis → diagnosis intervals.
  - **Longitudinal liver CT (D17):** T0 → T1/T2; 54 patients, A-r.
  - **TopAneu center-4 (D23):** 7 patients, order not chronological.
  - CFB-GBM v2 (D28): RANO, conditional.
  - Tier C: EchoRisk (closed), TAIX-Ray.
- **F / G.**
  - F: registration + temporal fine-tuning.
  - G: F plus a difference circuit / lesion-identity edits.
- **Metrics.** Lesion Dice/recall, correspondence F1, change-class accuracy. Guardrail: single-timepoint retention.
- **Helps / doesn't.** As S44.
- **24 GB.** Yes (crops).
- **Ready.** RN (D12); RA (D17).
- **Confounds.** Patient-level splits; the small liver cohort cannot power 0.01 effects.

---

## 8. Coverage matrices

### 8.1 Setups × datasets

★ marks the recommended instantiation. Dataset IDs refer to §5. "—" means no qualifying dataset was found. "(sim)" means simulated on top of the listed data.

| Setup | Tier A / A-r / A-p / A-u | Tier B (B1, B2) | Tier C fallback | Tier D fallback | Status |
|---|---|---|---|---|---|
| S1 cross-site | ★D02, D12, D44, D07 | — | C32 | CheXpert, MIMIC, PadChest, VinDr | RV |
| S2 multi-vendor seg | D30, D13, D23, D16 (analogues) | D24 | C23 (recon) | M&Ms-1/2 | Analogue only |
| S3 prostate protocol | D25 (substitute) | — | C22 (PDF) | 6-site prostate, PI-CAI | **NR (Tier A gap)** |
| S4 mammo vendor | D34 (conditional) | D33 | ★C24, C26 | EMBED, VinDr-Mammo, CMMD | Pilot (Tier C) |
| S5 kernel / CBCT | ★D12, D13, D17, D19 | D18, D20 | C13 | LIDC, NLST, LNDb | RN |
| S6 field strength | D25, D23 | D27, D28 | ★C15 (paired) | ADNI, SRPBS | RN / C |
| S7 unseen-site DG | ★D30, D07, D23, D13, D12, D44 | D27 | C37 | — | RN |
| S8 unlabeled adaptation | ★D30, D16, D13, D02, D36 | — | — | — | RN |
| S9 temporal hotfix | ★D12, D17, D44 | D06, D28 | ★C01 | MIMIC years | RN |
| S10 defect patch | D01, D08, D23, D19 | D43, D03 | — | MURA, GRAZPEDWRI-DX | RX |
| S11 PCCP overlay | (any of S1, S9, S24, S30) | D38 | — | — | RN |
| S12 pipeline control | ★D01, D02, D12, D14 (sim) | — | C24 | — | RN |
| S13 prevalence null | ★D12, D01, D02, D03 | — | C24 | RSNA ICH / CQ500 | RN |
| S14 DINOv3 → radiograph | ★D02, D07, D08, D01 | D40 | — | CheXpert, MIMIC (source) | RV / RN |
| S15 HU-window circuit | ★D12, D16 | D15, D26 | — | RSNA ICH, CQ500 | RN |
| S16 natural → US | ★D30, D31, D32 | D33 | ★C25 | BUSI, BUS-BRA | RN |
| S17 vocab editing | D02 | ★D40, D05 | C28 | PadChest | RA |
| S18 CT → MRI | ★D25, D23 | D24 | — | AMOS, CHAOS | RN |
| S19 2D → 3D | ★D12, D44 | D38 | C29, C09 | CT-RATE | RN |
| S20 add PET / fluoro | D36 (RX), D37 (pending), D39 (unreleased) | — | C31 | autoPET, HECKTOR | **NR (Tier A gap)** |
| S21 CXR-FM → mammo / dental | ★D07, D08 (dental substitute), D34 | — | C24, C26 | CBIS-DDSM | RN |
| S22 rare + knowledge | ★D01, D08, D23, D12 | — | C03, C25 | GRAZPEDWRI-DX | RN |
| S23 zero-label concepts | ★D12, D01 | D40 | C03 | BIMCV, COVIDx | RN |
| S24 add class | ★D12, D02 | ★D24, D15, D05 | C02, C11 | — | RN |
| S25 add structure | D12 | ★D24, D15, D18, D26, D29 | C10, C11 | TotalSegmentator v2 | RN |
| S26 site onboarding | ★D07, D30, D13, D23 | — | C37 | M&Ms | RN |
| S27 site unlearning | ★D30, D07, D13, D12 | — | — | — | RN |
| S28 attribute removal | D12, D02, D09 | D11 (probe only) | C01 | MIMIC, CheXpert | RN (deprioritized) |
| S29 PHI canaries | D02, D03 (reports) | — | — | MIMIC (synthetic canaries) | RN |
| S30 adult → pediatric | ★D16, ★D25, D01 | — | C03, C07, C38 | GRAZPEDWRI-DX, VinDr-PCXR | RN |
| S31 acquisition subgroup | D03, D02, D12 | — | ★C01 | MIMIC, CheXpert views | RA / C |
| S32 compression | ★D30, D07, D25 | D27, D15, D04 | — | — | RN |
| S33 convention shift | ★D16, D25 (v2 → v3 labels) | ★D15, D24, D26, D28, D18 | C08 | — | RN |
| S34 detection FROC | D23, D12, D07, D08, D30, D19 | D20 | C13 | LUNA16, LNDb | RN |
| S35 report style | D03, D02, D44 | — | — | MIMIC, IU-Xray | RA / RV |
| S36 hallucinated priors | ★D02, D03 (evaluation images) | — | — | MIMIC (generator) | RV / RA |
| S37 laterality | — | ★D40, D41 | — | MIMIC, VinDr | RA |
| S38 report labeler | D42, D44, D03 | — | C06 | CheXpert Plus, PadChest | RV / RA |
| S39 merging | ★D30, D07, D13, D12 | D27 | — | FeTS | RN |
| S40 artifacts | ★D13, D14, D03 (IQA), D17 | D18 | C15 | Mayo LDCT, MR-ART | RN |
| S41 OOD / selective | ★D02, D01, D08, D16, D03 | D04, D27 | — | — | RN |
| S42 backdoor | D02, D30, D12 | — | — | — | RN |
| S43 taxonomy | D02, D44, D03 | D40, D05, D24 | — | NIH, PadChest | RV |
| S44 multi-view / prior | ★D12, D17, D44, D34 | D06 | C24 | MIMIC sequences | RN |
| S45 version upgrade | ★D30, D07, D02, D16, D25, D44 | — | — | — | RN |
| S46 guideline revision | D19, D12 (sim) | D28, D24 | C08, C24 | — | RV / RN (sim) |
| S47 generalist VLM | D44, D12 | ★D40 | C32, C33 | — | RA |
| S48 multilingual | ★D44, D42 | D41 | C32, C06 | — | RA |
| S49 new hardware | ★D13, D14, D31, D32, D37 | D18 | C15, C16, C38 | — | RN |
| S50 new protocol / tracer | D44, D12, D25, D36 | D26, D28 | C31, C08 | — | RA / RN |
| S51 weak labels | ★D44, D03 | D27, D26, D04, D06, D22 | — | — | RA / RN |
| S52 geographic / pediatric | ★D02, D07, D08, D30, D12, D01 | — | C03, C39, C38 | — | RV (**LMIC pediatric gap**) |
| S53 restricted access | ★D19 (model-to-data), D12 / D02 (sim) | — | — | — | RV |
| S54 operating point | D12, D01, D02 | — | C24 | — | RN |
| S55 longitudinal | ★D12, D17, D23 | D28 | C27, C01 | — | RN / RA |
| S56 3D FM extension | ★D12, D16, D25, D23, D37 | D15, D24, D18 | C10, C11 | — | RN (profile VRAM) |

**Datasets that support the most setups:**

| Dataset | Setups supported |
|---|---|
| CancerVerse (D12) | ~25 |
| Naija-CXR (D02) | ~18 |
| FUSEP (D30) | ~13 |
| RSNA Knee (D44) | ~12 |
| TotalSegmentator v3 CT/MRI (D16/D25) | ~12 each |
| MOPG-7 (D07) | ~10 |
| COBRA2026 (D13) | ~10 |
| TopAneu (D23) | ~10 |

Concentration risk: if CancerVerse's licence or Naija-CXR's schema fails, coverage drops sharply (§10).

### 8.2 Setups × hypotheses

● = primary hypothesis tested; ○ = secondary.

| Setup | H1 few labels | H2 locality | H3 audit | H4 compose | H5 known transform | H6 removal | H7 compute | Null |
|---|---|---|---|---|---|---|---|---|
| S1 | ● | ○ | | | | | | |
| S2 | ● | ● | | | | | | |
| S3 | ● | ○ | | | | | | |
| S4 | ● | | | | ● | | | |
| S5 | ○ | | | | ● | | | |
| S6 | ● | | | | ● | | | |
| S7 | ● | | | | | | | |
| S8 | ● | | | | | | | |
| S9 | | ● | | | | | ● | |
| S10 | | ● | ● | | | | | |
| S11 | | ○ | ● | | | | | |
| S12 | | | | | ● | | ○ | (positive control) |
| S13 | | | | | | | ○ | ● |
| S14 | ● | | | | | | | |
| S15 | ○ | | | | ● | | | |
| S16 | ● | | | | | | | |
| S17 | ● | ○ | | | | | | |
| S18 | ● | | | | ● | | | |
| S19 | | | | ● | ● | | | |
| S20 | | ● | | | ● | | | |
| S21 | ○ | | | | | | | ● |
| S22 | ● | | | | | | | |
| S23 | ● | | | | | | | |
| S24 | | ● | | | | | | |
| S25 | | ● | | | | | | |
| S26 | | ● | | ● | | | | |
| S27 | | | | | | ● | | |
| S28 | | | | | | ● | | |
| S29 | | | | | | ● | | ● |
| S30 | ● | ● | | | | | | |
| S31 | | ● | | | | | | |
| S32 | | ● | | | | ● | ● | |
| S33 | | ● | | | ● | | | |
| S34 | | ● | | | | | | ● |
| S35 | | ● | | | | | | |
| S36 | | ● | | | | ● | | |
| S37 | | ● | | | | | | |
| S38 | ● | | | | | | ● | |
| S39 | | | | ● | | | | |
| S40 | ● | | | | ● | | | |
| S41 | ● | | | | | | | |
| S42 | | | | | | ● | | |
| S43 | ● | | | | ● | | | |
| S44 | | | | ● | ● | | | |
| S45 | ○ | | | ● | ● | | | |
| S46 | | ● | ● | | | | | |
| S47 | ● | ● | | | | | | |
| S48 | ● | | | | | | | |
| S49 | ● | | | | ● | | | |
| S50 | | | | ● | ● | | | |
| S51 | ● | | | | | | | |
| S52 | ● | | | | | | | |
| S53 | ● | | | | | | ● | |
| S54 | | ● | ● | | | | | ○ |
| S55 | | | | ● | ● | | | |
| S56 | ● | ● | | | | | | |

**Hypothesis coverage by the recommended portfolio (§9):**

| Hypothesis | Covered by |
|---|---|
| H1 | S16/S7/S8, S1/S52/S14, S30 |
| H2 | S24/S25, S30, S9 |
| H3 | S11 overlay |
| H4 | S45, S39 |
| H5 | S12/S15 gate, S45, S33 |
| H6 | S27 (stretch) |
| H7 | Low-compute regime on S9/S45 |
| Null | S13 |

---

## 9. Recommended portfolio

### 9.1 Ranking criteria

Each setup was judged on five criteria:

1. how often practitioners face the situation;
2. whether WSP has a concrete channel *beyond labels* (pilot lesson 7);
3. data readiness under Tier A/B1;
4. statistical power and clean measurement;
5. fit with the investigator's preference for distribution shift and natural-image domain gap.

### 9.2 Ranked list: the 12 most informative and runnable setups

| Rank | Setup(s) | Instantiation | Why it ranks here | Tier / readiness | Key risk |
|---|---|---|---|---|---|
| 0 (gate) | **S12 + S15** positive controls | Pipeline inversion and resolution change on MFXR/Naija; HU-window circuit with DINOv3-B on CancerVerse slices | Proves that the edit machinery works. If G cannot win where the answer is known, nothing else is interpretable. Cheap (hours, CPU-feasible). | A · RN | None important; a win does not show practical value (P14) |
| 1 | **S16 + S7 + S8** | DINOv3-B (and USFM; SonoBase/UltraSAM3 as post-cutoff references) → **FUSEP** held-out hospital/device, R1 and k ∈ {5, 10, 25, 50} | Covers both preferred themes (natural → US domain gap and vendor/site shift) with real multi-device Tier A data and open access. Published UDA recipes exist, so F is strong. | A · RN | 4,017 images, no patient IDs → limited power; data terms |
| 2 | **S1 + S52 (+ S14)** | RAD-DINO (and DINOv3-B for S14) CheXpert/MIMIC-trained → **Naija-CXR**, R0–R2 | The most common practitioner problem; the only Tier A cross-country CXR set; the backbone's pretraining excludes the target. | A · **RV** | Counts, schema and licence unknown; may be underpowered or have an unusable label schema |
| 3 | **S30 (+ S8, S56)** | TotalSegmentator v2 / nnFoundation-CNN adult model → **TotalSegmentator CT v3 (291) and MRI v3 (249) pediatric additions** | Clean adult → pediatric shift on Tier A segmentation, open access, adequate segmentation test sizes, worst-age-bin metric, churn on adult cases. | A · RN | ID diff needed; CT licence field; age × scanner confound |
| 4 | **S24/S25 + S11 overlay** | Locked CancerVerse segmenter + a new cancer type (Tier A); secondary TopBrain TA36 new classes / ImageCAS-X segments (B1) | The strongest H2/H3 test. The no-replay variant is realistic. The PCCP diff budget makes auditability measurable. | A / B1 · RN | A frozen-backbone new head may already give zero churn (fair null); CC BY-NC-ND |
| 5 | **S45** | DINOv2-B → DINOv3-B ported on FUSEP/MOPG-7/Naija; pre-cutoff 3D encoder → nnFoundation/NeuroVFM | A frequent, under-studied operations problem. Closed-form maps are a natural WSP win (H4/H5) and cheap. A post-cutoff target removes agent prior knowledge. | A · RN | Whether a closed-form map counts as WSP (preregister, P3) |
| 6 | **S9 + S1/S7 (CT)** | nnFoundation-CNN / nnU-Net on **CancerVerse**: early years → late years, Swiss → Turkish hospitals | The largest Tier A dataset; screening-relevant FP/scan metrics; temporal drift + site shift + churn. | A · RN | Drift must be shown to exist; site IDs and kernel metadata completeness; licence |
| 7 | **S49 + S5 + S40** | Reconstruction U-Net on **COBRA2026**: Elekta → Varian (and center holdout) | New-hardware onboarding with real vendor shift and paired references. Physics-motivated edits give WSP a mechanism. | A · RN (patch subset) | Reconstruction task (not diagnostic); 750 GB; deformed reference |
| 8 | **S26 + S27 + S39 (+ S7)** | DINOv3/ConvNeXt detector on **MOPG-7** (4 clinics) ± DentalOPG-1550 | One small Tier A dataset answers four practitioner questions (onboarding, unlearning, merging, DG) with a cheap retrain gold standard. | A · RN | Very unequal clinic sizes; licence; no patient IDs |
| 9 | **S51 + S48** | Plan's RSNA Knee pipeline (2.5D ConvNeXt-T / DINOv3 / MRI-CORE): report-derived labels (4,349) vs 58 gold; held-out report language | Reuses the prepared Phase 2 data and the Kaggle **hidden test**. Weak-label correction and multilingual shift are frequent problems. | A · RA | Site/language metadata unverified; denylist from the plan; 16 vs 19 sites |
| 10 | **S47 (+ S17, S37)** | MedGemma-4B / Qwen2.5-VL-7B → **VinDr-Ground-VQA** grounded VQA | The only VLM setup with a substantial post-cutoff target; tests locality (M³Bench-style). | B2 · RA | Not confirmatory (old VinDr labels); public test labels |
| 11 | **S33** | TotalSegmentator v2 model → v3 refined-label convention (D16/D25); ImageCAS-X re-annotation | A real, crisp H5 test (convention change on the same images) at near-zero cost. | A/B1 · RN | Label refinements may be small in Dice terms |
| 12 | **S13** null control | Prevalence shift on CancerVerse / MFXR | Required calibration of claims. A G win here flags a parity bug. | A · RN | None |

### 9.3 Minimal Phase 2 core (6 setups)

If only about six can run, choose these. They cover ≥4 modalities (US, CXR, CT, MRI), both preferred themes, H1/H2/H3/H4/H5 and a null.

1. **Gate: S12 + S15** (positive controls, run first). Pass criterion: G recovers ≥ 95% of the known transform at k = 0.
2. **S16/S7/S8 on FUSEP:** shift + domain gap, ultrasound.
3. **S1/S52/S14 on Naija-CXR:** cross-country CXR + DINOv3 → RAD-DINO gap. *If Naija-CXR fails verification* (no usable labels, or n too small), substitute **S9/S1 on CancerVerse**.
4. **S30 on TotalSegmentator v3 pediatric additions:** adult → pediatric segmentation, 3D.
5. **S24/S25 + S11 on CancerVerse new cancer type** (or TopBrain TA36): locality and auditability.
6. **S45 version upgrade**, with **S13** run as an embedded null control on the same data (no extra agent sessions beyond the S13 cells).

**Budget sketch (from P8 and the pilot).**

- The pilot needed ~$17–68 of API cost per F/G session at list prices, and ~4–12 h of wall clock.
- For each of the 5 core setups: ≥3 replicates × 2 arms (F, G) × 2 regimes ≈ 12 sessions, so ≈ 60 sessions in total.
- Add G-permitted, E and M arms where preregistered.
- Mechanical arms and controls need no agent.

**Relation to `plan.md`.** The plan's Phase 2 is the RSNA Knee label-efficiency study. Its Phase 3 candidates are LIDC-annot-NLST501 and a Pillar-0 chest CT task.

- RSNA Knee fits here as rank 9 (S51/S48).
- LIDC-annot-NLST501 is **Tier C/ambiguous** by `11`, so it should not be the confirmatory Phase 3 test unless its post-cutoff deposit date is proven.
- Whether this portfolio replaces or complements the plan's phases is an investigator decision (§10).

### 9.4 Stretch list (run if resources allow, or when data mature)

| Setup | Instantiation | Prerequisite |
|---|---|---|
| S10 | Defect correction on MFXR/DentalOPG/TopAneu with X-Edit as arm M | Local error-family annotation |
| S56 | HoloCT-4B extension | VRAM profiling |
| S53 | LUCQUE model-to-data | Date and terms confirmation |
| S20 | PET add-channel on CMB V25 | Local lesion annotation, or MetaStructAtlas / TAIR label releases |
| S6, S49 | Field strength | Tier C MRIxFields (flagged secondary) |
| S4, S21 | Mammography | Tier C LUMINA pilot; OMAMA HYFOWN overlap audit |
| S36 | Hallucinated priors | MAIRA-2 on Naija/XQA images |
| S22, S23 | Rare / zero-label with knowledge channels | MFXR follow-on to the pilot |
| S31 | Acquisition subgroup | Tier C TAIX-Ray, flagged |
| S35, S29 | Report style / PHI canaries | — |
| S27 on CancerVerse | Site unlearning at scale | — |
| S42 | Backdoor security | — |
| S41 | OOD gatekeeper | — |

### 9.5 Gaps: where new data must be awaited or annotated locally

| Gap | Affected setups | Best current option | Action |
|---|---|---|---|
| **Powered, multi-site post-cutoff diagnostic CXR** | S1, S14, S31, S9 (CXR), S43 | Naija-CXR (size unknown); TAIX-Ray (Tier C, single site) | Verify Naija; consider local annotation of a new cohort; watch TREAT-MMTB / RSNA 2026–27 |
| **LMIC pediatric (any modality)** | S30, S52 | BDCXR-3257 (Tier C); LISA, TREAT-MMTB, CAPTURE (unverified) | Await LISA / TREAT public data; partner annotation |
| **Multi-vendor mammography / DBT** | S4, S21, S54 | LUMINA (C, 468 patients); DBT-2026 (DUA); OMAMA HYFOWN (overlap ?) | Overlap audit on HYFOWN; dental substitute for S21 |
| **Multi-vendor cardiac MRI; multi-site prostate MRI** | S2, S3 | None (analogues only) | Await; use FUSEP / COBRA / TopAneu analogues |
| **Paired reconstruction-kernel CT; photon-counting CT** | S5, S49 | CancerVerse kernel strata (unpaired); COBRA (CBCT) | Check CancerVerse kernel metadata |
| **Paired field-strength / low-field MRI** | S6, S49 | MRIxFields2026 (C); LISA (unverified) | Use as flagged secondary |
| **Labelled PET/CT, new tracers (FAP), image + EHR** | S20, S50 | CMB V25 (unlabeled); MetaStructAtlas (unreleased); PSMA (C) | Annotate CMB subset; await MetaStructAtlas |
| **Post-cutoff image–report corpus at scale** | S35, S36, S29, S38 | XQA-Chest 650 (A-r); Naija reports (?); RSNA Knee reports | Verify Naija reports; RSNA Knee reports for text setups |
| **Echo / longitudinal video** | S9, S55 | EchoRisk (C, closed) | Await open release |
| **Error-family and subgroup annotations** | S10, S31 | None (pilot found none) | Budget local radiologist annotation |
| **Interventional fluoroscopy labels** | S20, S49, S56 | TAIR (December 2026 labels promised) | Recheck after December 2026 |

---

## 10. Open questions and verification before preregistration

**Access requests and terms**

1. **Naija-CXR (D02).** Download and inspect the ZIP. Record:
   - image and patient counts;
   - label ontology and granularity;
   - report pairing;
   - institutions and acquisition period.

   Ask the depositor to clarify CC BY 4.0 vs the non-commercial prose.
2. **RSNA Knee (D44).**
   - Confirm the exact file-release date, site count (16 vs 19), per-study site and language metadata, and current access.
   - Resolve whether 3rd/6th-place weights were released: `plan.md` denylists them; `16` found none.
   - Confirm third-party-API approval scope for the new setups.
3. **XQA-Chest (D03).** Apply for safeguarded access. Confirm whether the 735 re-annotated MIMIC studies are in the package.
4. **LUCQUE (D19).** Ask PARADIM for the first user-access date, terms, runtime/hardware limits and the cohort (1,678 vs 3,000).
5. **Restricted Tier A.**
   - Longitudinal liver CT (D17): access request; reconcile record IDs 23349228 vs 23349229.
   - BoneLoss-PAN769 (D09): InReDD portal.
   - BUS-Large (D33).
   - OMAMA HYFOWN (D34): access, plus a patient-overlap check against KXJCIU.
6. **Licences needing review.**
   - CancerVerse: CC BY-NC-ND (derived models; publishing diffs).
   - TotalSegmentator CT v3: licence field not visible.
   - MOPG-7 and DentalOPG-1550: no licence found.
   - FUSEP data terms.
   - radiology-conflict and HUAC: no licence.
   - SKELEX: ND.
   - DINOv3: custom licence vs "open" in the plan.
   - nnFoundation: unclear.
   - UltraSAM3: `13` Apache-2.0 vs `17` unclear.
   - Mammo-FM: `13` academic-only vs `17` CC BY 4.0.
   - HoloCT: MIT, plus third-party notices.

**Date confirmations**

7. Confirm dates for:
   - CFB-GBM v2 (TCIA upload history);
   - OpticNerveSeg (artifact URL);
   - CTSpinoPelvic1K v7 (which fields are new);
   - MAGIC-CT (day);
   - ISLES'26/ATLAS v3 new cases;
   - LISA 2026;
   - TREAT-MMTB;
   - MosaicMRI;
   - CMRx4DFlow2026;
   - LIDC-annot-NLST501 (February vs August 2026; this affects the plan's Phase 3);
   - TAIR fluoroscopy availability and December annotations;
   - MetaStructAtlas full release;
   - Merlin first public weights;
   - TotalSegmentator v3-era model weights;
   - BreastGPT checkpoint;
   - HarMoE weights.
8. Run post-cutoff sweeps that were blocked or premature at the snapshot:
   - NeurIPS 2026 E&D accepted papers;
   - ISBI 2027 challenges (after 2026-11-16);
   - the five Kaggle leads (JS-rendered);
   - a fuller re-sweep, because several shards hit Exa rate limits (`10`, `11`, `12`, `14`, `17`) and `16` could not use the specified search tool.

**Overlap and data audits**

9. **Build the source-to-target overlap matrix** (§4.1 channel 2) from:
   - RAD-DINO's 5 sources;
   - MedSigLIP and MedGemma disclosures;
   - UltraSAM3's 37 sets;
   - SonoCorpus' 53 sets (check whether FUSEP is included);
   - nnFoundation's 125 sources;
   - HoloDATA's 73 sets;
   - NV-Reason-CT (CancerVerse!);
   - MedSAM / MedSAM2 / VISTA3D lists;
   - Mammo-CLIP (RSNA, VinDr).
10. **Dedup and patient-ID reconstruction** where IDs are missing: FUSEP, MOPG-7, DentalOPG-1550 (+ cross-dedup with MOPG-7), Naija-CXR, VinDr-Ground-VQA. Use pHash plus embedding, with manual review (pilot pHash false positives).
11. **Isolate the TotalSegmentator CT/MRI v3 additions** by ID diff. Reconcile the 15 unexplained MRI additions. Check IDC-sourced MRI for pre-cutoff public availability.
12. **Freeze snapshots and hashes:**
    - CancerVerse (choose v3.5.1, or document the chosen version);
    - DentalOPG-1550 v3;
    - Open-H-RF subset;
    - Kaggle files.
13. **Label-leak audit for B1 targets:** how predictable the new labels are from old public labels. Examples: ImageCAS-X segments from old lumen masks; TopBrain TA36 classes from TopCoW labels.

**Compute**

14. **Profile VRAM on the actual 24 GB card** for:
    - HoloCT-4B/8B (inference and PEFT);
    - nnFoundation-ViT (674M, 192³);
    - NV-Reason-CT QLoRA;
    - MedGemma-4B and Qwen2.5-VL-7B QLoRA;
    - DINOv3-L at 448–518 px;
    - 3D nnU-Net patch plans for CancerVerse / ImageCAS-X / TopAneu;
    - COBRA patch reconstruction.

**Design decisions to preregister** (investigator authority)

15. The F / G / M boundary per setup: BN re-estimation, temperature scaling, task arithmetic, closed-form maps (P3).
16. Whether to run a G-permitted arm alongside edit-mandated G.
17. The early-FINAL policy (P7).
18. Whether Opus image-reading pseudo-labels are allowed in F. They were the pilot's strongest method (D-ft).
19. Margins and power targets per setup, and the minimum detectable effect, given small Tier A tests.
20. Whether this portfolio **replaces or complements** `plan.md` Phase 2 (RSNA Knee) and Phase 3 (LIDC-annot-NLST501 / Pillar-0).
21. Whether pre-cutoff vs post-cutoff backbone pairs are run to measure the agent-prior-knowledge channel (§4.1, channel 3).

---

## 11. Appendix: source file index

| File | Role | Content used here |
|---|---|---|
| `plan.md` | Study plan (Phase 1 design, approved 2026-11-08) | Arms A–H, MFXR details (D01), denylist and enforcement stack, encoders (SKELEX, MedSigLIP, DINOv3-L, MRI-CORE, OrthoFoundation), RSNA Knee Phase 2 specifics, Phase 3 candidates |
| `results/phase1-results.md` | Phase 1 pilot results (2026-11-11) | Lessons in §2: G did not edit; G2 edits; ablations; D-ft dominance; early stopping; transductive smoothing; side channel; costs |
| `research/wsp-setups/00-research-brief.md` | Search brief for the dataset fleet | Release-date rule, per-dataset fields, preferences (no shortcut framing; shift and domain gap) |
| `research/wsp-setups/01-brainstorm-opus.md` | Brainstorm, S1–S44 | Hypotheses H1–H7, design principles, setup designs, ranking, threats to validity |
| `research/wsp-setups/02-orchestrator-supplement.md` | Supplement, S45–S56 | Version upgrade, guideline revision, VLM, multilingual, new hardware, new protocol, weak labels, geographic, restricted access, operating point, longitudinal, 3D FM |
| `research/wsp-setups/10-cxr-radiography.md` | Shard: CXR and projection radiography | D02–D11; C01–C07; excluded leads; CXR backbones |
| `research/wsp-setups/11-ct.md` | Shard: CT | D12–D22; C08–C14, C43; CT backbones (HoloCT, Merlin, CT-FM, ULS) |
| `research/wsp-setups/12-mri.md` | Shard: MRI | D23–D29; C15–C23; BrainFedFM, Brain2Vec, MRI_BreastSeg |
| `research/wsp-setups/13-breast-us.md` | Shard: breast and ultrasound | D30–D35; C24–C28; US/mammo/echo models (USFM, SonoBase, UltraSAM3, Mammo-FM, EchoPrime) |
| `research/wsp-setups/14-nuclear-multimodal-3dfm.md` | Shard: nuclear, interventional, multimodal, 3D FM | D36–D39; C29–C31; HoloCT, PET legacy comparators; FAP / EHR gaps |
| `research/wsp-setups/15-text-vlm.md` | Shard: text and VLM | D40–D43; C32–C35; Qwen2.5-VL, MedGemma, CheXagent |
| `research/wsp-setups/16-challenges-cross.md` | Shard: challenges and cross-cutting | D13 / D24 (cross-check), D44, D45; C36–C42; MICCAI / Grand Challenge / ISBI / RSNA / Kaggle / NeurIPS inventory; LMIC gap |
| `research/wsp-setups/17-backbones.md` | Shard: pretrained backbones | §6 backbone tables, prior SAE / editing work, pairings, 24 GB conventions |
| `research/wsp-setups/rerun.js` | Orchestration script for shard reruns (not content) | Not used for content |

**Disagreements carried over from the inputs (not resolved here):**

- MFXR patient IDs: 1,482 vs 1,484.
- Naija-CXR licence.
- XQA-Chest MIMIC subset.
- DentalOPG-1550 v2 vs v3 counts.
- BoneLoss-PAN769 licence vs access.
- TAIX-Ray paper vs file date.
- CancerVerse counts.
- AMPLIFAI counts.
- ImageCAS-X image overlap.
- Longitudinal liver CT record ID.
- LUCQUE cohort size.
- LIDC-annot-NLST501 date.
- TotalSegmentator MRI v3 15 unreconciled cases.
- TopAneu / TopBrain dependence.
- MetaStructAtlas QA counts.
- CMB patient delta.
- TAIR fluoroscopy availability.
- OMAMA scope.
- BUS-Large access.
- DBT-2026 exam count.
- CLEAR-EC access.
- RSNA Knee site count; winner weights (plan vs `16`).
- Merlin release date (`11` vs `14` vs `17`).
- Mammo-FM licence (`13` vs `17`).
- UltraSAM3 licence (`13` vs `17`).
- DINOv3 licence (`17` vs plan).
- MSK FM availability (`17` vs plan's SKELEX).
- CT-FM repository link (as given in `11`; verify).
