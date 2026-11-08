# Research: Post-June-2026 public radiology datasets for a WSP study

Date of research: 2026-11-08.
Use case: Claude Opus 5.5 edits image-model weights (WSP) at several
label budgets.
Target journal: Radiology: Artificial Intelligence.

## Summary

The RSNA 2026 knee challenge ended on 2026-10-22.
It has exactly 58 expert-labelled training studies, but the top teams
used frontier-LLM agents to label the other 4,349 studies.
Its RSNA MIRA licence does not clearly allow sending images to a
commercial LLM API, so use it only after written RSNA permission.
The cleanest pilot is MFXR (CC BY 4.0, public 2026-07-18), then Garden
(open since 2026-09-17), then LIDC-annot-NLST501 for detection and
segmentation.

## Findings

1. **Claim:** The knee challenge is "RSNA Knee Abnormality Detection"
   on Kaggle.
   It launched 2026-08-05 and the final submission deadline was
   2026-10-22.
   It is study-level multilabel classification of 12 findings on knee
   MRI, scored by macro ROC-AUC.
   **Sources:** [rsna-press], [rsna-page], [repo-comp], [aicomp].
   **Support:** direct for launch and description (RSNA pages).
   The deadline table is from a team's notes and aicompetition.dev.
   **Confidence:** high.

2. **Claim:** Training has 4,407 studies, 24,371 series and 819,078
   DICOM files.
   Only 58 studies have expert labels for all 12 findings.
   The other 4,349 have only a multilingual free-text report.
   The hidden test set (about 1,322 studies) has no reports or labels.
   **Sources:** [repo-comp], [arxiv-knee], [kg-1st], [rsna-7th].
   **Support:** direct (several independent write-ups agree).
   **Confidence:** high.

3. **Claim:** The 58 gold labels were set from the images by two
   musculoskeletal radiologists plus an adjudicator.
   Positives per finding on the 58 range from 9 to 35.
   The hidden test set was also graded by experts from the images.
   **Sources:** [arxiv-knee], [rsna-2nd], [repo-comp].
   **Support:** direct for counts; the host statement is second-hand.
   **Confidence:** medium-high.

4. **Claim:** Final private leaderboard: 1st Team Kangaroo 0.960
   (public 0.969).
   2nd 0.960, 3rd 0.959, 5th and 6th 0.958, 7th, 8th and 10th 0.957.
   The public-board leader (Barry) fell from 0.970 to 0.957 and
   finished 7th.
   1,297 teams scored exactly 0.942, the score of widely copied public
   notebooks.
   **Sources:** [arxiv-knee], [pilkwang5], [rsna-clist].
   **Support:** direct (third-party tables).
   The Kaggle leaderboard page itself could not be read.
   **Confidence:** medium-high.

5. **Claim:** Late submissions are scored after the deadline with
   public and private scores, but are not on the official leaderboard.
   Test labels are not released.
   **Sources:** [kg-late], [arxiv-knee].
   **Support:** direct from two participants' own reports.
   **Confidence:** medium (the Kaggle rules page was not readable).

6. **Claim:** Top solutions used frontier-LLM agents to label the 4,349
   unlabelled training studies, from reports and from images.
   The 1st-place team used Codex, Claude and pi CLI agents to produce
   probabilities, ROI boxes and slice boxes.
   They tuned protocols on the 58 gold studies (label AUC 0.93 to
   0.94 on gold).
   The 2nd-place team raised gold-set label AUC from 0.899 (report
   only) to 0.942 by letting a vision LLM read all slices.
   **Sources:** [rsna-1st], [rsna-2nd], [rsna-7th], [arxiv-knee].
   **Support:** direct (winner write-ups).
   **Confidence:** high.

7. **Claim:** The winners' effective supervision was 58 expert labels
   plus about 4,349 LLM-generated soft labels.
   Several top-10 teams added pseudo-labels from OAI or fastMRI knees.
   **Sources:** [arxiv-knee] (Table 9), [rsna-6th], [kg-1st-labels].
   **Support:** interpretation of the write-ups (researcher synthesis).
   **Confidence:** medium-high.

8. **Claim:** Several winners released code, weights or labels.
   6th place: code and weights (CC BY-NC 4.0) on Kaggle.
   3rd place: weights on Kaggle.
   1st and 7th place: LLM-derived training labels on Kaggle.
   The NTejas-1 GitHub repository (MIT) holds Claude Opus 4.5 report
   labels for all 4,407 reports.
   **Sources:** [kg-6th], [kg-3rd], [kg-1st-labels], [kg-7th-labels],
   [ntejas].
   **Support:** direct.
   **Confidence:** high.

9. **Claim:** The knee data are under the RSNA MIRA Dataset Research
   Use Agreement (version 2.0, 2025-11-05).
   It allows research use only.
   It forbids distributing or reproducing a copy to others.
   It forbids creating derivative works.
   It does not mention LLM APIs.
   **Sources:** [mira], [aicomp], [kg-6th].
   **Support:** direct for the MIRA text.
   That the knee data fall under it comes from the 6th-place licence
   file and aicompetition.dev.
   **Confidence:** medium.

