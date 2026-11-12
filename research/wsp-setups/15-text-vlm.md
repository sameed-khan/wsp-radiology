# Newly released radiology text and vision-language datasets

**As of:** 2026-11-12  
**Cutoff rule:** include data first made publicly available on/after 2026-07-01; Jan–Jun 2026 releases go in a separate borderline list. An extension qualifies only for its post-cutoff material. A later paper, repository edit, or code-only version is not by itself a new data release.

## Summary

I found three directly relevant post-cutoff releases/extensions with verifiable artifact dates: (1) **VinDr-Ground-VQA**, a substantial grounded CXR VQA extension over old VinDr-CXR images; (2) **radiology-conflict**, whose English base predates the cutoff but whose 22 translated configurations were added on 2026-07-06; and (3) two **HUAC Portuguese report-label releases**, whose new annotations were published on Hugging Face in July. A further November 2026 REFLACX-derived eye-tracking/discrepancy table is a useful adjacent annotation resource, but not a new report/VLM dataset. The best near-cutoff candidates are RadM-Bench (first artifact 2026-06-30) and SynRad-IR-200 (first data version 2026-06-11); neither qualifies for the strict post-cutoff list.

The strongest study-ready lead is VinDr-Ground-VQA, but its images and underlying annotations are old, its image pixels require PhysioNet credentials, and every benchmark answer—including its test split—is released. The other new candidates are much smaller or have unclear data semantics/licensing, so they should be treated as pilots until those gaps are resolved.

## Findings

### A. Verified post-cutoff releases and extensions

#### 1. VinDr-Ground-VQA — eligible post-cutoff benchmark/annotation extension; highest priority

