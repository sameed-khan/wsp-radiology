# WSP for Radiology Practitioners — Experimental Setting Brainstorm

**Scope.** These are candidate settings for testing whether weight-space programming (WSP) is worth adding to a radiology ML practitioner's toolbox. Each setting compares two arms under identical budgets and tools. **Arm F** uses standard ML engineering: any training, but no direct weight edits. **Arm G** may do everything F does, but must use direct weight edits derived from interpretability.

**What the pilot taught us.** In the Monteggia pilot, the bottleneck was label scarcity, not representation quality. Dataset quirks such as duplicate crops and confounds mattered more than anything else, and edits moved test AUROC by at most 0.02. A redesign should therefore:

- (a) pick settings where WSP can bring **information or constraints that gradient training on the available labels cannot easily use**: an unlabeled target distribution, a source model, a textual or anatomical prior, a locality or auditability requirement, a no-data constraint, or a requirement to compose models;
- (b) use curated, deduplicated, patient-level-split datasets with large enough test sets to resolve effects of about 0.01–0.02;
- (c) **avoid "spurious shortcut removal" as a framing.** Where a setting touches nearby ground (subgroups, artifacts, error patching), it is framed as a distribution-shift, maintenance, or capability problem.

---

## 0. Where could WSP have a comparative advantage? (hypotheses the settings target)

| ID | Hypothesis | Why gradient training might be worse | Settings that test it |
|---|---|---|---|
| H1 | **No or few target labels.** Edits can use *unlabeled* target data (statistics, feature directions) or prior knowledge in ways fine-tuning can't when labels are ~0. | Fine-tuning on k≈10 overfits, and unsupervised DA methods are brittle | S1–S8, S12, S17–S19 |
| H2 | **Locality and low churn.** Edits change behavior only where intended, so fewer unintended prediction flips. | Fine-tuning moves everything (catastrophic forgetting, churn) | S9–S11, S23–S25, S35 |
| H3 | **Auditability and change control.** Small, documented, reversible diffs suit regulated "locked" models (FDA PCCP). | Fine-tuning diffs are dense and hard to justify | S11, S10, S35 |
| H4 | **Composition without data.** Merging, transplanting, and inflation reuse existing weights without pooling data. | Requires data sharing or retraining | S20–S22, S36 |
| H5 | **Exact, known transforms.** Some shifts are analytically invertible in weights (intensity inversion, windowing, resolution, channel added). | Training only has to *re-learn* what is known | S12, S16, S21, S22 |
| H6 | **Removal.** Deleting a capability, a data subset, or a behavior is a natural fit for ablation-style edits. | Gradient unlearning is approximate and costly | S26–S28, S32, S39 |
| H7 | **Compute and time.** A hotfix in hours on a CPU vs. a retraining cycle. | Retraining pipelines, GPUs, revalidation | S9, S10, S38 |
| Null | **Fair null tests.** Settings where we expect F≈G. Their purpose is to calibrate claims and stop us from cherry-picking. | — | S13, S29, S34 |

---

## 1. Cross-cutting design principles

### 1.1 Starting points and arms
1. **Same starting checkpoint for both arms.** Each setting fixes a "deployed" checkpoint, usually a foundation model plus a source-site fine-tune trained by us, not by the agents. Both arms start from it byte-identical. Report results relative to this checkpoint.
2. **Arm G = F's toolset + mandatory edits.** G may also train. G must log every edit as structured metadata: target tensor, operation, magnitude, interpretability evidence, and rationale.
3. **Edit-contribution ablation.** For every final G model, revert each logged edit (individually and all together) while keeping the training G did, then re-score. Report "edit contribution" = G_final − G_final-with-edits-reverted. Without this, a G win may just be extra training.
4. **Optional third arm E (edits only, no gradient steps).** This isolates whether WSP can stand alone, which matters for the locked-model and no-GPU settings.
5. **Random-edit control.** Apply edits with the same tensor locations and norms but random directions or units. This tests whether the interpretability guidance matters, or only the magnitude or regularization effect.
6. **Mechanical WSP baselines.** Non-agent implementations of known edit methods: BN/LN statistics re-estimation, task arithmetic, TIES/DARE, ROME/MEMIT-style rank-1 edits, activation-steering bakes, and fixed-rule pruning. If the agent's G can't beat a script, the "agent + interpretability" story fails.

### 1.2 Data hygiene (pilot lesson)
7. **Patient-level splits plus near-duplicate detection** (perceptual hash and embedding cosine) across train, dev, and test. Publish the dedup audit before the agents run.
8. **Sealed test sets.** Agents never see target test images or labels. They get only a small target dev pool, plus (per regime) unlabeled target data. Scoring runs on a separate harness.
9. **Pre-audit for confounds.** Before choosing a dataset, run quick checks such as a "site-from-image" probe and a "label-from-metadata" probe. Drop datasets where trivial confounds explain most of the signal. This avoids repeating the pilot.
10. **Power analysis.** Size test sets so the 95% CI on ΔAUROC is ≤±0.01–0.015, which usually means ≥1,000–3,000 test studies with ≥150–300 positives. For segmentation, ≥50–100 test volumes per target site. Report the minimum detectable effect.

### 1.3 Regimes (each setting is run across a grid)
11. **Target-data regimes:**
    - R0: no target data at all, only a textual description of the shift
    - R1: unlabeled target data (N=100–1,000)
    - R2: k labeled target patients (k ∈ {5, 10, 25, 50, 200})
    - R3: abundant target labels, an oracle/upper bound that agents don't get

    WSP's value probably peaks at R0–R2 and disappears at R3. Plotting the curve is itself the deliverable.
12. **Compute parity.** Equal GPU-hours, equal wall clock, and equal agent token/turn budget. Also report a *low-compute regime* (e.g., 1 GPU-hour or CPU-only) where retraining is barely possible.

### 1.4 Scoring
13. **Per-image or per-study independent scoring.** No transductive batch effects at test time unless the setting explicitly allows them (TTA settings). Batch norm runs in eval mode with stats frozen at the submitted values.
14. **No early stopping on test, no test-time hyperparameter selection.** Agents submit one final model. Optionally they also submit a pre-registered "fallback" model, which is scored separately.
15. **Replicates.** ≥3 (ideally 5) independent agent runs per arm × setting × regime, with different agent seeds and data subsamples for k-shot. Report between-run variance; agent variance is usually larger than seed variance.
16. **Multi-axis scorecard** (matching what practitioners care about):
    - (a) target performance: AUROC/AUPRC, Dice/HD95, FROC, RadGraph-F1/GREEN
    - (b) source/retained performance
    - (c) worst-site / worst-subgroup performance
    - (d) calibration: ECE and Brier
    - (e) **churn**: fraction of reference-set predictions that flip vs. the starting checkpoint
    - (f) diff footprint: number and fraction of changed parameters, ‖Δθ‖
    - (g) time-to-fix and compute used
    - (h) reversibility and auditability, rated by blinded reviewers on a change log