10. **Claim:** During the competition the host reportedly allowed
    commercial LLM APIs to read reports and derive labels.
    Top teams also sent images to GPT-6 models.
    Whether this continues after the competition is not documented.
    **Sources:** [repo-comp] (quotes forum topic 733965), [rsna-2nd],
    [rsna-7th].
    **Support:** direct but second-hand (forum page not readable).
    **Confidence:** low-medium.

11. **Claim:** PhysioNet credentialed data (MIMIC-CXR and derivatives)
    must not be sent through external APIs.
    Cloud services are tolerated only with verified zero retention,
    no training on the data and no human review.
    **Sources:** [physionet-llm].
    **Support:** direct.
    **Confidence:** high.

12. **Claim:** The DrivenData DaT scan challenge forbids sending its
    data to any third-party API, including ChatGPT and Gemini.
    **Sources:** [dat-rules].
    **Support:** direct.
    **Confidence:** high.

13. **Claim:** Two leads have an earlier public date than the brief.
    Garden: Zenodo record v1 is dated 2026-03-11 but its files were
    restricted.
    Open files appeared on 2026-09-17 and the Sci Data paper is dated
    2026-10-08.
    PatchChestCT: Zenodo 2026-04-23, before the cutoff.
    **Sources:** [garden-z1], [garden-z2], [garden-sd], [patchct-z].
    **Support:** direct (Zenodo API records).
    **Confidence:** high.

14. **Claim:** MFXR qualifies on date: Figshare shows publication on
    2026-07-18 under CC BY 4.0.
    The Sci Data paper is dated 2026-07-07.
    **Sources:** [figshare-api], [sd-mfxr].
    **Support:** direct.
    **Confidence:** medium-high (see Contradictions).

## Contradictions

- Number of sites: the RSNA challenge page says 19 sites.
  The RSNA press release says 16 sites.
  Sources: [rsna-page], [rsna-press].
- Number of teams: 6,425 (Pilkwang blog) versus 6,299 (arXiv
  2610.40708).
  Sources: [pilkwang5], [arxiv-knee].
- Knee licence wording: the rules reportedly name CC BY-NC 4.0 for
  winners but also contain conflicting commercial-use text.
  Source: [aicomp].
- MFXR: the Sci Data paper (2026-07-07) says the data are public.
  Figshare lists publication on 2026-07-18.
  The Figshare record number suggests it was created in about October
  2025.
  Sources: [sd-mfxr], [figshare-api].
- Garden: the paper reports kappa 0.82 between annotators.
  The Zenodo text reports kappa 0.95 for the final label.
  The metadata file lists 13,751 annotated images, but the title
  figure is 19,940 images.
  Sources: [garden-sd], [garden-z2].
- Naija-CXR: the Zenodo licence field is CC BY 4.0.
  The description says non-commercial research and education only.
  Source: [naija].

## Missing evidence

- The Kaggle rules, data and discussion pages are JavaScript-only and
  could not be read.
  The exact knee rule wording on third-party APIs is unverified.
- Whether RSNA will deposit the knee data in MIRA, and when, is unknown.
- Whether Kaggle late submissions stay open indefinitely is unknown.
- No confidence intervals exist for the knee leaderboard.
- MFXR baseline AUCs (Tables 2 and 3) were not extracted.
- The licence of LIDC-annot-NLST501 and of the NLST images was not
  found in the page text.
- The PDAC-TAGS licence was not readable (OSF is JavaScript-only).
- TAIX-Ray date and licence, and BraTS, autoPET V and HECKTOR
  licences, were not checked.
- Whether Anthropic API terms (retention, human review) meet any
  dataset agreement was not assessed.

## Priority item: RSNA knee challenge

### Facts

- **Name and URLs:** RSNA Knee Abnormality Detection AI Challenge
  (2026); [rsna-kaggle] and [rsna-page].
- **Dates:** launch 2026-08-05.
  Entry and team-merger deadline 2026-10-15.
  Final submission 2026-10-22 23:59 UTC.
  Winners' materials due 2026-11-05.
  Recognition at RSNA 2026 (29 November to 3 December).
- **Format:** Kaggle code competition.
  Notebook run time at most 9 hours, internet off, 5 submissions
  per day.
  Public external data and pretrained models are allowed.
- **Task:** 12 independent probabilities per study.
  Findings: ACL, MCL, medial meniscus, lateral meniscus, medial OA,
  lateral OA, patellofemoral OA, effusion, synovitis, Baker's cyst,
  contusion, fracture.
- **Metric:** mean of the 12 per-finding ROC-AUC values.
  A second track ranks AUC plus runtime (USD 18,000).
  Total prize pool USD 77,000.