- **Name and links:** [Zenodo v1.0 record](https://zenodo.org/records/24073784) · [project/code and datasheet](https://github.com/Yifan-wang-maybe/VinDr-Ground-VQA) · [parent VinDr-CXR on PhysioNet](https://physionet.org/content/vindr-cxr/1.0.0/).
- **Release date and verification:** **2026-11-09.** Direct evidence: Zenodo v1.0 metadata gives that publication date; GitHub's API lists repository creation and first public commits on 2026-11-09. The GitHub datasheet says the release files were frozen earlier (August), but that is a build date, not evidence of public access; the Zenodo label archive and public repository appeared in November. The Zenodo archive is the new data artifact.
- **Modality/anatomy:** PA chest radiographs; thorax.
- **Task and labels:** Grounded visual question answering on 22 VinDr-CXR findings. It contains **102,072 QA pairs** for **8,434 radiographs**: yes/no presence, localization, and open questions; positive findings carry evidence boxes. There are co-occurrence-controlled positive/negative sets, unrelated-context negatives, and a weak-association sensitivity set. Boxes and source diagnoses are radiologist-derived; questions, paraphrases, natural-language locations, and an auxiliary ROI-appropriateness field are generated/checked through the documented pipeline. The authors caution that the ROI-appropriateness field is auxiliary; image crops were sent to an external model API for that check.
- **Size:** 8,434 images/studies and 102,072 QAs (81,656 train / 9,652 val / 10,764 test). **Distinct patient count is not reported.** The subset is not 8,434 newly collected images.
- **Sites, scanners, countries, metadata:** The source VinDr-CXR cohort came from two Vietnamese hospitals (Hospital 108 and Hanoi Medical University Hospital); the source paper reports scanners from Philips, GE, Fujifilm, Siemens, Toshiba, Canon, and Samsung. It is not shown which vendors/sites occur in this particular subset, and the new benchmark does not provide per-image site/vendor/demographic fields. The schema includes image IDs and original dimensions. VinDr-CXR's de-identification removed acquisition date/time and personal identifiers; do not assume temporal or patient metadata is recoverable.
- **Access and license:** QA/box labels and code are downloadable from Zenodo; Zenodo/GitHub declare MIT for the new package. **Pixels are not included.** Users need a credentialed PhysioNet VinDr-CXR copy and must follow its DUA/credentialing terms. Plan for both license regimes.
- **Test set:** Train/val/test labels are public. The new test uses official VinDr-CXR test images, but this is not a hidden test. Make a fresh image- and preferably patient-grouped holdout before any agent sees the benchmark. Original test annotations were five-reader consensus; some reader-agreement fields are not available on that split.
- **Overlap/contamination:** Directly derived from the pre-cutoff VinDr-CXR 1.0.0 images and radiologist labels. The new contribution is the QA framing, consensus-box aggregation, question language, and controlled evaluation sets, not new acquisitions. Models may have encountered VinDr images or diagnoses during pretraining; quarantine the new QA data but treat source-image memorization as a residual risk.
- **WSP fit:** **S47** (generalist medical VLM to a focused radiology task), with a useful **S14** natural/general-image-to-CXR domain-gap variant. Start a fixed generalist VLM (e.g., Qwen2.5-VL) or MedGemma; target VinDr-Ground-VQA using 5/25/100 image-level labeled studies. Compare LoRA/SFT (F) with the same training plus logged, probe/interpretability-derived edits to visual-projector or attention directions tied to finding and localization concepts (G). Use held-out exact answer accuracy, localization/grounding scores, area-matched occlusion response, calibration, and source-task retention. Do not frame this as shortcut removal: the practitioner question is whether the model grounds a CXR answer in lesion evidence.

**Support:** Zenodo record and GitHub datasheet/schema are direct evidence for release/package contents; PhysioNet source documentation is direct evidence for the older source cohort. The use of the new set as a WSP target is researcher interpretation.

#### 2. Multilingual radiology-conflict — eligible only for its post-cutoff language extension

- **Name and links:** [Hugging Face dataset](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict) · [repository revision history](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict/commits/main) · [Hugging Face dataset API metadata](https://huggingface.co/api/datasets/multilingual-vlm-conflict/radiology-conflict).
- **Release date and verification:** The English/default 100-case dataset was first uploaded **2026-06-30** and is borderline, not eligible by itself. Hugging Face commit history shows the language data added on **2026-07-06**, so the extension qualifies. The new configs are Arabic, Czech, German, Greek, Spanish, Persian, French, Hebrew, Hindi, Indonesian, Italian, Japanese, Korean, Dutch, Polish, Portuguese, Romanian, Russian, Turkish, Ukrainian, Vietnamese, and Simplified Chinese. Direct Hugging Face metadata reports 100 rows/config; the 22 new configs therefore represent 2,200 language-rendered rows over the same 100 underlying cases/images, not 2,200 independent patients/images.
- **Modality/anatomy:** Mixed radiology images and text. Sampled rows show, among others, head CT and renal ultrasound; an authoritative modality/anatomy breakdown is not published.
- **Task and labels:** Image plus original caption, question, image-consistent answer, deliberately conflicting caption/answer, conflict type, distractor, and language. The schema includes laterality/pathology conflict fields and caption verification. The extension enables testing whether a model's answer remains clinically/image-consistent across languages; it is not a natural-language report corpus.
- **Size:** 100 underlying cases/images, with 100 rows in each of 23 configurations (English plus 22 added translations). Patient count is not documented. Configurations repeat the same underlying image cases, so never split by row/language alone.
- **Sites, scanners, countries, metadata:** Source institution, image provenance, country, scanner/vendor, and per-image demographics are not specified in the card/API. Some ages appear in captions, but there is no structured patient-demographic field.
- **Temporal metadata:** Acquisition dates and source time period are not documented.
- **Access and license:** Publicly downloadable from Hugging Face. No license is declared in the dataset API/card metadata inspected; clear rights for the images and translated annotations before reuse. Translation method/quality is also undocumented.
- **Test set:** Every language has a public `train` split of 100; no public held-out split. Create a case-grouped split across all language configurations, and keep test-language labels sealed from agents.
- **Overlap/contamination:** English base was public on June 30, and the image-source dataset is not identified. The translated text versions are the post-cutoff addition, but the original cases may be old/public and could already be known to models. The post-cutoff release does not create new images.
- **WSP fit:** **S48/S47.** Use English as source and a held-out target language (e.g., Chinese or Portuguese) as the language-distribution shift, keeping identical images. F: multilingual VLM LoRA on a fixed number of target-language cases. G: the same plus auditable edits based on internal language/pathology/laterality concept directions. Score image-consistent answer accuracy, answer invariance across translations, conflict sensitivity, and calibration. This is best treated as a small cross-lingual pilot, not a clinically powered validation.

**Support:** Repository/API metadata and actual commits directly establish initial upload, the July 6 additions, schema, and row counts. Dataset provenance, image rights, and translation quality remain unknown; do not infer them from the repository name.

#### 3. HUAC Portuguese labeled chest-X-ray report releases — eligible annotation extensions, conditional on schema/overlap audit

- **Name and links:** [v6 labeled reports](https://huggingface.co/datasets/guilhermenf/huac_labeled_chest_xray_reports_v6) · [c5-v1 labeled reports](https://huggingface.co/datasets/guilhermenf/huac_labeled_chest_xray_reports_c5_v1) · [pre-cutoff raw report collection](https://huggingface.co/datasets/guilhermenf/huac_chest_xray_reports).
- **Release date and verification:** Hugging Face API `createdAt` timestamps are **2026-07-10** for v6 and **2026-07-12** for c5-v1. They are after cutoff. The raw, text-only HUAC collection was already public on **2026-05-10** (borderline) and had 223 rows. The qualifying new material is the later labeled release, not any raw report text already in the May collection. Row-level overlap and the exact novelty of the new annotations have not been audited, so count these as annotation-extension candidates, not as new independent report cohorts.
- **Modality/anatomy:** Portuguese-language chest-X-ray report text only. No image files are present in these label releases.
- **Task and labels:** HF schema exposes `report`, `requisition`, numeric fields (`c1`–`c4` and `c1`–`c5` respectively), string fields `j1`–`j4` in v6, and a `label` field. The task/label ontology and codebook were not retrievable from the inspected card; do not guess what the variables mean.
- **Size:** v6 has 254 report rows (190 train / 64 test); c5-v1 has 227 (170 train / 57 test). Distinct-patient count is not specified.
- **Sites, scanners, countries, metadata:** The base card identifies Hospital Universitário Alcides Carneiro (HUAC), associated with the Federal University of Campina Grande, Brazil; this appears to be a one-hospital source, but verify it for each extension. Scanner, per-record site, and patient demographic metadata are not documented in the extension schema. `requisition` should be reviewed for privacy and linkage risk.
- **Temporal metadata:** The pre-cutoff raw-card description says the underlying report collection was 2026-01-01 to 2026-05-07 (date notation follows the Brazilian context, but should be confirmed). The temporal provenance of the new labeled records is not clear.
- **Access and license:** v6 is HF **manual-gated**; c5-v1 is ungated/public. No explicit license field was present in the API metadata inspected. Obtain permission/terms before redistribution or training.
- **Test set:** Train/test partitions and labels are public to anyone with access (v6 access still gated); neither has a hidden challenge test. Test counts are 64 and 57, too small for robust subgroup claims.
- **Overlap/contamination:** The raw HUAC repository predates cutoff and contains reports from the same named hospital. New repositories include report text and labels but no row-level overlap statement. Treat older raw reports as contaminated; deduplicate by requisition/report text and verify which label columns are genuinely new before counting any examples as eligible.
- **WSP fit:** Potential **S48/S51** text adaptation: a fixed multilingual medical text/VLM model trained on compatible English report labels (e.g., MIMIC-CXR/CheXpert label concepts) → Portuguese HUAC reports, with 5/10/25 new target labels. F fine-tunes; G also applies interpretable concept/label-direction edits. Evaluate macro-F1, sensitivity for rare findings, calibration, and retention on English. **Do not run until label definitions, permissions, and overlap are resolved.**

**Support:** Direct HF API metadata establishes repo creation dates, splits, fields, gating, and the base collection's May date/description. Eligibility is limited to newly released labels/annotation material; exact annotation semantics and whether reports are new remain unverified.

#### 4. REFLACX diagnostic-discrepancy derived tables — post-cutoff, adjacent rather than core text/VLM

- **Name and link:** [Zenodo v1 data/code package](https://zenodo.org/records/24128748).
- **Release date and verification:** **2026-11-11**, directly in Zenodo publication metadata. This is a new derived annotation package, not a new release of the old REFLACX images.
- **Modality/anatomy:** Chest X-ray interpretation, eye-tracking/spatial-annotation-derived tabular data. The release does **not** redistribute radiographs, original eye traces, or radiology report text.
- **Task and labels:** 525 valid reading sessions on 109 radiographs were retained; consolidation produced 358 case-finding records/consensus ROIs. Fields include gaze/spatial/consensus features and proportional perceptual, cognitive, satisfaction-of-search-type, and normal diagnostic-discrepancy outcomes.
- **Size:** 109 radiographs, 525 reader sessions, 358 case-finding rows. Unique patient count not stated in the Zenodo description.
- **Sites/scanners/countries/metadata:** Derived from REFLACX, itself based on the older public MIMIC-CXR/REFLACX resource. Site/device/demographic metadata are not reported in this package description; no new acquisition metadata is added.
- **Temporal metadata:** No per-study acquisition dates described in the derived release.
- **Access and license:** Derived CSV tables and code are open under CC BY 4.0. Original images and eye-tracking data are not included and remain subject to REFLACX/MIMIC-CXR access terms.
- **Test set:** Public train/validation/test CSVs, including model-ready versions; no hidden set. Image-level partitioning is stated to avoid one radiograph appearing in multiple splits.
- **Overlap/contamination:** Entirely overlaps old REFLACX/MIMIC-CXR images; only the derived reader/discrepancy annotations are new after cutoff. Not a report-generation benchmark.
- **WSP fit:** Adjacent support for **S10** (maintenance/error-family analysis) if paired with approved access to the older images: predict where radiologist readings diverge, then test whether a small model patch improves error-family performance without harming other cases. This is not a direct VLM fine-tuning dataset; keep it outside the core text/VLM count.

**Support:** Zenodo record description, file listing, splits, and license are direct evidence. The S10 application is researcher inference.

### B. Borderline January–June 2026 releases (not strict-eligible)

#### 5. RadM-Bench — first data files were public 2026-06-30

- **Name/links:** [Hugging Face dataset](https://huggingface.co/datasets/Elizabeth123/RadM-Bench) · [GitHub README and data](https://github.com/ELIZABETH21Wu/RadM-Bench) · [GitHub commit history](https://github.com/ELIZABETH21Wu/RadM-Bench/commits/master).
- **Date evidence:** GitHub repository created June 30 and its initial/upload commits are all June 30; HF metadata also shows last modification June 30. The later paper date does not move this already-public data past cutoff.
- **Modality/anatomy and task:** Bilingual English/Chinese MLLM diagnostic benchmark: clinical history + radiologist-curated key images; complete volume cine clips for clinical cases. 9 subspecialties (80 cases each); CT 250, hybrid/multimodality 299, MR 163, DR 8. Reference diagnosis(es) and common/rare label.
- **Size:** 720 cases total: 360 public English teaching cases from Eurorad and 360 Chinese routine clinical cases from one academic tertiary hospital. The source describes cases, not a guaranteed distinct-patient count. All cases have key images; the 360 RealClin cases have volumetric video/series exports.
- **Sites/time/metadata:** Clinical cases from Henan Provincial People's Hospital, China, retrospectively collected 2022-01-01 to 2024-01-01. RadEdu educational material spans 1999-08-16 to 2024-05-15 and may aggregate many institutions. Scanner/vendor metadata and a structured demographic table are not documented; age/context may appear in histories.
- **Access/license:** HF and a Google Drive archive are linked; dataset card declares MIT. Because some images originate from Eurorad and others from a hospital, verify that this broad license covers all images and downstream use.
- **Test/overlap:** All histories, images, answers, and labels are public; there is no hidden test. Split by case and do not leak images across RadEdu/RealClin. Both source cohorts predate the cutoff; the benchmark packaging was public on June 30.
- **WSP fit:** Strong pilot for **S1/S47/S48**: source English teaching/rare cases → target Chinese routine-practice cases (or 2D key images → full-volume inputs). Use 10/25/50 target cases; compare LoRA against probe-guided language/image-connector edits; score per-specialty accuracy, rare/common performance, and language/volume robustness. The 360-case target is underpowered for small differences and public-test contamination is unavoidable.

#### 6. SynRad-IR-200 — first data version 2026-06-11; November update did not add data

- **Name/links:** [Zenodo v1.0 (2026-06-11)](https://zenodo.org/records/20637519) · [Zenodo v1.2 (2026-11-02)](https://zenodo.org/records/23896461) · [version history](https://zenodo.org/api/records/23896461/versions).
- **Date evidence:** Zenodo version history shows v1.0 publicly deposited June 11; the November v1.2 adds analysis code and supplementary tables, explicitly leaving dataset files unchanged. So it is borderline, not a qualifying new November dataset.
- **Modality/task/size:** Text-only, 200 synthetic radiology reports, generated with Gemma-4-31B-Instruct from structured scenarios designed/reviewed by radiologists. Labels cover IR referral indication and urgency over five clinical domains: vascular, tumoral, infectious, obstruction/leaks, and osteoarticular. Patient/image counts are not applicable.
- **Site/time/metadata:** No real patients, clinical site, scanner, or demographics; no useful acquisition time. Scenario provenance is synthetic and clinical-domain labels are explicit.
- **Access/license/test/overlap:** Open Zenodo, CC BY 4.0. The full generated reports and labels are released; no hidden test. No real-patient image overlap is described. Because this is a small synthetic collection, treat it as a prompt/label pilot, not clinical generalization evidence.
- **WSP fit:** **S47** text-only pilot: generic medical LLM → IR triage, with 10/25/50 labeled reports; F uses LoRA/classification fine-tuning and G adds an interpretable urgency/referral concept edit. Metric macro-F1 and sensitivity at a fixed referral rate. All labels are public; create a scenario-level split and account for possible generator/model contamination.

#### 7. HUAC raw report corpus and radiology-conflict English base

- The raw [HUAC report collection](https://huggingface.co/datasets/guilhermenf/huac_chest_xray_reports) was created **2026-05-10** (manual-gated) and has 223 Portuguese CXR report rows (167 train / 56 test). It is a pre-cutoff base, not a qualifying new dataset. Its later July label releases are described above only as new annotation material.
- The English/default 100-case config of [radiology-conflict](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict) first appeared **2026-06-30**. It is borderline; only the 22 language configs added July 6 qualify as a post-cutoff extension. Do not count the English rows or 100 underlying images as post-cutoff material.

### C. Unverified leads and exclusions

- **LUCQUE (Québec LDCT screening).** The [2026-11-09 preprint](https://arxiv.org/abs/2611.12817v1) describes 1,678 baseline LDCT studies from 1,678 participants, with 1,776 pulmonary nodules, 60 cysts, voxel-level nodule/cyst segmentations, Lung-RADS characteristics, and a PARADIM model-to-data access path. It is promising for CT distribution-shift evaluation, but not a text/VLM corpus, and I could not verify the **first date users could actually access the data** or the platform's access/licensing terms. Do not count it as strict-eligible until PARADIM release/access logs confirm the date. The paper date alone is insufficient.
- **CT/MRI report-summarization evaluation paper:** [arXiv:2611.10277](https://arxiv.org/abs/2611.10277) was screened as a possible report-summary benchmark. A public repository/data artifact and its first data-release date were not verified from the sources reviewed; omit from the dataset count pending an artifact link.
- **PETARSeg-11K:** [arXiv:2510.27680](https://arxiv.org/abs/2510.27680) predates cutoff; a later HF mirror/timestamp does not make the underlying data new.
- **RadCoT and translation-only papers:** prompt/code resources or papers whose data-availability statements do not establish a releasable radiology report corpus were not counted as datasets.

## Concrete experimental setups enabled

All arms start from the same frozen checkpoint and receive identical compute, token, label, and evaluation budgets. Arm **F** may fine-tune but does not directly edit weights. Arm **G** may do everything F does but must add logged, interpretable direct edits and report the edit-ablation contribution. These datasets are small/public; rebuild grouped, sealed test splits before exposing them to agents.

1. **Generalist VLM → grounded CXR VQA (VinDr-Ground-VQA; S47/S14).** **Backbone:** Qwen2.5-VL-7B-Instruct, with MedGemma-4B as a medical-VLM comparator. **Source → target:** fixed generalist/multimodal checkpoint → VinDr-CXR images and newly released grounded questions; evaluate low-label target regimes k=5/25/100 studies. **F:** QLoRA/SFT using only the k target labels. **G:** same plus probe-derived sparse edits to visual-projector/attention directions associated with findings and localization, then revert each edit for attribution. **Metric:** balanced exact-match for presence, text answer F1, box localization/grounding and area-matched occlusion response; calibration and performance retention are guardrails. **Why practitioners care:** a CXR answer should be tied to visible evidence and localization, not just fluent language. **24-GB GPU:** yes for 4B QLoRA; 7B requires 4-bit weights, microbatch 1, checkpointing/limited resolution. No full-model tuning.
2. **Same-image multilingual transfer (radiology-conflict extension; S48/S47).** **Backbone:** Qwen2.5-VL-7B or MedGemma-4B. **Source → target:** English base → one post-cutoff language config (e.g., zh or pt) on the same 100 image cases; use 5/10/25 target-language examples. **F:** multilingual LoRA on those examples. **G:** same plus interpretable edits to language/pathology/laterality concept directions. **Metric:** image-consistent answer accuracy, consistency across translations, correct response to altered laterality/pathology text, calibration. **Why practitioners care:** clinicians need multimodal performance under language and report-style shift. **24-GB GPU:** feasible with quantized LoRA, but this is a 100-image pilot. Split/group by underlying case across every language; no row-random split.
3. **Educational-to-routine radiology shift (RadM-Bench; borderline; S1/S47/S48).** **Backbone:** Qwen2.5-VL-7B; freeze or subsample video frames for 24-GB limits. **Source → target:** 360 English RadEdu cases → 360 Chinese RealClin cases, optionally comparing key images with full-volume cine. **F:** fine-tune/LoRA on k=10/25/50 RealClin cases. **G:** same plus probe-guided edits to visual and language connector directions. **Metric:** case diagnosis accuracy by subspecialty and rare/common disease, plus language and 2D/volume strata. **Why practitioners care:** a model validated on rare teaching cases may not transfer to routine prevalence or volumetric clinical inputs. **24-GB GPU:** 4B quantized LoRA feasible; 7B with short frame sequences and microbatch 1; full-resolution/whole-volume full tuning is not. Dataset is borderline and target N is too small for high-power claims.
4. **English-report model → Portuguese HUAC report labels (conditional; S48/S51).** **Backbone:** a multilingual text/VLM checkpoint such as Qwen2.5-VL-7B, or a compact clinical language encoder. **Source → target:** compatible English report-label task (e.g., harmonized MIMIC-CXR/CheXpert labels) → HUAC Portuguese reports; target k=5/10/25 after codebook and license clearance. **F:** LoRA/classification fine-tuning on the same target examples. **G:** same plus interpretable edits to relevant report-label concept directions. **Metric:** macro-F1, rare-finding sensitivity, ECE/Brier, and source-language retention. **Why practitioners care:** a clinic needs small-data adaptation across language and documentation practice. **24-GB GPU:** yes for an encoder or 4B/7B QLoRA. Not actionable until label semantics, permission, and row overlap are clarified.
5. **Synthetic IR referral/urgency pilot (SynRad-IR-200; borderline; S47).** **Backbone:** MedGemma-4B or another compact medical instruction model. **Source → target:** general medical text instruction checkpoint → synthetic radiology reports with IR referral/urgency labels; use scenario-level k=10/25/50. **F:** LoRA or a simple classifier. **G:** same plus a sparse, concept-probe-guided urgency/referral edit. **Metric:** macro-F1, referral sensitivity at a fixed workload, and edit contribution. **Why practitioners care:** IR referral/urgency triage is a concrete text workflow. **24-GB GPU:** yes. Public labels and synthetic cases make it a low-cost method pilot, not evidence of clinical readiness.

## Relevant pretrained backbones

Release dates below are for the named public checkpoints/families; none listed first released after the 2026-07-01 data cutoff.

| Backbone | First public release | Relevance and constraints | Post-cutoff? |
|---|---:|---|---|
| [Qwen2.5-VL-7B-Instruct](https://qwenlm.github.io/blog/qwen2.5-vl/) | 2025-01 (Qwen announcement) | Generalist multilingual VLM with image, video, localization, and structured-output support; useful for cross-language and video settings. Not a radiology-only model. | No |
| [MedGemma-4B-IT](https://huggingface.co/google/medgemma-4b-it) | 2025-07-09 (model-card “Model created”) | Medical text/image comprehension; 4B multimodal model, a practical medical comparator for VQA and report text. Google Health AI Developer Foundations terms apply. | No |
| [CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b) | 2023-12-15 (project release note) | CXR-specialized VLM for findings/report generation; relevant comparator on VinDr. 8B generally needs quantization/adapter tuning under 24 GB. | No |
| [DINOv3 ViT-B/16](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m) | 2025-08 (paper/model release) | Natural-image vision backbone for S14/S15 domain-gap controls; not a VLM by itself—pair with a fixed text head/decoder or use it for feature-level diagnostics. ViT-B is small enough for one-GPU probing/fine-tuning. | No |

## Contradictions

No primary-source contradiction found for the verified artifact dates. Apparent date conflicts are resolved by distinguishing data access from publication/update: RadM-Bench’s data files were public June 30 despite a later paper; SynRad’s November v1.2 is newer but its record says dataset files are unchanged from June v1.0; VinDr’s internal August freeze date precedes the November public archive and is not itself a public-release date. HUAC's base collection and July label extensions may overlap, but the overlap cannot be resolved from published row metadata.

## Missing evidence and residual risks

- **HUAC:** label codebook/ontology, license/consent for reuse, row-level overlap with the May 2026 raw corpus, and exact temporal provenance of each July set are unavailable. This is the largest blocker for a report-classification experiment.
- **radiology-conflict:** image source/rights, site/scanner and acquisition details, translation method/quality, and a hidden or case-grouped test split are missing. Its effective unique image count is 100, not 2,300.
- **VinDr-Ground-VQA:** no public patient-level grouping field, no included images, and public test labels. The old VinDr-CXR source creates pretraining/benchmark contamination risk; credentialed image access and source/image terms must be respected. Newly generated QA fields include an external-API image-crop check according to the dataset datasheet.
- **Small sets and power:** SynRad (200 synthetic reports), HUAC (~200–250 rows/set), radiology-conflict (100 underlying images), and RadM-Bench (360 clinical cases) are pilots, not adequately powered clinical validation sets.
- **Model/data contamination:** multiple candidate datasets use pre-cutoff source images/reports. The post-cutoff package date does not erase prior exposure of source cases. Every study should document pretraining/evaluation overlap and use grouped, sealed target tests.
- **Date verification:** Zenodo/Hugging Face/GitHub primary metadata and revision histories were manually inspected. The automated source-check pass returned “unclear” for semantic assessment of some repository-date claims, so its score was not used as proof; the cited record timestamps/commit history are the direct evidence.
- **LUCQUE:** exact first access date and PARADIM terms remain unverified; do not count without provider confirmation.

## Sources

### Kept (primary/direct)

- [VinDr-Ground-VQA Zenodo v1.0](https://zenodo.org/records/24073784) — release date, dataset description, size, access split, license.
- [VinDr-Ground-VQA GitHub](https://github.com/Yifan-wang-maybe/VinDr-Ground-VQA) — schema/datasheet, construction, exact release procedure and known limitations.
- [VinDr-CXR on PhysioNet](https://physionet.org/content/vindr-cxr/1.0.0/) — original image access, source-cohort context, site/scanner and de-identification details.
- [radiology-conflict Hugging Face API](https://huggingface.co/api/datasets/multilingual-vlm-conflict/radiology-conflict) and [revision history](https://huggingface.co/datasets/multilingual-vlm-conflict/radiology-conflict/commits/main) — row schemas/configs and direct June 30/July 6 artifact history.
- [HUAC v6](https://huggingface.co/datasets/guilhermenf/huac_labeled_chest_xray_reports_v6), [HUAC c5-v1](https://huggingface.co/datasets/guilhermenf/huac_labeled_chest_xray_reports_c5_v1), and [HUAC raw reports](https://huggingface.co/datasets/guilhermenf/huac_chest_xray_reports) — direct metadata, fields, splits, gates, and createdAt dates.
- [REFLACX discrepancy Zenodo package](https://zenodo.org/records/24128748) — direct description, size, release date, license and files.
- [RadM-Bench HF repo](https://huggingface.co/datasets/Elizabeth123/RadM-Bench) and [GitHub repository/commits](https://github.com/ELIZABETH21Wu/RadM-Bench/commits/master) — dataset composition, public access, and June 30 initial release.
- [SynRad-IR-200 v1.0](https://zenodo.org/records/20637519), [v1.2](https://zenodo.org/records/23896461), and [Zenodo version API](https://zenodo.org/api/records/23896461/versions) — first release, later unchanged data, files, and license.
- [LUCQUE arXiv v1](https://arxiv.org/abs/2611.12817v1) — announced cohort size and model-to-data access, but not an actual first-access date.
- [MedGemma model card](https://huggingface.co/google/medgemma-4b-it), [Qwen2.5-VL announcement](https://qwenlm.github.io/blog/qwen2.5-vl/), [CheXagent model card/release note](https://huggingface.co/StanfordAIMI/CheXagent-8b), [DINOv3 model card](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m) — model scope and release provenance.

### Rejected or deprioritized

- **PETARSeg-11K** — pre-cutoff paper/data history; a later mirror is not a new data release.
- **RadCoT prompt resources** — prompts/code do not establish a publicly released radiology report corpus.
- **Report-translation papers with data unavailable** — paper publication alone is not a dataset release.
- **CT/MRI adversarial report-summarization paper** — no verifiable public artifact/release timestamp found in this sweep.
- **LUCQUE as a strict-eligible dataset** — not rejected as a valuable resource, but deprioritized from the counted list until first data-access date and terms are verified.

## Next steps

1. Request the HUAC codebook, permission/license, and a row-level de-dup report for both July label releases against the May raw set.
2. Ask the radiology-conflict authors for image provenance/license and translation-generation/quality details; construct case-grouped language splits before model exposure.
3. Confirm VinDr-Ground-VQA patient grouping and PhysioNet data-use compatibility; prepare a sealed image-level test because released answer labels are public.
4. Ask PARADIM/LUCQUE maintainers for the first user-access date, access rules, and available per-study metadata before counting it in scope.