17. **Pre-registration.** Before running, register the primary metric per setting and the "WSP helps" threshold (e.g., ΔAUROC ≥0.02 *or* equal performance with ≥50% less churn).
18. **Blinded evaluation** of change logs and model artifacts for auditability, by a radiologist and a regulatory-affairs reviewer.
19. **Strong standard baselines in F's playbook**, so F isn't a strawman. F should have access to LoRA, linear probing, LP-FT, BN adaptation/TENT, SHOT, mixup, augmentation (including MONAI and TorchIO intensity/artifact augmentation), class-balanced losses, and temperature scaling.
20. **Report negative results as results.** If WSP gives ≤0.01 in most settings but wins on churn or auditability, that is useful practitioner guidance.

---

## 2. Settings (40), grouped by theme

Format: **Problem → Why WSP might help / null rationale → Design → Data needs → Clean-comparison notes.**

---

### Theme A — Cross-site, scanner, vendor, protocol, and population shift

#### S1. CXR cross-institution transfer with tiered target labels
- **Problem.** A CXR classifier built at hospital A loses AUROC at hospital B because of different scanners, processing LUTs, patient mix, and geography. This is the most common deployment failure.
- **Why WSP.** Site differences often show up as a few dominant feature directions, such as processing or contrast style. An edit can project out the "site direction," estimated from unlabeled A vs. B embeddings, or re-center LayerNorm/BN statistics. That uses unlabeled target data that k-shot fine-tuning ignores (H1).
- **Design.**
  - Start: RadDINO or a CXR-FM (e.g., CheXagent's vision encoder, MedImageInsight) fine-tuned on CheXpert for 5–8 findings.
  - Targets: MIMIC-CXR (same country, different site), PadChest (Spain), VinDr-CXR (Vietnam), plus a geographic population-shift sub-variant for TB: Shenzhen↔Montgomery↔TBX11K.
  - Regimes R0–R2.
  - F: LP-FT/LoRA on the k target labels, BN/LN adaptation, augmentation.
  - G: F plus edits, e.g., nulling the site direction in residual streams, rescaling heads, and a rank-1 edit of the classifier toward target-class means estimated from pseudo-labels.
  - Primary metric: macro-AUROC on the target site, with source AUROC as a guardrail.
  - **WSP helps if** G beats F by ≥0.02 at R1/R2 (k≤25), with an edit-ablation contribution ≥0.01 and source drop ≤0.005.
- **Data.** ≥3 sites with harmonized labels for overlapping findings. The test set needs ≥2,000 studies/site. Radiologist-adjudicated test labels are preferable (VinDr, the CheXpert test set, MIMIC's gold subsets) because NLP labels add noise.
- **Clean comparison.** Harmonize label definitions first; otherwise label shift masquerades as covariate shift (see S40). Dedupe follow-up studies per patient. Fix the image preprocessing pipeline for both arms.

#### S2. Multi-vendor cardiac MRI segmentation
- **Problem.** Cardiac cine segmentation trained on Siemens/Philips fails on GE/Canon. Contrast and intensity profiles differ.
- **Why WSP.** Vendor effects concentrate in early filters and normalization layers, while shape priors in the decoder transfer. An edit can retune only the intensity-sensitive stem channels (found with vendor-predicting probes) and leave the decoder untouched (H1, H2).
- **Design.**
  - Data: M&Ms-1 (4 vendors, 6 centers) and M&Ms-2.
  - Start: nnU-Net trained on vendors A+B.
  - Targets: vendors C and D. Regimes R1 (unlabeled C/D volumes), R2 (k=1, 3, 5 labeled volumes).
  - F: fine-tuning, intensity augmentation, BN adaptation.
  - G: F plus probe-guided stem-channel rescaling, normalization-stat transplant, and channel ablation.
  - Primary metric: Dice (LV, RV, MYO) on target vendors. Secondary: HD95 and source Dice.
- **Data.** Public, multi-vendor, with expert labels. ~75–150 test subjects per vendor.
- **Clean comparison.** Use the same nnU-Net plan and the same patch size and spacing resampling. Don't let F change the preprocessing plan unless G can too.

#### S3. Multi-site prostate MRI: protocol and coil shift
- **Problem.** Endorectal coil vs. no coil, different T2 protocols, 1.5T vs. 3T. Prostate gland segmentation varies across sites.
- **Why WSP.** As in S2, but the shift is protocol-driven and includes a geometric component (coil deformation). This tests whether edits handle more than intensity shift.
- **Design.**
  - Data: the 6-site prostate dataset (RUNMC, BMC, I2CVB, UCL, BIDMC, HK; Liu et al.), plus PI-CAI as a large external set.
  - Leave-one-site-out. Regimes R0–R2.
  - Primary metric: Dice on the held-out site. Worst-site Dice is co-primary.
- **Data.** Small (30–80 volumes/site), so use PI-CAI to power the test.
- **Clean comparison.** Report per-site results; don't average away the effect.

#### S4. Mammography vendor and image-processing shift
- **Problem.** Screening models trained on Hologic "for presentation" images degrade on GE/Siemens/Fuji. Vendor post-processing differs a lot. This is a major real-world issue for commercial mammography AI.
- **Why WSP.** Vendor processing is a largely global, monotone transform of intensity and texture, which may be correctable with an edit in the stem or normalization (H1, H5).
- **Design.**
  - Data: EMBED (multi-vendor), VinDr-Mammo (Siemens), CMMD (GE), OPTIMAM if accessible.
  - Start: Mammo-CLIP or an EfficientNet/ConvNeXt malignancy classifier trained on EMBED-Hologic.
  - Target: another vendor.
  - Primary metric: exam-level AUROC for malignancy. Secondary: sensitivity at 90% specificity, which is the clinical operating point.
- **Data.** Exam-level pathology-confirmed labels, vendor metadata, ≥200 cancers in the test set.
- **Clean comparison.** Fixed view-fusion logic. Don't allow F to change the input resolution unless G can.

#### S5. CT reconstruction kernel and slice-thickness shift
- **Problem.** Sharp vs. soft kernels and thin vs. thick slices change texture. Nodule malignancy classifiers and segmentation degrade.
- **Why WSP.** Kernel differences are mostly frequency-domain. An analytically motivated edit of first-layer filters (attenuating high-frequency response) could approximately invert them (H5). This makes a crisp mechanistic test.
- **Design.**
  - Data: LIDC-IDRI (kernel metadata), NLST (paired kernels for some scans), LNDb.
  - Paired-reconstruction subsets give a *ground-truth* counterfactual: the same patient under two kernels.
  - Tasks: nodule malignancy classification, or TotalSegmentator organ Dice.
  - Primary metric: AUROC (or Dice) on the target kernel, plus paired-consistency, i.e., agreement between predictions on the paired recons.
- **Data.** Paired reconstructions are the gold standard here. Raw-data reprojection simulations are a fallback.
- **Clean comparison.** Paired data removes population confounds, which makes this one of the cleanest shift settings available.

#### S6. MRI field-strength and scanner-upgrade shift (neuro)
- **Problem.** A site upgrades from 1.5T to 3T, or changes vendor. Brain segmentation, lesion detection, or volumetrics shift.
- **Why WSP.** Same as S2, plus a quantitative bias problem (volumes systematically shifted). A bias or affine edit at the output could fix it exactly.
- **Design.**
  - Data: ADNI (documented scanner changes; traveling subjects), OASIS-3, and the MS lesion datasets (MSSEG multi-scanner, ISBI 2015). SRPBS traveling-subject data gives paired scans.
  - Primary metric: lesion-wise F1 or Dice, plus volume bias (Bland–Altman) on traveling subjects.
- **Data.** Traveling-subject or paired data greatly strengthens causal claims.
- **Clean comparison.** As in S5, paired subjects remove population confounds.

#### S7. Zero-target-data domain generalization (multi-source)
- **Problem.** The developer doesn't know where the model will be deployed. They have several training sites and want robustness to unseen sites.
- **Why WSP.** With site labels on the training data, an agent can locate site-encoding units or directions and remove them, building invariance by construction (H1 at R0). The fair alternatives are DG training methods: GroupDRO, IRM, CORAL, augmentation.
- **Design.**
  - Train on 3–4 CXR sites; test on 2 unseen sites. Alternatively, use the M&Ms or prostate sites.
  - F: any DG method. G: F plus site-direction ablation and head pruning guided by site probes.
  - Primary metric: mean and worst unseen-site AUROC or Dice.
- **Data.** ≥5 sites with site metadata.
- **Clean comparison.** Identical source data. No access to unseen sites, not even unlabeled.

#### S8. Test-time / unlabeled-target adaptation, edit vs. TTA
- **Problem.** At go-live, the practitioner has a stream of unlabeled target images and no labels or annotation budget.
- **Why WSP.** It is a direct contest between gradient-based TTA (TENT, SHOT, pseudo-label self-training), which is known to be unstable, and one-shot statistic/feature edits computed from the unlabeled stream (H1).
- **Design.** Any of S1–S6 at R1 only. F: TTA and self-training. G: edits computed from unlabeled data, plus TTA if desired.
- **Primary metric:** target AUROC/Dice, plus **stability**: performance variance across runs and failure rate (runs worse than the starting checkpoint).
- **Clean comparison.** The same unlabeled pool. The final model is frozen before test (no online updating during test unless both arms do it).

---

### Theme B — Post-deployment maintenance and change control

#### S9. Temporal drift hotfix with a small post-drift sample
- **Problem.** Months after deployment, performance slips (new scanner fleet, protocol update, case-mix shift). The team has 50–200 newly labeled cases and wants a fix without full retraining or revalidation.
- **Why WSP.** It could give a localized, fast fix with low churn on cases unaffected by the drift (H2, H7).
- **Design.**
  - Data: a temporal split of MIMIC-CXR (anchor-year groups), or CheXpert → CheXpert Plus/later years. Optionally a real scanner change from DICOM metadata.
  - Start: a model trained on early years.
  - Budget: n post-drift labeled studies, 2 GPU-hours.
  - Primary metric: post-drift AUROC. Co-primaries: pre-drift AUROC retention and churn on a frozen pre-drift reference set.
  - **WSP helps if** it gets equal post-drift gains with ≥50% less churn, or better gains at equal churn.
- **Data.** Timestamps and scanner/manufacturer DICOM tags.
- **Clean comparison.** Confirm the drift is real (measure the AUROC drop first). Hold patient overlap across time out of both sets.

#### S10. Error-report-driven patching (the "bug ticket")
- **Problem.** Radiologists flag 10–30 specific failures, for example missed apical pneumothoraces or missed fractures in casts. The team must patch these without breaking anything else.
- **Why WSP.** This is the canonical model-editing use case: specific, local, and auditable (H2, H3).
- **Design.**
  - Start: a deployed CXR or MSK-fracture model (MURA, GRAZPEDWRI-DX).
  - We curate an "error family" via metadata or annotation: a coherent subset of failure cases sharing a visual property. The agents get N flagged cases. The *held-out* family members and all other cases are sealed.
  - Primary metric: sensitivity on held-out family members (generalization of the fix). Guardrails: overall AUROC, specificity, and churn outside the family.
- **Data.** Requires annotated sub-types. VinDr-CXR boxes, RSNA pneumothorax segmentations, and GRAZPEDWRI-DX cast/plaster annotations are candidates.
- **Clean comparison.** The family definition must not be visible as metadata to either arm beyond the flagged cases. Both arms get the same flagged cases.

#### S11. Locked-model change control under a parameter-diff budget (PCCP)
- **Problem.** For FDA-cleared devices, modifications fall under a Predetermined Change Control Plan. Small, bounded, documented changes are easier to justify than full retrains.
- **Why WSP.** WSP produces sparse, interpretable, reversible diffs (H3). The fair comparison is *budgeted* fine-tuning: F gets the same diff budget via sparse fine-tuning, LoRA rank-1, BitFit, or last-layer-only.
- **Design.**
  - Run S1 or S9 with a hard constraint: ≤0.1% (and ≤0.01%) of parameters changed, or only pre-declared modules.
  - Each arm submits a change log in a PCCP-style template.
  - Primary metric: target gain per changed parameter, plus a blinded reviewer rating of auditability and risk (Likert scale and accept/reject).
  - **WSP helps if** it wins on performance at equal budget, or on reviewer acceptance at equal performance.
- **Data.** As in S1/S9.
- **Clean comparison.** Identical diff budgets. Reviewers are blinded to the arm (normalize change-log format).

#### S12. Input-pipeline changes (MONOCHROME1/2, windowing, bit depth, resolution)
- **Problem.** A site's DICOM export changes: inverted photometric interpretation, different default window, 8-bit vs. 12-bit, different pixel spacing. Models break silently.
- **Why WSP.** Many such changes are exactly invertible in weights. For example, flipping the sign of first-layer weights and adjusting the bias undoes intensity inversion, and interpolating positional embeddings handles resolution (H5). This is a *positive control*: WSP should win cleanly. If it doesn't, the agent tooling is broken.
- **Design.**
  - Simulate pipeline changes on S1 data. Rule: input preprocessing is frozen, so the deployed pipeline can't be changed (realistic for a vendor box).
  - F: fine-tuning on k target images. G: edits.
  - Primary metric: AUROC recovery vs. the starting model on the original pipeline, and time-to-fix.
- **Data.** Any; this is synthetic but realistic.
- **Clean comparison.** State clearly that in practice you'd just fix preprocessing. The setting measures the edit machinery, not practical necessity.

#### S13. Prevalence shift and recalibration (screening → diagnostic) — **null-leaning**
- **Problem.** A model is deployed from an ED population (high prevalence) to outpatient screening (low prevalence). Calibration and PPV at the threshold break.
- **Why WSP / null.** The best-known fix is a bias/temperature adjustment, which is effectively a weight edit anyway. This tests whether "agent-driven" interpretability adds anything over simple logit adjustment (expected: no).
- **Design.**
  - Resample CXR datasets to create prevalence shifts. Also use real ones: RSNA ICH vs. CQ500, and screening vs. diagnostic mammography in EMBED.
  - Primary metric: ECE and Brier at the target. Secondary: sensitivity and PPV at a fixed threshold.
- **Clean comparison.** Give F the same unlabeled-target prevalence estimation tools (EM / BBSE).

---

### Theme C — Natural-image → medical domain gap

#### S14. DINOv3 → CXR: closing the gap to a domain foundation model
- **Problem.** Natural-image backbones (DINOv2/v3, CLIP, ConvNeXt) are the default starting point for many practitioners. How close can they get to RadDINO-class performance?
- **Why WSP.** Natural features include texture and edge detectors that partly match radiologic patterns. Edits could re-weight the relevant ones, suppress color/semantic channels, and re-wire the stem for grayscale (H1). A domain FM gives an *upper bound* and a *target representation* that edits can steer toward without labels, e.g., by aligning DINOv3 head outputs to RadDINO features via closed-form linear maps baked into weights.
- **Design.**
  - Start: DINOv3 ViT-B/L with a linear head trained on k source labels.
  - Task: 5–8 CXR findings and a rare finding. Regimes: k ∈ {10, 50, 200, 1000} plus an unlabeled CXR pool (R1).
  - F: LP, LP-FT, LoRA, continued SSL pretraining on unlabeled CXRs within the compute budget.
  - G: F plus edits.
  - Primary metric: the fraction of the DINOv3 → RadDINO gap closed, at fixed compute.
  - **WSP helps if** G closes ≥X% more of the gap than F at small compute.
- **Data.** Large unlabeled CXR pool (MIMIC), labeled subsets, external test.
- **Clean comparison.** F's continued-pretraining option is the strong competitor. Compute parity is essential.

#### S15. DINOv3 → CT/MRI slices: HU-windowing stem circuit
- **Problem.** Natural backbones expect 8-bit RGB, while CT is 12-bit HU and MRI intensities are arbitrary. Practitioners hack in 3 windows mapped to RGB.
- **Why WSP.** A hand-built first-layer "multi-window" circuit (piecewise-linear HU windowing implemented with clamps and ReLUs in an inserted layer) can carry diagnostic dynamic range into the pretrained stem. It is a principled edit vs. ad-hoc preprocessing or learned adapters (H5).
- **Design.**
  - Data: RSNA ICH (CT head), CQ500 as external, or TotalSegmentator organs (2D slice segmentation with a DINOv3 encoder plus decoder).
  - F: standard 3-window RGB plus fine-tuning or a learned 1×1 adapter.
  - G: F plus the inserted window circuit and stem edits.
  - Primary metric: AUROC (or Dice) at the external site; low-k regimes.
- **Clean comparison.** Both arms must use the same raw HU input (no pre-windowed images given to one arm only).

#### S16. Natural → ultrasound (speckle domain)
- **Problem.** Ultrasound has heavy speckle, operator dependence, and vendor differences. Natural FMs transfer poorly. Ultrasound FMs (USFM, EchoCLIP) are emerging.
- **Why WSP.** Speckle-sensitive high-frequency channels can be identified and attenuated. Also tests whether WSP generalizes beyond X-ray/CT.
- **Design.**
  - Data: breast ultrasound (BUSI → BUS-BRA / UDIAT cross-site), or EchoNet-Dynamic → EchoNet-Pediatric / CAMUS for LV segmentation or EF.
  - Start: DINOv3 fine-tuned on the source.
  - Primary metric: target AUROC (BI-RADS benign/malignant), or Dice / EF MAE.
- **Clean comparison.** Remove burned-in annotations, calipers, and text overlays in preprocessing for both arms. The goal is to evaluate domain gap, not overlay artifacts.

#### S17. CLIP-style VLM → radiology zero/few-shot vocabulary editing
- **Problem.** General CLIP/BiomedCLIP models misunderstand radiology terms ("blunted costophrenic angle", "air bronchogram"). Practitioners use them for zero-shot triage or retrieval.
- **Why WSP.** Rank-1 edits to the text tower or projection can re-map term embeddings to image-concept centroids estimated from a few examples or SAE features (H1). The same mechanism can construct a classifier for a new finding from its *textual definition* with zero image labels.
- **Design.**
  - Start: CLIP, BiomedCLIP, or CheXzero.
  - Task: zero-shot and k-shot CXR findings (PadChest's 170+ findings give a long tail).
  - F: prompt engineering, prompt tuning, linear probe, CLIP-adapter.
  - G: F plus text/projection edits.
  - Primary metric: macro-AUROC over long-tail findings at k ∈ {0, 1, 5}.
- **Data.** Image–report pairs for concept estimation (MIMIC), PadChest labels for testing.
- **Clean comparison.** The same text prompts are available to both arms. Report retrieval metrics on unedited concepts (locality).

---

### Theme D — Modality transfer

#### S18. CT → MRI abdominal organ segmentation
- **Problem.** Plenty of labeled CT data, few MRI labels. A practitioner wants an MRI organ segmenter from a strong CT model (e.g., TotalSegmentator).
- **Why WSP.** Organ shape and topology priors (decoder) transfer; the appearance mapping (stem/encoder) doesn't, and contrast relationships invert (fat bright on T1 MRI, mid-gray on CT). Targeted stem edits plus keeping the decoder frozen could beat fine-tuning at k≤3 (H1, H5).
- **Design.**
  - Data: AMOS (paired-ish CT and MRI, 15 organs), CHAOS (CT + MRI), TotalSegmentator-MRI.
  - Start: nnU-Net or a SwinUNETR CT model.
  - Regimes: k ∈ {0, 1, 3, 10} MRI volumes plus unlabeled MRI.
  - F: fine-tuning, CycleGAN/intensity augmentation, MRI-specific SSL.
  - G: F plus edits.
  - Primary metric: mean Dice across organs on MRI test. Guardrail: CT Dice if the model must stay dual-modality.
- **Clean comparison.** Identical resampling and spacing, and the same organ label set.

#### S19. 2D → 3D weight inflation and slice-aggregation circuits
- **Problem.** Most FMs are 2D, while clinical CT/MRI is 3D. Practitioners inflate 2D kernels (I3D-style) or aggregate slices.
- **Why WSP.** Inflation is itself a weight edit. The question is whether *interpretability-guided* inflation (choosing which channels get depth extent, hand-wiring cross-slice attention to replicate known 3D features such as a vessel vs. nodule distinction) beats naive inflation plus fine-tuning (H4, H5).
- **Design.**
  - Data: CT-RATE (CT volumes + 18 abnormality labels; external RadChestCT), or RSNA ICH at study level, or LUNA16 nodules.
  - Start: a 2D RadDINO or DINOv3. Comparator: native 3D FMs (CT-FM, Merlin) as an upper bound.
  - Primary metric: study-level AUROC at the external site.
- **Clean comparison.** Equal compute. F may also inflate, but only with standard recipes (centered or uniform inflation).

#### S20. Adding an input modality to a deployed model (CT → PET/CT)
- **Problem.** A tumor-segmentation model was built on CT. The site now has PET/CT and wants to use PET uptake without discarding the validated CT model.
- **Why WSP.** Insert a PET channel whose stem weights are hand-wired to a known-good detector (an SUV-threshold or local-max circuit) and leave the CT pathway unchanged at init, so performance is guaranteed not to degrade at step 0 (H2, H5). This is the classic "grow the network" surgery.
- **Design.**
  - Data: autoPET (FDG PET/CT, multi-center versions), HECKTOR (head & neck PET/CT, 7+ centers).
  - Start: a CT-only model.
  - Primary metric: lesion Dice and lesion-wise detection F1. Secondary: the false-positive volume (a known problem in PET, e.g., physiological bladder/brain uptake).
- **Clean comparison.** F can add the channel with zero-init or random init and fine-tune. G must hand-wire. The budget is equal.

#### S21. Projection radiography FM → mammography / DBT
- **Problem.** Mammography-specific FMs are limited. Can a CXR FM transfer? The physics differ (soft-tissue, high resolution).
- **Why WSP.** Tests whether edits can repurpose CXR-specific features (rib/edge detectors) toward calcification and mass morphology. This is a fair null-leaning test of "cross-modality repurposing."
- **Design.** RadDINO → CBIS-DDSM / VinDr-Mammo for mass/calcification classification. Compare against ImageNet-pretrained and Mammo-CLIP baselines.
- **Primary metric:** AUROC at k ∈ {50, 500}.
- **Clean comparison.** Use the same patch/ROI extraction for both arms. The ROI-level task avoids full-field resolution confounds.

---

### Theme E — Label scarcity and rare disease

#### S22. Rare finding with prior-knowledge injection
- **Problem.** Rare but critical findings (pneumomediastinum, tension pneumothorax, Monteggia, SCFE, pediatric abuse fractures) have <50 positives at most institutions.
- **Why WSP.** The pilot showed that label scarcity dominates. WSP can only help if it injects information *from outside the labels*: anatomical localization priors (e.g., "the radiocapitellar line must pass through the capitellum"), concept features from SAEs trained on large unlabeled data, or knowledge from a related common finding (pneumothorax → pneumomediastinum). The setting tests H1 directly, with explicit knowledge channels.
- **Design.**
  - Data: PadChest rare labels, VinDr-CXR rare classes, RSNA cervical spine fracture (subtypes), GRAZPEDWRI-DX (rare pediatric fracture classes), SCFE / pediatric hip datasets.
  - k ∈ {5, 10, 25} positives.
  - F: few-shot fine-tuning, transfer from the related finding, synthetic augmentation.
  - G: F plus hand-built circuits (e.g., a landmark-relation detector using probes for anatomical landmarks) and an SAE-feature classifier.
  - Primary metric: AUROC and sensitivity at fixed specificity, on a large sealed test set (pool across sites to get enough positives).
- **Clean comparison.** Both arms get the *same* knowledge source (text of the radiological rule, landmark annotations on unlabeled images), so G doesn't win by information asymmetry.

#### S23. Zero-image-label concept classifiers from knowledge or text
- **Problem.** For a new finding (e.g., a new device type, an emerging disease like COVID in 2020), there are initially no labels.
- **Why WSP.** Construct a classifier from SAE features plus textual concept descriptions, or a VLM text embedding projected into the image model, with no gradient on labels (H1, R0).
- **Design.**
  - Simulated "emergence": hold out COVID (BIMCV-COVID19+, COVIDx) or a device class (e.g., Impella, LVAD) from the start model's labels.
  - Arms get unlabeled images plus text. F: zero-shot VLM prompting, weak labels from report NLP.
  - Primary metric: AUROC at k=0, then the learning curve as labels arrive (k = 5, 25).
- **Clean comparison.** F also gets report text for weak labeling. This is a strong baseline that WSP must beat.

---

### Theme F — Continual learning (adding capability without forgetting)

#### S24. Adding a new finding to a deployed multi-label classifier
- **Problem.** A deployed CXR model detects 8 findings. The product team wants a 9th (e.g., "pneumoperitoneum" or "support device malposition") without degrading the cleared 8.
- **Why WSP.** Add an output unit wired to existing features (SAE or probe directions) plus rank-1 edits, so old heads are untouched by construction (H2). F must fight forgetting with replay or regularization (EWC, LwF, frozen backbone).
- **Design.**
  - Start: a model trained on 8 MIMIC/CheXpert findings.
  - New class from PadChest/VinDr/NIH with k ∈ {25, 100, 500}.
  - F: frozen-backbone new head, LoRA, LwF, replay (with the old training data, or without it in a "no old data" variant).
  - Primary metric: new-class AUROC. Co-primary: max old-class AUROC drop and churn on old classes.
  - **WSP helps if** G's new-class AUROC ≥ F's while old-class churn ≈0.
- **Clean comparison.** Run variants with and without old-data replay. The no-replay variant is the realistic one when the original training data has expired under governance.

#### S25. Adding a new structure to a segmentation model
- **Problem.** A TotalSegmentator-style model needs a new structure (e.g., a specific vessel or a lymph-node station) with few labels.
- **Why WSP.** Same as S24, for dense prediction. It also tests whether edits can carve out a new class from an existing parent class (e.g., splitting "aorta" into segments) via decoder unit rewiring.
- **Design.**
  - Data: TotalSegmentator v2 (hold out several classes), plus AMOS / AbdomenAtlas.
  - Primary metric: new-structure Dice at k ∈ {1, 5, 20} volumes. Guardrail: mean Dice change on old structures.
- **Clean comparison.** The held-out structure must not appear as an implicit "background" artifact. Retrain the start model with it merged into background, or exclude its voxels.

#### S26. Sequential site onboarding (continual domain adaptation)
- **Problem.** A vendor rolls out to sites one at a time and adapts to each new site. Earlier sites must not regress.
- **Why WSP.** Per-site edits can be modular and switchable, e.g., site-keyed normalization edits or a small "site patch." That beats sequential fine-tuning, which accumulates forgetting (H2, H4).
- **Design.** M&Ms vendors or prostate sites in a sequence of 4–6. After each step, evaluate on all seen sites and the next unseen one.
- **Primary metric:** average Dice/AUROC over seen sites after the final step (backward transfer), plus forward transfer.
- **Clean comparison.** Fixed site order across arms. Randomize the order across replicates.

---

### Theme G — Unlearning and capability removal

#### S27. Site/cohort unlearning (consent withdrawal, data-use agreement expiry)
- **Problem.** A partner hospital withdraws or its DUA expires, and its contribution must be removed. Retraining from scratch is costly and may require revalidation.
- **Why WSP.** Site-specific knowledge may be concentrated in identifiable units or directions. Ablating them approximates "retrain without site X" cheaply (H6).
- **Design.**
  - Train on 4 sites including X. The gold standard is a retrain without X (several seeds).
  - F: gradient ascent / NegGrad+, fine-tune-on-retain, SCRUB, SalUn.
  - G: F plus targeted ablations and edits.
  - Primary metric: distance to the retrain gold standard. This combines (i) membership-inference advantage on X (target ≈ the retrain's), (ii) X-site performance ≈ the retrain's, and (iii) retained performance on other sites.
- **Data.** Multi-site CXR or MRI with clear site IDs.
- **Clean comparison.** Use the retrain-model distribution (several seeds) as the reference, not "zero performance on X". Over-forgetting is also a failure.

#### S28. Capability removal: demographic attribute inference
- **Problem.** CXR models can predict self-reported race, sex, and age from images. Some deployments (privacy, fairness governance) require that the released embedding or model *not* expose these, while keeping diagnostic utility. This is a *capability removal* setting, not shortcut removal: the target is attribute recoverability from the released representation.
- **Why WSP.** Concept erasure (LEACE/INLP-style projections baked into weights) is a weight edit with guarantees for linear probes (H6).
- **Design.**
  - Start: a released CXR embedding model (RadDINO, or a fine-tuned CheXpert model).
  - Attacker: linear and MLP probes, plus a fine-tuning attack with a small budget, on held-out data.
  - F: adversarial training / gradient reversal.
  - Primary metric: attribute probe AUROC (lower is better, at chance) vs. diagnostic AUROC (retain), plotted as a Pareto frontier.
- **Data.** MIMIC-CXR / CheXpert with demographics, and EMBED.
- **Clean comparison.** The attacker gets a fixed budget and runs blind to the arm. Report both linear and nonlinear recoverability.

#### S29. Memorization and PHI removal in report generators
- **Problem.** Report-generation models trained on real reports can memorize names, dates, and rare-case details. A PHI incident requires removing specific memorized strings.
- **Why WSP.** It is the textbook knowledge-editing / unlearning setting for language models (MEMIT-style localization, neuron ablation) (H6). It is also a null-leaning test, because LM unlearning via editing is known to be leaky.
- **Design.**
  - Fine-tune a radiology VLM (e.g., LLaVA-Med or a small MAIRA-like model) on MIMIC-CXR reports with inserted *canary* PHI strings at controlled frequencies.
  - Request removal of a subset of canaries.
  - Primary metric: canary extraction rate (greedy and sampled, plus prompt attacks). Guardrail: RadGraph-F1 / GREEN on the test set. Also check non-requested canaries (specificity).
- **Clean comparison.** Synthetic canaries give ground truth. Never use real PHI.

---

### Theme H — Subgroup performance gaps

#### S30. Adult → pediatric transfer
- **Problem.** Most models are trained on adults. Pediatric anatomy (growth plates, thymus, proportions) causes failures, and pediatric data is scarce. This matches the pilot's motivation.
- **Why WSP.** Pediatric-specific structures can be explicitly modeled: e.g., a growth-plate detector that suppresses fracture activation along physes, or rewiring thymus features. Knowledge injection under label scarcity (H1).
- **Design.**
  - Adult fracture model (MURA, adult wrist datasets) → GRAZPEDWRI-DX (20k pediatric wrist radiographs with boxes).
  - Alternatively, adult CXR → VinDr-PCXR / the Guangzhou pediatric pneumonia dataset (beware this dataset's known quirks; pre-audit).
  - k ∈ {10, 50, 200} pediatric patients.
  - Primary metric: pediatric AUROC (with age-binned results), and adult retention.
- **Clean comparison.** Age-stratified test sets. Dedupe multiple radiographs per patient (GRAZPEDWRI has many per patient). This is a pilot lesson.

#### S31. Acquisition-subgroup gaps (portable AP vs. PA, supine vs. erect, device class)
- **Problem.** ICU portable films perform worse. Practitioners want to raise the worst subgroup without hurting others.
- **Why WSP.** Subgroup-specific failure may be localized, e.g., magnified heart on AP views affecting cardiomegaly features. An edit could condition a correction on a view-probe direction (H2). Framed as raising worst-group performance under acquisition variation.
- **Design.**
  - Data: MIMIC-CXR / CheXpert with ViewPosition metadata.
  - Primary metric: worst-subgroup AUROC. Guardrails: other subgroups and overall.
  - F: GroupDRO, reweighting, subgroup fine-tuning.
- **Clean comparison.** The subgroup labels available to each arm are identical (from metadata). Report per-finding results because label prevalence differs by view.

---

### Theme I — Compression for edge deployment

#### S32. Interpretability-guided pruning and compression, including robustness after compression
- **Problem.** Portable X-ray units, handheld ultrasound, and on-prem CPUs need small models. Pruning often disproportionately hurts minority sites, subgroups, and rare classes.
- **Why WSP.** If the agent knows *which* heads and neurons matter for the task, especially for OOD sites and rare findings, it can prune selectively (H2, H6). The comparator is magnitude/movement pruning plus distillation.
- **Design.**
  - Start: ViT-B CXR or ultrasound model.
  - Targets: 50%/75%/90% FLOP reduction or a fixed latency on a reference CPU.
  - F: structured magnitude pruning, distillation to a small model, quantization.
  - G: F plus interpretability-guided pruning, merging of redundant heads, and edits to restore critical circuits.
  - Primary metric: **external-site** and **rare-class** AUROC at matched latency. In-distribution AUROC is secondary.
- **Clean comparison.** Matched latency measured on the same hardware. Equal distillation data.

---

### Theme J — Segmentation and detection specifics

#### S33. Annotation-protocol (label-definition) shift in segmentation
- **Problem.** Sites define structures differently: prostate with or without seminal vesicles, liver with or without IVC/portal vein, tumor core vs. whole tumor, lesion boundary conventions. A model must match a new site's convention.
- **Why WSP.** Convention differences are systematic and local, e.g., "include structure Y in label X." A decoder edit that adds a learned sub-structure's logit to the parent class could implement the convention exactly with ~0 labels (H5, H2).
- **Design.**
  - Data: TotalSegmentator sub-structures, BraTS sub-regions (ET/TC/WT relabeling), multi-site liver datasets with documented convention differences.
  - Simulate new conventions by deterministic relabeling rules applied to the test set. The agent gets k ∈ {1, 3} examples and a textual description.
  - Primary metric: Dice under the new convention, while the old convention stays available (switchable).
- **Clean comparison.** The rule must be expressible from existing model outputs. Run two variants: one where a sub-structure already exists in the model and one where it doesn't (harder).

#### S34. Detection under site shift: FROC with error-class patching — **null-leaning**
- **Problem.** Nodule and lesion detectors produce site-specific false positives (vascular branch points at sites with thinner slices, nipple shadows on CXR) when moved.
- **Why WSP / null.** Tests whether score-head edits that suppress a specific FP pattern beat hard-negative mining. Expected to be close.
- **Design.**
  - Data: LUNA16 → LNDb / NLST subsets, or the VinDr-CXR detection track across subsets.
  - Primary metric: CPM / FROC sensitivity at 1 and 4 FP/scan on the target.
- **Clean comparison.** The same set of FP examples is available to both arms (as hard negatives for F, as concept examples for G).

---

### Theme K — Report generation, VLMs, and radiology text

#### S35. Report generator cross-site style and content adaptation
- **Problem.** A generator trained on MIMIC writes in Boston style and with Boston priors. A new site wants its own templates, terminology, and finding priors with few example reports.
- **Why WSP.** Style can sit in identifiable directions or heads. A steering-vector bake might shift style with minimal effect on clinical content, while fine-tuning on 50 reports may degrade factuality (H2).
- **Design.**
  - Start: a MIMIC-trained generator (MAIRA-2 class, CheXagent, or a smaller open model).
  - Targets: IU-Xray (OpenI), CheXpert Plus (different institution), PadChest-GR / ReXGradient (multi-site).
  - k ∈ {20, 100, 500} target report–image pairs.
  - Primary metric: clinical factuality (GREEN, RadGraph-F1, CheXbert-F1 on findings) plus style match (target-style classifier score, BLEU vs. target templates).
  - **WSP helps if** it gets equal style match with higher factual retention.
- **Clean comparison.** Use the same decoding settings and the same metric implementations. Assess factual quality with an LLM judge plus a radiologist subsample.

#### S36. Hallucinated prior-comparison removal in report generation
- **Problem.** Generators trained on real reports hallucinate references to prior studies ("unchanged from prior", "interval improvement") when no prior is given. This is a well-documented safety issue.
- **Why WSP.** The behavior is a coherent, likely localized concept, so ablation or projection of a "comparison" direction is a natural edit (H6, H2). F's alternatives: rewriting training reports to remove priors (as in published work) and fine-tuning, DPO against hallucinated priors, or constrained decoding.
- **Design.**
  - Start: a MIMIC-CXR-trained generator.
  - Primary metric: rate of hallucinated-prior phrases on studies without priors (pattern-based plus LLM-judge). Guardrail: GREEN / RadGraph-F1, and correct use of priors when they *are* provided (if the model supports priors).
- **Clean comparison.** Fixed compute. F's report-rewriting pipeline is permitted, so the comparison is fair.

#### S37. Laterality and negation error correction
- **Problem.** Left/right swaps and negation errors in generated reports or impressions are high-severity and medicolegal.
- **Why WSP.** Laterality may be represented as a clean direction tied to image geometry. Edits could enforce consistency (H2). This is a strong mechanistic test of whether edits fix a *specific factual dimension* without collateral damage.
- **Design.**
  - Image-flip pairs give ground-truth counterfactuals: flipping the image should flip the laterality of every mentioned finding. Use MIMIC-CXR plus VinDr boxes for laterality truth.
  - Primary metric: laterality accuracy and flip-consistency. Guardrail: overall factuality.
- **Clean comparison.** Watch for text markers (e.g., the "L" marker on the film). Both arms get the same flip-augmentation option.

#### S38. Cross-institution radiology-report label extractor / NLP model
- **Problem.** Report labelers (CheXbert, an LLM extractor, or a BERT classifier for incidental findings) degrade at new institutions because of different templates, hedging language ("cannot exclude"), and languages.
- **Why WSP.** Hedging and negation handling might be fixable with targeted edits (e.g., rank-1 edits mapping site-specific hedging phrases to the "uncertain" representation) with fewer labeled reports. It also tests WSP on text-only models, which are cheap to experiment with (H1, H7).
- **Design.**
  - Start: CheXbert, or a small LLM fine-tuned on MIMIC labels.
  - Targets: CheXpert reports (CheXpert Plus), PadChest (Spanish, or translated), institution-specific report sets with expert labels.
  - k ∈ {20, 100} labeled target reports.
  - Primary metric: macro-F1 over findings, including the uncertain class.
- **Clean comparison.** Fixed label schema and adjudicated target labels.

---

### Theme L — Merging (federated-like) and composition

#### S39. Multi-site model merging without data sharing
- **Problem.** Hospitals each fine-tune a shared FM locally but cannot pool data. A consortium wants one model that works everywhere, including unseen sites.
- **Why WSP.** Weight arithmetic is the core tool. *Interpretability-guided* merging (aligning neurons, choosing per-head sources, resolving conflicting directions) might beat plain task arithmetic, TIES, or Fisher merging (H4).
- **Design.**
  - Start: 4–6 site-specific fine-tunes from the same FM: CXR sites, or the FeTS brain tumor data (real federated partitions), or M&Ms vendors.
  - Arms get only the weights plus a tiny public calibration set (e.g., 100 unlabeled images, or 50 labeled from a public source).
  - F: training-based merge (distill an ensemble of the site models into one student on the public set; FedAvg-style averaging plus calibration-set fine-tuning).
  - G: F plus interpretability-guided merging.
  - Primary metric: mean and worst-site performance over contributing sites plus an unseen site.
  - Variant: multi-*task* merging (classification + segmentation, or CXR + MSK models) into one backbone.
- **Clean comparison.** Plain arithmetic merging counts as a mechanical baseline (principle 6) available to both arms, *or* define it as WSP and give F only distillation. **Decide this explicitly**, because it determines what "WSP" means here.

---

### Theme M — Robustness to acquisition artifacts

#### S40. Low-dose / noisy CT and other acquisition artifacts (motion, contrast phase, exposure)
- **Problem.** Low-dose screening CT, MRI motion, arterial vs. portal-venous phase, and under- or over-exposed portable CXR. Models trained on clean, standard acquisitions degrade.
- **Why WSP.** Noise and motion sensitivity can be localized in specific high-frequency or edge channels. Contrast-phase differences change the enhancement of specific organs, which could be handled with an intensity-conditional edit (H1, H5).
- **Design.**
  - Sub-variants, each with a source model on standard acquisitions:
    - **(a) Dose:** Mayo LDCT Grand Challenge (paired full/quarter dose), and LIDC with simulated dose reduction. Task: nodule or organ segmentation.
    - **(b) Motion:** MR-ART (paired motion/no-motion brain MRI), plus TorchIO simulation. Task: brain segmentation or volumetrics.
    - **(c) Contrast phase:** multiphase liver CT (LiTS-like, KiTS phases where available, or a multiphase HCC dataset). Task: liver/lesion segmentation.
  - F: artifact augmentation (strong competitor), denoising preprocessing (disallowed if the pipeline is frozen), fine-tuning.
  - G: F plus edits.
  - Primary metric: performance on the artifact condition, and paired consistency vs. the clean scan.
- **Clean comparison.** Prefer paired real data over simulation. Report a dose or motion-severity curve, not a single point.

---

### Theme N — OOD detection and selective prediction

#### S41. Built-in OOD gatekeeper and selective prediction under shift
- **Problem.** Deployed models receive wrong body parts, wrong modality, pediatric patients, post-surgical anatomy, and images with lines or tubes. They should abstain or flag rather than silently predict. Practitioners currently bolt on separate OOD detectors.
- **Why WSP.** Internal probe or SAE features that fire on "unfamiliar" inputs can be wired into an abstention head inside the model. This builds on the model's own representation with no separate training data for the OOD classes (H1).
- **Design.**
  - Start: a CXR model.
  - Near-OOD: pediatric CXR, portable with heavy devices, different sites.
  - Far-OOD: abdominal X-rays, CT scouts, MSK, natural images.
  - F: energy / MSP / Mahalanobis scores, outlier exposure.
  - G: F plus an edited-in abstention circuit.
  - Primary metric: OOD AUROC (near and far, separately), plus AURC and selective risk at 90% coverage on the shifted target site (selective prediction).
- **Clean comparison.** OOD test classes are unseen by both arms. Equal access to any outlier-exposure data.

---

### Theme O — Other practitioner situations

#### S42. Supply-chain trojan/backdoor removal in downloaded foundation models
- **Problem.** Practitioners download FMs and checkpoints from public hubs. A backdoored model (trigger: a small marker or watermark pattern) could flip predictions. This is an under-discussed but real security risk for medical AI.
- **Why WSP.** Trigger circuits are often localized. Neural-cleanse / fine-pruning-style detection plus surgical ablation is a weight-editing problem (H6).
- **Design.**
  - We plant backdoors of varying stealth in a CXR or CT classifier. Agents get the model and clean data, not the trigger.
  - Primary metric: attack success rate after the fix vs. clean AUROC. Secondary: detection (did they find the trigger?).
- **Clean comparison.** Several backdoor types. Some models contain no backdoor (false-alarm control).

#### S43. Label-taxonomy harmonization across datasets
- **Problem.** NIH, CheXpert, PadChest, and VinDr define findings differently ("consolidation" vs. "pneumonia" vs. "infiltration"). A practitioner combining or deploying across datasets needs the target taxonomy.
- **Why WSP.** Rewiring output heads as linear combinations of existing concept units, guided by probes, may map taxonomies with few labels. This is a label-shift analogue to S33.
- **Design.** A model trained on CheXpert's taxonomy, deployed on VinDr's or PadChest's. k ∈ {0, 20, 100} per new label. Primary metric: macro-AUROC under the target taxonomy.
- **Clean comparison.** Use adjudicated targets. Separate concept mismatch from image shift by also evaluating on source images relabeled to the target taxonomy, where possible.

#### S44. Adding multi-view or prior-comparison capability via circuit insertion
- **Problem.** Single-image models ignore the lateral view, CC+MLO mammography pairs, or prior studies. Radiologists rely on them.
- **Why WSP.** A hand-wired "difference" or "view-fusion" circuit (e.g., subtracting aligned prior embeddings) could add a capability that would otherwise need paired training data (H4, H5).
- **Design.**
  - Interval change detection on MIMIC-CXR sequential pairs (labels from report comparisons: worsened/improved/stable), or mammography bilateral asymmetry.
  - Primary metric: AUROC of change classification at low k.
- **Clean comparison.** Equal access to paired data. Register image pairs identically.

> Count note: 44 settings are listed; S41–S44 can be dropped or merged to reach the 25–40 target. The core 40 are S1–S40.

---

## 3. Ranking: the 10 most informative settings for practitioners

Criteria: (i) how often practitioners face it, (ii) plausibility that WSP has a real mechanism to win, (iii) clean measurement (paired data, big sealed tests, low confound risk), (iv) whether the result changes practice either way, (v) fit with the investigator's preferences (shift, domain gap).

| Rank | Setting | Why it ranks here |
|---|---|---|
| 1 | **S1 CXR cross-institution transfer (R0–R2)** | The highest-frequency practitioner problem. Large public multi-site data. Directly tests H1. The result generalizes as "should I edit or fine-tune when moving sites?" |
| 2 | **S14 DINOv3 → CXR gap closing (vs. RadDINO)** | The investigator's preferred domain-gap setting. A domain FM gives a natural upper bound and a target representation, so "% gap closed" is easy to interpret. |
| 3 | **S2/S5 multi-vendor MRI / CT kernel shift (paired)** | Segmentation plus vendor or reconstruction shift with paired or traveling-subject data. This is the cleanest causal design for shift, and a mechanistic story exists (stem/normalization). Pick S5 if paired-kernel data is obtainable, otherwise S2. |
| 4 | **S9 Temporal drift hotfix (low churn)** | Matches the "maintain the model" phase. Evaluated on churn and locality, where WSP's theoretical advantage (H2) is strongest even if the AUROC difference is small. |
| 5 | **S11 PCCP / locked-model change control** | The most regulatory-relevant setting. The parameter-diff budget makes the comparison fair, and reviewer-rated auditability is an outcome only WSP can plausibly win. Can sit on top of S1/S9 at little extra cost. |
| 6 | **S24 Adding a new finding without forgetting** | A common product request with a measurable trade-off (new-class gain vs. old-class churn). The no-replay variant is realistic and favors locality-based approaches. |
| 7 | **S18 CT → MRI segmentation** | Modality transfer where the shape-prior/appearance split gives WSP a concrete mechanistic hypothesis. Large label-cost savings if it works. |
| 8 | **S39 Multi-site merging** | Federated-like consortia are common. Merging is inherently weight-space, and the question is whether *interpretability* improves on mechanical merging. Must define the F/G boundary carefully. |
| 9 | **S27 Site/cohort unlearning** | A real governance pain (DUA expiry, consent withdrawal) with a principled gold standard (retrain-without-X). Ablation is a natural fit. Few practitioners have good tools today. |
| 10 | **S36 Hallucinated-prior removal in report generation** | Brings in the fast-growing VLM/report-generation workflow. A coherent, measurable behavior with a known non-WSP fix to compare against. High practitioner relevance. |

**Honorable mentions:**
- **S12** (input-pipeline positive control). Run it first as a *tool-validation* gate: if G can't win here, the WSP tooling is inadequate.
- **S13** (prevalence recalibration). A mandatory *null control*.
- **S22** (rare finding with knowledge injection). Directly continues the pilot's lesson, but only if both arms have the same knowledge source.
- **S28** (attribute capability removal).
- **S32** (compression with OOD robustness).

### Suggested study portfolio (if only ~6 can be run)
1. **S12 tool-validation gate.**
2. **S1** (shift, classification), with the **S11** diff-budget overlay.
3. **S14** (domain gap).
4. **S2 or S5** (shift, segmentation, paired).
5. **S9 or S24** (maintenance/continual; churn-focused).
6. **S13** (null control).

This portfolio covers shift, domain gap, segmentation, maintenance, regulatory, and a null, across ≥2 modalities.

---

## 4. Known risks and threats to validity (whole study)

- **Agent skill confound.** G may win or lose because of the agent's interpretability skill, not WSP's inherent value. Mitigations: mechanical WSP baselines, multiple agent models, and logging agent trajectories.
- **"G trains more" confound.** If G's edits are later fine-tuned over, the edits may be irrelevant. The edit-reversion ablation and the E arm handle this.
- **Edit-as-regularizer.** Random-direction edits of the same norm may help just as much. The random-edit control handles this.
- **Benchmark contamination.** Agents may know published results on public datasets (e.g., the M&Ms leaderboard). Prefer sealed or relabeled test sets and fresh splits.
- **Effect sizes vs. noise.** The pilot's ≤0.02 effect means many settings will be underpowered unless tests are large. Do a power analysis per setting before committing.
- **Over-fitting to the dev pool.** k-shot dev pools are tiny. Agents may tune heavily to them. Cap the number of dev evaluations, or score dev under an exposure budget.
- **Practitioner realism.** Some G wins (e.g., S12) are things practitioners would solve another way. Report a "would a practitioner actually do this" note per setting.
- **Definition of WSP vs. standard practice.** BN-stat re-estimation, temperature scaling, positional-embedding interpolation, and task arithmetic are already standard weight edits. Decide per setting whether they belong to F, G, or the shared mechanical baseline, and pre-register that.