- **Training data:** 4,407 studies, 24,371 series, about 570 GB of
  DICOM (570 GB is from a secondary catalogue).
  58 gold studies, 4,349 report-only studies.
  Reports are in at least nine languages.
- **Test data:** about 1,322 hidden studies, images only,
  expert-graded.
  The private part is about 70% of the test set.
  Prevalence may differ between train, public and private sets.
- **Gold prevalence (58 studies):** ACL 24, MCL 9, medial meniscus 26,
  lateral meniscus 23, medial OA 15, lateral OA 11, PF OA 21,
  effusion 35, synovitis 27, Baker's cyst 12, contusion 19,
  fracture 18.
- **Patient-level splits:** not guaranteed.
  No patient identifier is released, so one patient could appear in
  two studies in different folds.
- **Scores:** see Finding 4.
  Ranks 4 and 9 were not tabulated in any source I could read.

### What the winners did

- **1st (Team Kangaroo):** LLM agents produced per-finding
  probabilities, ROI boxes and per-slice lesion boxes for all
  training studies.
  A "trained guide" was learned from the 58 gold studies.
  Models: ConvNeXt-T at 384 px, MambaOut-B+, MaxViT-V2-B and
  6-channel variants.
  Efficiency entry: one ConvNeXt-T, public 0.964, private 0.954,
  about 4 minutes.
- **2nd:** GPT-6.1 Sol read reports; GPT-6 Astra read all slices with
  the report.
  Gold-set label AUC rose from 0.899 to 0.942.
  Effusion rose from 0.806 to 0.975.
  Six 2.5D MIL models, rank blend, fastMRI pretraining for two members.
- **6th:** report labels plus image models trained on OAI grades,
  keypoint localiser and 3-slice tile bags.
  Code and weights released.
- **7th:** GPT-6 Astra labels from reports plus images, with no
  external training data.
- **Pattern:** seven of the eight published top-10 solutions had an
  LLM read the training images.
  None isolates the effect of that choice.
- **Single-model reference:** a 2.5D ResNet50 on report-only labels
  scored 0.877 private.
  The same model on a mixed target scored 0.872.
  So most of the gap to 0.960 came from other factors (ensembles,
  stronger labels, resolution), not report-label quality alone.
  This is an inference from one entry.

### Suitability for this study

- **Relevance:** high.
  It has an expert hidden test, 12 labels, a tiny gold set, a large
  unlabelled pool and a precedent for LLMs as label producers.
- **Label budgets:** 0, 10, 20, 50 and 58 fit inside the gold set.
  Budgets of 100, 250 or "all" are impossible with expert image
  labels.
  Larger budgets would need report-derived or LLM-derived labels,
  which are a different kind of label.
- **Confound:** report-derived labels for 4,349 studies are free and
  public.
  Any label-saving claim must state whether they count as labels.
- **Evaluation:** the gold set is too small for stable validation
  (AUC standard error about 0.04 to 0.08 per finding).
  The hidden test is reachable only through late submission of a
  Kaggle notebook with no internet.
  WSP-edited weights can be made offline and uploaded, so this is
  feasible.
  Repeated late submissions leak test information, so cap them in
  advance.
- **Beating the top score (0.960):** not a sound primary goal.
  The top ten private scores span 0.003, and no confidence intervals
  exist.
  Winners used thousands of LLM-made labels, ensembles and nine-hour
  inference.
  A WSP head trained on at most 58 expert labels is a different
  comparison.
  A fair claim compares against baselines with the same inputs and
  budget.
- **Licence and API:** see Findings 9 and 10.
  Treat as unclear and ask RSNA for written permission
  (informatics@rsna.org).
  Frozen-encoder activations might count as derived data under MIRA
  clause 6.
- **Suitability: 3 of 5.**
  Strong scientifically, but limited by a licence question and the
  label-count confound.
  Use it as a secondary or confirmatory dataset.

## Summary table

Cls = classification, Det = detection, Seg = segmentation.
API = whether sending images or activations to a commercial LLM API
is permitted by the licence text.
Suit. = suitability from 1 to 5.

| ID | Dataset | Task | First public | API | Suit. |
|---|---|---|---|---|---|
| D1 | MFXR forearm X-ray | Cls | 2026-07-18 | Allowed | 4 |
| D2 | Garden femoral neck | Cls | 2026-09-17 | Allowed | 4 |
| D3 | LIDC-annot-NLST501 | Det/Seg | 2026-08-05 | Unclear | 4 |
| D4 | TotalSeg MRI v3 | Seg | 2026-09-10 | Allowed | 3 |
| D5 | RSNA knee MRI | Cls | 2026-08-05 | Unclear | 3 |
| D6 | TopAneu 2026 | Cls/Det/Seg | 2026-06-15 | Unclear | 3 |
| D7 | TopBrain v2 (TA36) | Seg | 2026-08-17 | Unclear | 3 |
| D8 | PDAC-TAGS | Seg | by 2026-06-29 | Unclear | 3 |
| D9 | TotalSeg CT v3 | Seg | 2026-09-10 | Allowed | 3 |
| D10 | XQA-Chest | Cls | 2026-08-26 | Unclear | 2 |
| D11 | Naija-CXR | Cls | 2026-08-04 | Unclear | 2 |
| D12 | CheXmask-U | Seg (AI) | 2026-09-02 | Mixed | 1 |
| D13 | NLST DICOM annots | Seg | 2026-09 | Unclear | 2 |
| D14 | PatchChestCT | Det | 2026-04-23 | Mixed | 2 |
| D15 | SPARC-Rad | VQA | 2026-07-30 | Unclear | 1 |
| D16 | 3D oncology VQA | VQA | none | n/a | 1 |
| D17 | MultiCaRe-Thorax | Cls | 2026-06-05 | Allowed | 1 |
| D18 | DaT scan (DrivenData) | Cls | 2026 | Forbidden | 1 |

"Allowed" means the licence text has no clause against it.
This is my reading, not legal advice, and ethics-board terms may
still apply.

## Dataset sections

### D1. MFXR (Monteggia fracture X-rays)

- **URLs:** data [figshare-mfxr]; paper [sd-mfxr]; code [mfxr-code].
- **First public:** 2026-07-18 (Figshare API publication date).
  The paper was published 2026-07-07 (received 2025-10-12).
  Images date from 2013 to 2024; the labels are new.
- **Modality and body part:** paediatric forearm radiographs from one
  hospital (Shenzhen Children's Hospital), ages 0 to 14.
- **Task and label:** binary, Monteggia fracture versus control.
  Controls include normal forearms and other fractures.
  A paediatric orthopaedist labelled from the radiograph, then
  reconciled with clinical records; a second surgeon verified.
  Label source: expert, image-based plus clinical record.
- **Size:** 4,586 images, 1,482 patients, 2,793 fracture images and
  1,793 control images.
- **Splits:** patient-level 2:1 train and test.
  Train 2,993 images (1,794 fracture).
  Test 1,593 images (999 fracture, about 63%).
  No hidden test; test labels are public.
- **Best published score:** eight baselines (ResNet, ViT, CLIP) at
  256 and 518 px are in Tables 2 and 3; values not extracted.
- **Licence:** CC BY 4.0 (Figshare API).
  API use: allowed by the licence; hospital ethics terms not checked.
- **Access:** open, no registration.
- **Disk:** about 413 MB.
- **Suitability: 4.**
  Clean licence, tiny, post-June, expert labels, patient-level split.
  Weaknesses: binary task, one hospital, no leaderboard.

### D2. Garden classification of femoral neck fractures

- **URLs:** open data [garden-z2]; first record [garden-z1]; paper
  [garden-sd].
- **First public:** open files 2026-09-17 (Zenodo latest version).
  The first record (2026-03-11) had restricted files, but its text,
  with class percentages, was public in March.
  Sci Data paper 2026-10-08 (received 2026-03-18).
- **Modality and body part:** hip CT, converted to 224 x 224 axial,
  coronal and 3D MIP views, with and without fixator removal.
  Hospitals in Chongqing.
- **Task and label:** four-class Garden type I to IV.
  Two orthopaedic surgeons read independently; a chief surgeon
  resolved disagreements.
  Label source: expert, image-based.
- **Size:** 1,579 patients; 19,940 images in the abstract.
  The metadata file lists 13,751 annotated images.
  Class mix about 15%, 26%, 28% and 30%.
- **Splits:** patient-level 7:1.5:1.5; test labels public; no
  leaderboard.
- **Best published score:** AUC above 0.96 on the coronal
  occlusion-removed subset (CNN and transformer models).
- **Licence:** CC BY 4.0 for the data; the article is CC BY-NC-ND.
  API use: allowed by the data licence.
- **Access:** open on Zenodo.
- **Disk:** 4.28 GB (`classification.zip`).
- **Suitability: 4.**
  The ordinal four-class label gives richer budget curves than a
  binary task.
  Caveats: 2D reconstructions, image-count discrepancy, one region.

### D3. LIDC-annot-NLST501 (lung nodule annotations on NLST)

- **URL:** [lidc-nlst]; companion preprint arXiv 2512.00281.
- **First public:** TCIA lists "Updated 2026/08/05".
  Whether this is the first publication is unverified.
  The annotation campaign ran December 2022 to October 2023.
  Images are old NLST scans; the labels are new.
- **Modality and body part:** chest low-dose CT.
- **Task and label:** nodule detection, segmentation and feature
  rating.
  Each of 501 cases was annotated by four independent radiologists
  drawn from 20.
  6,505 lesions were segmented and 12,968 non-target lesions reported.
  Label source: expert, image-based.
- **Size:** 501 patients (152 cancer, 349 non-cancer) with
  histology-linked outcome.
- **Splits:** no official split or hidden test found.
- **Best published score:** the preprint compares an AI system with
  radiologists; numbers not extracted.
- **Licence:** not found in the page text (unverified).
  NLST images come from the TCIA NLST collection.
  API use: unclear.
- **Access:** open through TCIA (NLST terms unverified).
- **Disk:** listed as 13.65 GB.
- **Suitability: 4.**
  Multi-reader labels allow a reader-noise study, and the task fits
  detection and segmentation.
  The images were public before the cutoff, so only labels are new.

### D4. TotalSegmentator MRI dataset v3

- **URL:** [ts-mri].
- **First public:** v3 on 2026-09-10 (Zenodo).
  Earlier versions had 298 images and then 616 images (2025-01-21).
  v3 adds 246 whole-body MR, 249 paediatric MR and 170 failure cases,
  and revises labels on existing cases.
  Images are partly old and labels partly new.
- **Modality and body part:** MRI, whole body, 50 structures.
- **Task and label:** multi-organ segmentation.
  The Zenodo page does not describe how labels were produced; check
  the paper (arXiv 2405.19492).
- **Size:** 1,296 MR images.
- **Splits:** a `meta.csv` exists; whether it has a split column is
  unverified.
- **Best published score:** not extracted.
- **Licence:** CC BY 4.0.
  API use: allowed by the licence.
- **Access:** open.
- **Disk:** 15.2 GB.
- **Suitability: 3.**
  Easy to obtain, but segmentation by weight editing is hard and
  organ segmentation is likely familiar to the model.

### D5. RSNA Knee Abnormality Detection

- See the priority section above.
- **URLs:** [rsna-kaggle], [rsna-page].
- **First public:** 2026-08-05 (launch).
- **Licence:** RSNA MIRA agreement (clauses 1, 4 and 6 matter).
  API use: unclear.
- **Access:** free Kaggle account and acceptance of competition rules.
- **Disk:** about 570 GB of DICOM ([hounsfield]).
- **Suitability: 3.**

### D6. TopAneu 2026

- **URLs:** [topaneu-home], [topaneu-data].
- **First public:** batch 1 on 2026-06-15 (98 cases); batch 2 on
  2026-07-31.
  Batch 1 is inside June, so it is borderline for a June cutoff.
- **Modality and body part:** brain CTA and MRA.
- **Task and label:** multilabel aneurysm presence over 50+ vessel
  locations, voxel segmentation and aneurysm-type masks.
  Label source: expert annotation with quality control.
- **Size:** 415 scans from 408 patients.
  68 MRA cases come from public INSTED and OpenNeuro data.
  UMC Utrecht scans are reserved for the hidden test.
- **Splits:** hidden test through Grand Challenge Docker submission.
  The final test phase ended 2026-09-21.
  Whether post-challenge submission stays open is unknown.
- **Best published score:** leaderboards exist but were not read.
- **Licence:** "Open use, cite the source, commercial use needs
  permission" (opendata.swiss terms).
  API use: unclear.
- **Access:** open download through SWITCHdrive.
- **Disk:** not stated.
- **Suitability: 3.**
  A real hidden test for detection and segmentation, but heavy 3D
  data, mixed old and new images and unclear post-challenge access.

### D7. TopBrain v2 (TA36 track)

- **URLs:** [topbrain-home], [topbrain-z].
- **First public:** TA36 labels added to the Zenodo release on
  2026-08-17.
  The images are 25 CTA and MRA pairs from TopCoW (2025), so the
  images are old.
  Veins and stenosis tasks run October to December 2026; I found no
  data release or rules for them.
- **Task and label:** 36-class cerebral artery segmentation, expert
  annotated.
- **Size:** 50 training volumes.
- **Splits:** hidden annotated test set through Docker submission.
  The TA36 phase closes one or two days after the TopAneu deadline.
- **Licence:** the same opendata.swiss open-use wording.
  API use: unclear.
- **Suitability: 3.**
  A small training set suits label-budget curves, but the images are
  old.

### D8. PDAC-TAGS (pancreatic tumour segmentation)

- **URLs:** [pdac-osf]; paper [pdac-pmc].
- **First public:** the paper cites the OSF repository as accessed
  on 2026-06-29.
  The OSF record shows 2026-08-17 and a preprint dated 2026-09-01.
  Public availability may therefore predate the cutoff.
- **Task and label:** pancreas and tumour masks on contrast CT, expert
  annotated.
- **Size:** 500 patients from four centres, CT from 2015 to 2025.
- **Splits:** five-fold cross-validation and leave-one-centre-out; no
  hidden test.
- **Best published score:** DSC 0.703 and NSD 0.835 (MSD-TAGS).
- **Licence:** not read.
  API use: unclear.
- **Suitability: 3.**
  A useful multi-centre segmentation set, but date and licence are
  uncertain.

### D9. TotalSegmentator CT dataset v3

- **URL:** [ts-ct].
- **First public:** v3 on 2026-09-10 with 1,939 CT images and 117
  structures.
  It adds 291 paediatric scans (previous version 1,228 images) and
  revises labels.
- **Licence:** CC BY 4.0; open; 37.4 GB.
- **Suitability: 3.**
  Same caveats as D4.
  Earlier versions of the CT data have been public since 2022.

### D10. XQA-Chest (Cambridge)

- **URLs:** [xqa-reshare], [xqa-readme]; paper [xqa-arxiv].
- **First public:** record published 2026-08-26 (UK Data Service).
  The paper was posted 2026-07-28.
- **Content:** 650 frontal chest X-rays with paired image-only and
  report-derived 14-label annotations and boxes.
  Also 323 reference and 1,571 degraded images with quality ratings,
  and a matched 735-study MIMIC-CXR subset.
- **Label source:** two image readers plus a senior radiologist, and
  separate report annotators.
- **Licence and access:** restricted.
  It needs the UK Data Service End User Licence, depositor permission
  and review by a hospital data access committee.
  The MIMIC-CXR part inherits PhysioNet terms.
  API use: not stated; likely refused or at best unclear.
- **Suitability: 2.**
  The label design is ideal (image-only versus report), but the set is
  small and access is gated.

### D11. Naija-CXR

- **URL:** [naija].
- **First public:** Zenodo 2026-08-04 (V1.1); the V1.0 date is
  unverified.
- **Content:** frontal chest X-rays with radiologist reports and label
  definitions.
  The number of images and positives is not stated.
- **Licence:** CC BY 4.0 in metadata; the text says non-commercial
  research only.
- **Disk:** 389 MB.
- **Suitability: 2.**
  Labels are under-documented and the size is unknown.

### D12. CheXmask-U

- **URLs:** [chexmask]; metadata [chexmask-api].
- **First public:** 2026-09-02 (PhysioNet).
- **Content:** model-generated lung and heart masks, with uncertainty,
  for 657,566 chest X-rays from five public datasets.
  The images are not included.
- **Label source:** AI (HybridGNet), not expert.
- **Licence:** CC BY 4.0, open, 42.8 GB.
  The source images (MIMIC-CXR, CheXpert and others) keep their own
  terms.
- **Suitability: 1.**
  Silver-standard labels cannot support a clean label-efficiency claim.

### D13. NLST anatomy and pathology annotations (IDC)

- **URL:** [nlst-arxiv] (posted 2026-09-09).
- **Content:** IDC NLSTSeg (581 patients) and NLSTSybil (601) repackage
  lesion annotations shared earlier in research formats.
  TotalSegmentator-CT-Segmentations covers 26,194 patients and is
  AI-generated.
- **Suitability: 2.**
  The labels are earlier or AI-made; the new part is DICOM packaging.
  Licence not checked.

### D14. PatchChestCT

- **URLs:** [patchct-z]; paper [patchct-sd].
- **First public:** Zenodo 2026-04-23, before the cutoff.
  The Sci Data paper date (2026-08-12) comes from a search summary and
  was not fetched.
- **Content:** patch-level binary labels for nine findings in 2,201
  CT-RATE studies.
- **Licence:** annotations CC BY 4.0.
  Images must come from CT-RATE under its own data agreement.
- **Suitability: 2.**
  It fails the date rule; use only as a reference.

### D15 and D16. VQA candidates

- **SPARC-Rad** ([sparc], [sparc-site]): 300 hand-written questions on
  healthy-control TCIA images, arXiv 2026-07-30.
  It tests anatomy reasoning, not label efficiency.
  The licence was not found.
  Suitability 1.
- **Contamination-controlled 3D oncology VQA** ([onc-vqa]): Research
  Square 2026-09-11, built from private radiology reports and imaging.
  No public release is described, so it cannot be used.
  Suitability 1.
- **Other VQA:** I found no public post-June VQA set that fits a
  label-budget design.

### D17. MultiCaRe-Thorax

- **URLs:** paper [multicare-paper]; data [multicare-z].
- **First public:** Zenodo 2026-06-05.
- **Problem:** images come from open-access PubMed Central case
  reports, and labels come from captions and text.
  The images were probably seen in training, and the labels are
  text-derived.
  Suitability 1.

### D18. DaT Parkinson's Challenge (DrivenData)

- **URLs:** [dat-rules], [dat-winners].
- **Content:** 3D SPECT DaT scans, normal versus abnormal, from ten
  French centres.
  Hidden test of 524 scans.
  Winning log loss 0.2532, 0.2731 and 0.2732; AUROC 0.949 to 0.959.
- **Rule:** participants may not send the data to any third-party
  service or API.
  Verdict: forbidden.
- **Watch:** the organisers say the data will later be open on
  data.gouv.
  That release may be usable under its own licence.

### Challenge data released before June 2026

These fail the date rule for training data, but hidden test sets may
be new.

- **BraTS 2026:** training data released from 2026-05-08 ([brats]).
- **PENGWIN 2026:** training sets released 2026-04-24; final results
  2026-09-02 ([pengwin]).
- **autoPET V:** opened 2026-04-01; databases re-released 2026-04-26
  ([autopet]).
- **AMPLIFAI:** gated on Hugging Face, 531 training and 59 validation
  cases, 174 private test cases ([amplifai]).
- **AIMS-TBI:** record posted around April 2026.
- **HEADLINE:** head CT report generation under a data-use agreement,
  not public.
- **ReXGroundingCT:** data from 2025, CC BY-NC-SA 4.0, gated, with a
  300-case held-out leaderboard ([rexground]).
- **Full list of MICCAI 2026 challenges:** [miccai-ch].

### Pre-cutoff datasets for unlabelled probes or external validation

- **TAIX-Ray:** 215,381 ICU chest radiographs with eight structured
  radiologist labels on Hugging Face ([taix]).
  Date and licence not checked.
- **Knee MRI:** fastMRI knee (with fastMRI+ boxes), OAI and MRNet were
  used as external data by top teams.
  Each has its own agreement; the 6th-place notice mentions the NYU
  fastMRI agreement.
  Terms were not verified here.
- **CT-RATE and NLST:** unlabelled CT sources with gated or
  collection-specific terms.
- **MIMIC-CXR and CheXpert:** do not send to an external API (see
  Finding 11).

## Ranked shortlist

1. **D1 MFXR (classification).** Recommended pilot.
   Open, CC BY 4.0, post-June, patient-level split, 413 MB.
2. **D2 Garden (classification).**
   Open, CC BY 4.0, four ordinal classes, AUC above 0.96 baseline.
3. **D3 LIDC-annot-NLST501 (detection and segmentation).**
   Four expert readers per case; verify the licence first.
4. **D4 TotalSegmentator MRI v3 (segmentation).**
   Open and moderate size; a lower-value segmentation option.
5. **D5 RSNA knee (classification).**
   Highest scientific value as an external test; needs written RSNA
   permission first.

Runner-up: D6 TopAneu (hidden test, detection and segmentation) if
the organisers confirm API use and post-challenge access.

### Recommended pilot: MFXR

- It has a verified post-June date and a CC BY 4.0 licence with no
  registration.
- It is small (about 413 MB) with a single binary label.
  A frozen-encoder head with budgets 0, 10, 20, 50, 100, 250 and all
  is cheap to run.
- It has an official patient-level train and test split.
- Labels come from the radiograph, with no report-derived confound.

Risks to check before the pilot:

- The test set is about 63% positive, so report AUC and calibration
  and consider re-weighting to a realistic prevalence.
- Patients have several images, so sample label budgets by patient.
- The control group mixes normal forearms and other fractures.
- The Figshare date differs from the paper date (see Contradictions).

## Sources

- Kept: [rsna-press] - launch date and challenge description.
- Kept: [arxiv-knee] - independent analysis, gold counts, top-10
  label methods.
- Kept: [rsna-1st], [rsna-2nd], [rsna-6th], [rsna-7th] - winner
  write-ups.
- Kept: [pilkwang5], [rsna-clist] - leaderboard evidence.
- Kept: [mira] - MIRA licence text.
- Kept: [physionet-llm] - PhysioNet rule on LLM services.
- Kept: [figshare-api], [garden-z1], [garden-z2], [ts-mri], [ts-ct],
  [naija], [chexmask-api] - primary API records for dates and licences.
- Kept: [dat-rules] - explicit ban on third-party APIs.
- Deprioritised: community Kaggle copies of processed knee volumes.
  They redistribute RSNA data under a different licence, which looks
  inconsistent with MIRA.
- Deprioritised: aggregator pages (Hounsfield Lab, aicompetition.dev),
  used only as secondary evidence.

## Next steps

1. Email RSNA (informatics@rsna.org) to ask whether sending MIRA knee
   images, or frozen-encoder activations, to a commercial API is
   permitted.
2. Read the Kaggle rules, data page and forum topic 733965 in a
   browser to confirm the API wording and the late-submission policy.
3. Confirm the licence of LIDC-annot-NLST501 and the NLST image terms
   on TCIA.
4. Ask the TopAneu organisers whether the hidden-test phase reopens
   and whether API use is covered.
5. Extract MFXR baseline AUCs from Tables 2 and 3 to set the pilot
   target.

Note on tooling: I had no shell tool, so I could not run `check_md.py`.
I wrapped the file by hand (one sentence per line, lines under 80
characters).
Run the checker before use.

## Link references

[rsna-press]: https://www.rsna.org/media/press/2026/2669
[rsna-page]: https://www.rsna.org/artificial-intelligence/ai-image-challenge/knee-mri-ai-challenge
[rsna-kaggle]: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection
[repo-comp]: https://github.com/JunhaoLiXD/RSNA_Knee_Abnormality_Detection/blob/main/docs/competition.md
[aicomp]: https://www.aicompetition.dev/en/competitions/rsna-knee-abnormality-detection
[arxiv-knee]: https://arxiv.org/html/2610.40708v1
[rsna-1st]: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/writeups/1st-place-solution
[kg-1st]: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/writeups/1st-place-solution
[rsna-2nd]: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/writeups/2nd-place-gold-solution-vision-llm-soft-labels-an
[rsna-6th]: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/writeups/6th-place-solution-knee-frame-tiles-pseudo-label
[rsna-7th]: https://www.kaggle.com/competitions/rsna-knee-abnormality-detection/writeups/7th-place-solution-with-no-external-training-data
[pilkwang5]: https://pilkwangkim.github.io/posts/RSNA-Knee-Part-5-After-the-Deadline/
[rsna-clist]: https://clist.by/standings/rsna-knee-abnormality-detection-medicine-computer-vision-image-text-image-classification-roc-auc-score-69383566/
[mira]: https://www.rsna.org/-/media/files/rsna/RSNAI/RSNA-MIRA-Dataset-License-2025.pdf
[hounsfield]: https://hounsfieldlab.com/datasets/rsna-knee-abnormality-detection-2026.html
[kg-1st-labels]: https://www.kaggle.com/datasets/liushuzhi/rsna-knee-1st-place-training-supervision
[kg-7th-labels]: https://www.kaggle.com/datasets/songqizhou/rsna-knee-llm-labels
[kg-6th]: https://www.kaggle.com/datasets/centralyds/rsna-knee-6th-place-models
[kg-3rd]: https://www.kaggle.com/datasets/yeeelzh/rsna-knee-2026-third-place-g36-weights
[kg-late]: https://www.kaggle.com/datasets/ttsuyaogawa/rsna-knee-sub47-x
[ntejas]: https://github.com/NTejas-1/RSNA-Knee-Abnormality-Detection
[physionet-llm]: https://www.physionet.org/news/post/llm-responsible-use/
[dat-rules]: https://www.drivendata.org/competitions/311/dat-parkinsons-challenge/page/990/
[dat-winners]: https://blog.drivendata.org/blog/dat-parkinsons-winners
[figshare-api]: https://api.figshare.com/v2/articles/30335941
[figshare-mfxr]: https://doi.org/10.6084/m9.figshare.30335941
[sd-mfxr]: https://www.nature.com/articles/s41597-026-07547-y
[mfxr-code]: https://github.com/ninglitony/Benchmark-for-MFXR
[garden-sd]: https://www.nature.com/articles/s41597-026-08452-0
[garden-z1]: https://zenodo.org/records/18947088
[garden-z2]: https://zenodo.org/records/22807611
[lidc-nlst]: https://www.cancerimagingarchive.net/analysis-result/lidc-annot-nlst501/
[ts-mri]: https://zenodo.org/records/22688334
[ts-ct]: https://zenodo.org/records/22688904
[topaneu-home]: https://topaneu-26.grand-challenge.org/
[topaneu-data]: https://topaneu-26.grand-challenge.org/data/
[topbrain-home]: https://topbrain2026.grand-challenge.org/
[topbrain-z]: https://zenodo.org/records/21972006
[pdac-osf]: https://doi.org/10.17605/osf.io/g6rv5
[pdac-pmc]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13564768/
[xqa-reshare]: https://reshare.ukdataservice.ac.uk/858610/
[xqa-readme]: https://reshare.ukdataservice.ac.uk/858610/11/README.md
[xqa-arxiv]: https://arxiv.org/abs/2607.26333
[naija]: https://zenodo.org/records/21781842
[chexmask]: https://physionet.org/content/chexmask-u/1.0.0/
[chexmask-api]: https://physionet.org/api/v1/project/published/chexmask-u/1.0.0/
[nlst-arxiv]: https://arxiv.org/abs/2609.10858
[patchct-z]: https://zenodo.org/records/19707049
[patchct-sd]: https://www.nature.com/articles/s41597-026-07793-0
[sparc]: https://arxiv.org/abs/2608.00100
[sparc-site]: https://penn-rail.github.io/SPARC-Rad-Benchmark/
[onc-vqa]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13622859/
[multicare-paper]: https://www.mdpi.com/2313-433X/12/10/484
[multicare-z]: https://doi.org/10.5281/zenodo.20548927
[brats]: https://challenges.synapse.org/brats2026
[pengwin]: https://pengwin2026.grand-challenge.org/
[autopet]: https://autopet-v.grand-challenge.org/timeline/
[amplifai]: https://huggingface.co/datasets/UM-IHC-CA2i/AMPLIFAI
[rexground]: https://huggingface.co/datasets/rajpurkarlab/ReXGroundingCT
[miccai-ch]: https://conferences.miccai.org/2026/en/challenges.asp
[taix]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13100122/
