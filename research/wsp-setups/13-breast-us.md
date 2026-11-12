# Breast imaging and general ultrasound datasets (release cutoff: 2026-07-01)

**As-of date:** 2026-11-12. This shard covers breast mammography/DBT and breast ultrasound, plus general/fetal/cardiac/pulmonary ultrasound. A paper date is not treated as a data-release date. “Post-cutoff” below means the data, annotation artifact, or public collection itself has verified evidence of first availability after 2026-06-30. An aggregation of older material, a record with no downloadable files, or access-restricted data is separately flagged rather than presented as a clean, usable new benchmark.

## Bottom line

The most useful *verified post-cutoff data releases* are **FUSEP** (fetal B-mode ultrasound; 4,017 images, 3 hospitals/devices, public Drive link present by 2026-09-09), **Open-H-RF** (multi-source raw-channel ultrasound, staged release beginning September 2026), and the **EPFL Multi-Anatomical Ultrafast Ultrasound RF dataset** (20,431 acquisitions, 16 volunteers plus phantom, released 2026-09-24). None is a large new pathology-labeled breast-ultrasound cohort. **BUS-Large** and the new **OMAMA multiview** Dataverse record have post-cutoff catalogue/repository dates, but BUS-Large data are restricted and likely reaggregate old public BUS cohorts; OMAMA’s new study-level subset may overlap the much larger OMAMA dataset released in 2024. Treat both as conditional pending access and provenance/deduplication. The strongest breast-US task data found in this pass, **PU2756**, was actually posted to Figshare on 2026-06-15, so it belongs in the Jan–Jun borderline list—not the eligible post-cutoff set—even though its paper appeared July 4.

### Evidence labels

- **Verified date:** date comes from the data repository’s version/release metadata or dated public data-download link, not simply a paper.
- **Conditional:** a post-cutoff catalogue/record exists, but actual data access, first data availability, or independence from older datasets is unresolved.
- **Not a standalone image dataset:** new metadata/splits/checkpoints are released, but pixels/masks are not.

## Post-cutoff releases and conditional candidates

### 1. FUSEP — early-pregnancy fetal ultrasound benchmark

1. **Name and link(s):** [FUSEP GitHub](https://github.com/ahuteam/FUSEP); [arXiv:2608.04766](https://arxiv.org/abs/2608.04766). The current README links the full COCO image archive on [Google Drive](https://drive.google.com/file/d/1HwY0p5Hw6eiZdgRAUTVy2sDSVqzr2vp8/view?usp=drive_link) and annotation files in the repository.
2. **Release date/evidence:** **2026-09-09 (first verified public full-data link).** The repository’s commit history shows the September 9 README update; that version contains the live full-dataset Drive link. The initial May 25 repo commit did not contain a working data URL (a May 27 README snapshot still had placeholder links). The arXiv preprint first appeared August 5, 2026, but is not used as the release-date evidence. Direct Drive access settings were not independently tested.
3. **Modality/anatomy:** B-mode fetal ultrasound, first-trimester CRL and NT views, gestational weeks 11–14.
4. **Tasks/labels:** Multi-object detection with 45,820 expert box annotations covering 14 anatomical structures. No pixel masks, pathology labels, or outcomes are described.
5. **Size:** 4,017 images. Patient count is not reported; do not equate the image count to patients.
6. **Sites/devices/countries/metadata:** Three hospitals in China (Shenzhen, Sichuan/Chengdu, Yunnan/Kunming) and three device brands: Samsung, SonoScape, GE. The repository gives hospital/device totals and domain labels/splits. Per-image scanner model, demographics, and acquisition date fields are not documented in the inspected card. All images are from 11–14 gestational weeks.
7. **Temporal metadata:** Gestational-window information (11–14 weeks) only; no visit dates or longitudinal examinations reported.
8. **Access/license:** Full images linked publicly through Google Drive; annotations and code publicly linked. Repository states Apache-2.0 for the code and says clinical data are for research purposes. **Do not assume the code license licenses clinical images**; the dataset-specific terms are not explicit in the inspected README. Confirm that Drive access and research-use terms permit the intended experiment before committing.
9. **Test set:** Released train/validation/test annotation files and per-hospital partitions are described; no hidden challenge test set. Use an independent evaluator and seal labels from agents. Rebuild patient-level splits if identifiers allow.
10. **Overlap risk:** No prior public source is claimed for FUSEP’s image cohort. Near-duplicates within/across CRL/NT views and repeated patients must be audited; source does not give patient IDs in its public summary. The model zoo/checkpoints in the repo are also public and must not leak into a “fresh-model” comparison.
11. **Setups:** Strongest fit is **S7/S8 (multi-source or unlabeled-target domain adaptation)** and **S16 (natural-image → ultrasound)**: train on one hospital/device, adapt to a held-out hospital/device with R1 unlabeled images or k∈{5,10,25,50} patients. Start separate, byte-identical F/G pairs from DINOv3, USFM, or SonoBase; the two arms must not use different starting checkpoints. A public 3-site benchmark already contains UDA/SFDA recipes, making this unusually direct. It also supports **S32** (small detector/segmenter at matched latency), though test sizes and patient count may be too small for a tight ΔmAP confidence interval.

### 2. Open-H-RF — community raw-channel ultrasound collection

1. **Name and link(s):** [Hugging Face data](https://huggingface.co/datasets/nvidia/Open-H-RF); [consortium GitHub](https://github.com/open-h/Open-H-RF); [project/catalogue](https://open-h.github.io/Open-H-RF/); [arXiv:2610.13616](https://arxiv.org/abs/2610.13616).
2. **Release date/evidence:** **September 2026 for the first public data contribution; staged release.** The Hugging Face data card explicitly gives “Dataset Creation Date: September 2026.” HF commit history shows raw dataset files/cards being added by September 24. The public v1.0 consortium snapshot and paper/docs were completed in October; the page does not establish one exact day when every contributor’s files first became downloadable. Use September as the earliest verified collection-level release, and record the constituent dataset’s own dates separately.
3. **Modality/anatomy:** Pre-beamformed ultrasound channel/RF capture in `zea` HDF5 format, covering multiple applications and anatomies (including B-mode, flow, ULM and other research acquisitions). Not a single clinical cohort or a standardized diagnostic benchmark.
4. **Tasks/labels:** Raw-signal processing, beamforming/reconstruction, image enhancement, and RF representation learning. Subsets have heterogeneous task-specific labels/metadata; the consortium-wide release does **not** supply one common diagnostic label schema.
5. **Size:** Data card reports **19,471 files, 39.07 TB, and 33 subdirectories**. Aggregate number of people/volunteers, exams and images is not given consistently at consortium level; use each contributing subset’s data card. Do not quote an aggregate patient count.
6. **Sites/devices/countries/metadata:** The contributor list spans 29 organizations (including hospitals, universities and industry), but the release does not give a harmonized number of clinical sites/countries/patients. Subset cards describe transducer/system, acquisition protocol, and available subject/acquisition metadata at different levels. The main card classifies collection/label methods as hybrid (manual, sensor/automatic, synthetic).
7. **Temporal metadata:** Subset-specific only; no unified longitudinal patient timeline.
8. **Access/license:** Public Hugging Face repository; dataset card states **CC BY 4.0**, ready for commercial and non-commercial use. Verify constituent subset cards and source-specific conditions before using any individual subset; do not assume all 33 have identical governance just because the top-level card has a CC-BY badge.
9. **Test set:** No global hidden challenge test. Splits/held-out cases are subset-specific; the consortium is a raw-data source rather than a turnkey benchmark. Create fixed train/dev/sealed-test splits by contributing dataset and subject.
10. **Overlap risk:** High for a naive whole-release benchmark. It is a community aggregation of multiple contributors and may include acquisitions or example/sample data that were separately public earlier. Some sources in the wider ultrasound ecosystem are public pre-cutoff. Treat v1 as a new packaging/collection, not proof every byte is novel. Run exact hashes and reconstructed-image perceptual deduplication; annotate constituent release dates and exclude any pre-cutoff subset from the eligible-data arm.
11. **Setups:** Best fits **S16** (ultrasound domain adaptation), **S40** (acquisition/raw-data reconstruction shift), and potentially **S39** (multi-source model composition) after selecting one subset with stable metadata and a reconstruction target. Use pre-cutoff DINOv3/USFM/USF-MAE on reconstructed B-mode inputs or a task-specific RF encoder; compare to standard fine-tuning with identical target cases. G can edit a probe-localized acquisition-sensitive subspace or wire a documented correction into the model; F can use strong reconstruction/augmentation baselines. The entire 39-TB collection is **not** feasible on one 24-GB GPU; only a small, pre-registered subset is.

### 3. Multi-Anatomical Ultrafast Ultrasound RF Dataset (EPFL / GE 11L-D)

1. **Name and link(s):** [Zenodo record, version DOI](https://doi.org/10.5281/zenodo.22936172); [EPFL data portal](https://datasets.epfl.ch/epfl_ge11ld_ultrafast_ultrasound/); [README/metadata and scripts](https://zenodo.org/records/22936172).
2. **Release date/evidence:** **2026-09-24.** Zenodo API/version metadata gives publication/creation date September 24, 2026; the associated data paper is secondary evidence. An earlier reserved concept DOI exists, but the public version with documentation and links is the 2026-09-24 record.
3. **Modality/anatomy:** Raw ultrafast plane-wave RF from a GE 11L-D probe / Verasonics Vantage 256, including abdomen, carotid/back, breast, arm and leg acquisitions plus phantom data.
4. **Tasks/labels:** Beamforming, coherent plane-wave compounding, reconstruction and signal/image-method benchmarking. **No diagnosis, pathology labels, lesion masks or disease labels.**
5. **Size:** 20,431 acquisitions: 20,121 in vivo from **16 volunteers** and 310 in vitro acquisitions from a CIRS phantom. Total data volume ~4 TB. The breast acquisitions are only a subset (the landing page identifies one breast acquisition archive); do not treat it as a breast-lesion cohort.
6. **Sites/devices/countries/metadata:** One EPFL/Verasonics acquisition setup; GE 11L-D probe; 105 plane waves. Volunteers are the subject unit, not an inference of 20,121 independent patients. Acquisition CSV/settings and volunteer identifiers are provided. Country is Switzerland by institution; no multicenter/vendor variation.
7. **Temporal metadata:** Per-acquisition settings and volunteer IDs are available; no patient disease follow-up or clinical temporal labels.
8. **Access/license:** Raw files are directly downloadable from the EPFL server/S3-compatible endpoint; Zenodo includes metadata/settings/scripts. **CC BY 4.0.**
9. **Test set:** No challenge-hidden test. A related 2026 reconstruction paper used volunteers 005, 008 and 017 as test subjects; this split is useful only for reproducing that paper, not as a sealed new benchmark. The full dataset has no universal train/test partition.
10. **Overlap risk:** Some subset data are described as used in a 2026 IEEE paper. That does not show pre-cutoff public release, but makes those named paper subsets benchmark-contaminated if evaluating agents exposed to the paper. Deduplicate by volunteer/acquisition and avoid reporting them as untouched tests.
11. **Setups:** **S16/S40** for a controlled RF-to-B-mode or acquisition-parameter transfer test. Start with a small reconstruction model or DINOv3/USFM on reference-beamformed images, target a held-out volunteer/acquisition protocol, and compare standard fine-tuning to probe-guided weight edits; primary metrics PSNR/SSIM plus paired reconstruction consistency. Feasible only for one volunteer/anatomical subset with patches; the 4-TB full corpus is not 24-GB-GPU feasible. Not suitable for cancer-classification claims.

### 4. BUS-Large — conditional post-cutoff breast-US aggregation (not open-download confirmed)

1. **Name and link(s):** [KTH repository record](https://doi.org/10.71775/kth.frfd6-ymw69); [Researchdata.se catalogue](https://researchdata.se/en/catalogue/dataset/oai-datarepository-kth-se-frfd6-ymw69); paper record [Medical Image Analysis](https://www.sciencedirect.com/science/article/pii/S1361841526001982).
2. **Release date/evidence:** Catalogue metadata gives `datePublished = 2026-07-15` and `dateModified = 2026-10-06`. This is a post-cutoff catalogue publication date, **not verified evidence that the image files themselves became accessible on July 15**. The KTH record labels access `NON_PUBLIC / restrictedAccess`; do not count this as an openly downloadable post-cutoff dataset unless access is granted and the deposit history confirms the data-release date.
3. **Modality/anatomy:** Curated static breast-ultrasound images.
4. **Tasks/labels:** Harmonized diagnostic labels, pixel-level lesion masks, standardized BI-RADS information; likely useful for both segmentation and benign/malignant or BI-RADS classification.
5. **Size:** Repository description states **more than 21,000 images** aggregated from 21 datasets. Patient count and exact image count are not confirmed in the public record.
6. **Sites/devices/countries/metadata:** Record says 21 source datasets across multiple countries/institutions. It does not expose a harmonized site/vendor/country-by-image table in the public catalogue; check the access package.
7. **Temporal metadata:** Not reported in catalogue metadata.
8. **Access/license:** Record lists **CC BY 4.0** but also restricted/non-public access. Request-based; the license statement does not make restricted image files directly available.
9. **Test set:** No public record of a hidden test; test labels/splits not verifiable without the restricted files.
10. **Overlap risk:** **Very high by construction:** the authors say it integrates static images from 21 already public BUS datasets. The new contribution is harmonization/curation/masks/clinical fields, not necessarily new scans. The source-level dataset list and duplicate-removal protocol need review before any “fresh data” claim.
11. **Setups:** If access is approved and patient-level splits/overlap audit pass, it could support **S16** and **S4-style** modality/vendor/domain transfer, with SonoBase/USFM/DINOv3, plus segmentation label-budget experiments. Until then it is a lead, not an immediately runnable setup.

### 5. OMAMA-DB multiview study-level record — conditional; do not conflate with the old full OMAMA release

1. **Name and link(s):** New [Harvard Dataverse record, `doi:10.7910/DVN/HYFOWN`](https://doi.org/10.7910/DVN/HYFOWN), titled “2D Mammograms Multiview + DeepSight Cancer Annotations”; [OMAMA project page](https://mpsych.org/omama/). The older 2D OMAMA record is [`doi:10.7910/DVN/KXJCIU`](https://doi.org/10.7910/DVN/KXJCIU).
2. **Release date/evidence:** New multiview record has Harvard Dataverse `publicationDate/releaseTime = 2026-08-20`. This verifies a post-cutoff **record release**, not that its scans are new acquisitions. The older 2D OMAMA dataset was already published **2024-07-08**; its Version 3 update in August 2026 adds/resamples files but does not establish newly acquired patients. Treat only any genuinely new cohort/annotations in HYFOWN as potentially eligible.
3. **Modality/anatomy:** 2D bilateral mammography, four standard views (left/right CC and MLO) per study in the new record.
4. **Tasks/labels:** Cancer-category labels (`IndexCancer`, `PreIndexCancer`, `NonCancer`), DeepSight scores, lesion coordinates/bounding boxes, view/laterality and window/pixel-spacing metadata. Not described as pixel-level segmentation.
5. **Size:** HYFOWN record reports **4,138 studies / 16,552 images**, with 1,957 cancer-labeled studies (1,339 index, 618 pre-index) and 2,181 non-cancer studies. Its unique-patient count is not explicitly given (patient IDs are present). **Do not substitute the larger old OMAMA figures**: KXJCIU lists 165,368 2D images from 157,810 patients and 7,351 cancers, with 67,512 3D items/15,149 patients on the OMAMA page; that is an earlier release.
6. **Sites/devices/countries/metadata:** The new record does not state a harmonized site/vendor/country count. PatientID, view, pixel spacing, laterality, window settings, ROI, score and label are in JSON; a full DICOM-header file is provided. Per-image institution/manufacturer tags may be derivable from headers, but are not characterized in the record.
7. **Temporal metadata:** `PreIndexCancer` implies pre-index exams, but time intervals/date coverage are not described in the new record. DICOM-header access may permit further audit.
8. **Access/license:** MIT license is listed; however, Dataverse marks `fileAccessRequest = true` and requires a guestbook/access request. Files are not simple anonymous direct downloads.
9. **Test set:** No hidden challenge test identified; dataset metadata/labels are included with the release. Use a sealed patient-level split.
10. **Overlap risk:** **High and unresolved.** OMAMA’s original 165,368-image 2D collection was public in 2024 and already carries patient/view/DeepSight metadata. The new 4,138-study release may be a subset/repackaging/annotation extension of those same images. Exact patient/image overlap has not been tested; do not use it as a novel-data benchmark until records are cross-matched.
11. **Setups:** Conditional **S4/S9/S21** (mammography vendor/temporal shift and CXR→mammography) using Mammo-FM or DINOv3. The older KXJCIU data can be source data only if its prior-public status is acknowledged; HYFOWN can be target only if its patient set is demonstrably new. Otherwise use it as an additional annotation/version test, not as uncontaminated post-cutoff data.

### 6. SonoCorpus — useful post-cutoff manifest, not a new standalone image release

1. **Name and link(s):** [Zenodo manifest, `10.5281/zenodo.22770825`](https://doi.org/10.5281/zenodo.22770825); [SonoBase repository](https://github.com/AlfredQin/sonobase).
2. **Release date/evidence:** Zenodo’s version metadata gives **2026-09-18**. This is a release of the corpus manifest/splits/checksums, not of raw image data.
3. **Modality/anatomy:** Manifest covers 53 public ultrasound datasets across multiple organs/modalities.
4. **Tasks/labels:** Dataset inventory, image-mask mappings, per-frame metadata, source/license information, leak-reduced pretrain/benchmark/external splits, checksums and evaluation records. Not an independent new annotation release of all constituent masks.
5. **Size:** SonoBase project reports 456,963 images/frames and 1,626,085 masks across 24 clinical applications and 17 countries. These counts describe constituent source datasets, not files hosted by this Zenodo record.
6. **Sites/devices/countries/metadata:** 53 source datasets; the manifest adds/records source/site/vendor/operator context where available. Coverage and completeness vary by source.
7. **Temporal metadata:** Inherits dataset-specific metadata; no unified timeline.
8. **Access/license:** Manifest and checksums open under CC BY 4.0; **no images, masks, or other pixel data are redistributed**. Each component must be obtained under its source terms and licenses.
9. **Test set:** The manifest defines eight benchmark datasets and seven held-out external datasets for SonoBase; the full split lists are public. This is not a new sealed test corpus.
10. **Overlap risk:** The entire corpus is assembled from previously public datasets; overlap with pre-cutoff sources is inherent. The value is reproducible curation/dedup and split records, not new image data.
11. **Setups:** Useful to construct **S7/S16/S32** when source components are independently obtainable, and for verifying patient/source splits. Do not count 456,963 images as post-cutoff images or as a new dataset.

## Borderline releases: January–June 2026

### 7. LUMINA — multi-vendor digital mammography

1. **Name and link(s):** [Kaggle dataset](https://www.kaggle.com/datasets/phy710/lumina-mammography-dataset); [project/GitHub](https://github.com/NUBagciLab/LUMINA); [paper](https://arxiv.org/abs/2603.14644).
2. **Release date/evidence:** Kaggle API records **Version 1 “Initial release” on 2026-03-10** (later dataset versions March 12 and 16). This is the data-hosting date, not the paper’s date.
3. **Modality/anatomy:** Full-field digital mammography (FFDM), usually CC/MLO views for each breast.
4. **Tasks/labels:** Pathology-confirmed benign/malignant classification; expert BI-RADS 0–6 and breast-density A–D labels. No released pixel masks/lesion boxes are described in the paper.
5. **Size:** **1,824 images / 468 patients** (960 benign, 864 malignant image labels); 1,282 images have interpretable BI-RADS/density annotations. Do not mistake images for independent cases.
6. **Sites/devices/countries/metadata:** One collaborating hospital in Istanbul, Turkey; six acquisition systems/vendors (IMS, Metaltronica, Fujifilm, Siemens, Carestream, GE). Native DICOM with 12–14-bit pixels and vendor/energy metadata. Vendor-level sample counts need to be extracted/audited.
7. **Temporal metadata:** Age range 30–88 years; no scan-date/longitudinal series described.
8. **Access/license:** Public Kaggle download (Kaggle account may be needed); listing specifies **CC BY-NC 4.0**. Dataset is ~95.9 GB across current versions; original-resolution mammograms are high-resolution.
9. **Test set:** Paper evaluates with five-fold CV; labels are released, not a hidden challenge set. Rebuild patient-level splits and seal test labels from agents.
10. **Overlap risk:** No source-level overlap with old public breast datasets is stated; it is described as a newly curated hospital cohort. It uses a public Kaggle distribution and paper/code; benchmark results and possible model pretraining exposure are contamination risks, not known image overlap.
11. **Setups:** **S4/S21** (mammography vendor shift; natural/CXR→mammography) and **S13/S54** (threshold/recalibration) with Mammo-FM or DINOv3. Strong exploratory domain shift because vendors are encoded, but **468 patients is too small for the brief’s usual 1,000–3,000-test-study power target**. One 24-GB GPU is sufficient for frozen/LoRA models and patch-based fine-tuning; do not resize away lesion detail without a fair-resolution control.

### 8. PU2756 — pulmonary tumor ultrasound

1. **Name and link(s):** [Figshare record, `10.6084/m9.figshare.32672274`](https://doi.org/10.6084/m9.figshare.32672274); [Scientific Data paper](https://www.nature.com/articles/s41597-026-07715-0); [code](https://github.com/Intelligent-Medical-Research-Group/PU2756).
2. **Release date/evidence:** **2026-06-15**. Figshare API gives `created_date` and `published_date` 2026-06-15 for version 1; the paper followed on July 4. Hence this is borderline despite post-cutoff paper publication.
3. **Modality/anatomy:** B-mode ultrasound of peripheral pulmonary lesions/tumors.
4. **Tasks/labels:** Expert lesion segmentation masks and benign/malignant classification, with biopsy/pathology confirmation.
5. **Size:** **2,756 images from 2,756 unique patients**; Figshare supplies `images.zip`, `masks.zip`, and a five-fold split spreadsheet.
6. **Sites/devices/countries/metadata:** Chinese cohort. The paper acknowledges clinicians from the First Affiliated Hospital of Guangzhou Medical University and Hengqin Hospital, but case counts/site IDs, scanner/vendor distribution and vendor-by-image fields are not exposed in the Figshare metadata. Confirm whether this is one or multiple acquisition sites before treating it as a site-shift set.
7. **Temporal metadata:** No scan dates, follow-up, or longitudinal patient series described.
8. **Access/license:** Direct Figshare downloads; **CC BY 4.0** on the record. The three dataset files total about 834 MB.
9. **Test set:** Five-fold stratified cross-validation spreadsheet supplied; no hidden challenge test. All images/masks and labels are released; construct sealed patient-level folds.
10. **Overlap risk:** No overlap with earlier named public datasets is stated. The code repository existed before this Figshare posting, but the image data’s first verified public artifact is the June 15 Figshare record. Deduplicate images and keep linked masks/patients together.
11. **Setups:** Best small-cohort **S16** test (ImageNet/DINOv3 vs ultrasound-pretrained USFM/USF-MAE) and segmentation/classification **S22** low-label task. F: fine-tune/LoRA, strong ultrasound augmentations and class balancing. G: same F plus probe/SAE-informed edits targeted to lesion-boundary/ultrasound-texture features. Primary metrics: patient-level AUROC and Dice, with calibration and cross-fold variance. Fits a 24-GB GPU with 2D 512-pixel inputs and batch-size/accumulation control; not enough for broad external-site claims without another cohort.

### 9. DBT-2026 — digital breast tomosynthesis with biopsies

1. **Name and link(s):** [medRxiv paper](https://www.medrxiv.org/content/10.64898/2026.03.03.25337924v1.full); [iMerit access page](https://imerit.net/3d-mammogram-dataset/); [Segmed application form](https://segmed.ai/resources/ai-for-impact-on-breast-cancer-dataset-form); [Hugging Face sample](https://huggingface.co/datasets/iMerit/3D-MammographyDataset).
2. **Release date/evidence:** The medRxiv manuscript was posted **2026-03-04** and states the data is available; Hugging Face sample repository was created **2026-03-10** and includes one sample case. These establish a Jan–Jun public announcement/sample, but do **not** establish the exact first date when the complete, DUA-gated dataset was accessible. Treat full-data release date as approximate/unverified.
3. **Modality/anatomy:** DICOM 3D breast tomosynthesis exams (limited-angle projections/reconstructions), screening cohort.
4. **Tasks/labels:** Radiologist localization, characterization, segmentation, measurements; BI-RADS, radiology reports, biopsy/follow-up ground truth. Cohort groups reported: 271 biopsy malignant, 140 benign, 115 callback, 32 biopsy benign.
5. **Size:** **558 patients**. Counts conflict: abstract says 558 DBT exams, while the Results/Discussion text says 1,110 exams from 558 patients. Number of images/slices is not clearly summarized. Resolve from the data manifest before any study plan.
6. **Sites/devices/countries/metadata:** Single hospital/PACS cohort from the Midwest United States; annotations produced by radiologists recruited in India. Scanner/vendor breakdown is not reported. Paper says age, sex, race/ethnicity, BI-RADS, biopsy result, radiology report and DICOM metadata were exported.
7. **Temporal metadata:** No longitudinal follow-up timetable is reported; screening BI-RADS 0–2 and subsequent biopsy/follow-up are represented.
8. **Access/license:** Registration/credentialing and Data Use Agreement required; **non-commercial research only**, no redistribution, no re-identification or clinical use. Paper says access is case-by-case; Hugging Face has samples, not full cohort. No permissive general data license identified.
9. **Test set:** No hidden challenge split stated; DUA-gated full cohort. Labels are tied to outcomes and radiology annotations.
10. **Overlap risk:** No prior dataset overlap claimed. One sample case is public on HF and data are in a public preprint, so check for benchmark familiarity and ensure test images are not among example materials.
11. **Setups:** Conditional **S4/S21/S54**: DBT-vs-2D mammography transfer or low-label DBT detection with Mammo-FM/DINOv3. Likely not a clean vendor-shift study (single hospital and no vendor breakdown), and access is gated. 24-GB feasibility depends on slice/volume pipeline; use 2D/2.5D crops and test full volume inference before selecting.

### 10. EchoRisk-MICCAI — longitudinal cardio-oncology echocardiography

1. **Name and link(s):** [Dataset page](https://echorisk-miccai.github.io/dataset.html); [timeline](https://echorisk-miccai.github.io/timeline.html); [rules/FAQ](https://echorisk-miccai.github.io/rules.html); [tasks](https://echorisk-miccai.github.io/tasks.html).
2. **Release date/evidence:** Official challenge timeline states **training and validation labels/data released 2026-04-17** to registered participants. This is a scheduled challenge data release corroborated by the challenge’s dataset/rules pages. Registration is now closed; the rules state new access requests cannot be granted and any future open release has no confirmed date.
3. **Modality/anatomy:** Clinical echocardiography DICOM videos, apical 4- and 2-chamber views, breast cancer patients undergoing cardiotoxic treatment.
4. **Tasks/labels:** LVEF regression; LV dysfunction classification from GLS; baseline prediction of future cardiotoxicity. Labels include LVEF, GLS and cardiotoxicity status.
5. **Size:** **422 patients, 2,159 DICOM videos**, 1,036 fully paired exams. Task 3 baseline cohort is 280 patients. Four follow-up points are described at three-month intervals.
6. **Sites/devices/countries/metadata:** Multicenter CARDIOCARE-derived cohort, but public challenge card does not expose harmonized per-site/vendor/country counts; de-identification removes clinical site identifiers. Do not claim an exact number of sites or manufacturers. DICOM temporal/spatial calibration fields are absent; `NumberOfFrames` is present.
7. **Temporal metadata:** Baseline plus up to four q3-month follow-ups; some exams can lack one of A2C/A4C views. Missingness and patient-linked longitudinal structure are central data properties.
8. **Access/license:** DUA and official registration required; **CC BY-NC-SA 4.0** with additional challenge restrictions. Training data are not open to new registrants after the challenge; future open release is only planned.
9. **Test set:** 56% train / 14% validation / 30% hidden test. Validation labels were released to registered participants; hidden test labels/results are organizer-held. Test access required a valid methodology-paper submission and Docker challenge submission.
10. **Overlap risk:** Derived from CARDIOCARE; no public overlap with a named earlier dataset is stated. Public papers/challenge baselines and challenge model checkpoints are a knowledge/benchmark contamination risk. Patient follow-ups must be grouped in any split.
11. **Setups:** **S9/S8** (temporal drift/low-label update; target-time adaptation) with EchoPrime or BUVFM weights. A clean design would train on baseline/earlier visits and adapt with k labeled follow-ups, scoring future visits and churn on earlier visits. F: LoRA/LP-FT and calibration; G: same plus interpretable temporal/probe-based edits. Primary: LVEF MAE or GLS AUC, with patient-level split and source retention. 24-GB GPU should fit sampled-frame video fine-tuning; data access prevents a new external team from running this now.

### 11. FADA Interpretation Dataset — fetal image interpretation annotations (not currently downloadable)

1. **Name and link(s):** [Zenodo v1 record, DOI `10.5281/zenodo.20104811`](https://doi.org/10.5281/zenodo.20104811); [FADA project/code](https://github.com/mahmoodphd/FADA); [current Zenodo version](https://doi.org/10.5281/zenodo.20381238).
2. **Release date/evidence:** **2026-05-11** for version 1 according to Zenodo API/record metadata. The v2 record is dated May 25. Both precede the cutoff. The model/data card and arXiv paper are not used in place of the Zenodo date.
3. **Modality/anatomy:** Expert interpretation annotations for fetal-ultrasound images across 14 anatomy/view categories.
4. **Tasks/labels:** 56,805 structured conversation/response items, eight clinical-description fields per full entry (anatomy, orientation, plane, biometry, gestational age, quality, normality and recommendation). It is a VLM instruction/annotation set, not pixel segmentation.
5. **Size:** **18,935 unique images** and 56,805 conversations (37,870 full eight-field records plus 18,935 four-field records). The images are not included.
6. **Sites/devices/countries/metadata:** Derived from seven existing public datasets (FPUS23, FUSEP, HC18, CRL_NT, FOCUS, fetal abdominal structures, PS-FH); original source sites/devices/demographics vary and are not harmonized in the described annotation set.
7. **Temporal metadata:** Gestational-age descriptions; source image collection dates and serial exams are not provided.
8. **Access/license:** Zenodo lists CC BY 4.0 for metadata but record access is **restricted**; Zenodo API showed no files attached to the inspected v1/v2 records. The source images are not redistributed and must be acquired from their original repositories. Thus the annotations are not presently verified as freely downloadable despite the record’s public metadata.
9. **Test set:** No hidden challenge set specified; the page describes 237-image expert validation and a 49-case human-in-the-loop evaluation. The source image/test splits are inherited from multiple datasets and require careful source-level deduplication.
10. **Overlap risk:** **Certain/high:** all image pixels are from pre-existing public datasets, and FUSEP is one of the sources. New contribution is the annotation layer; do not count 18,935 as newly released post-cutoff images. The release itself is Jan–Jun and restricted.
11. **Setups:** If a downloadable annotation export is obtained, supports **S17/S23/S47** (fetal ultrasound VLM adaptation and zero/few-shot clinical concept descriptions) with Qwen-VL/FADA-SKD-4B. It is not a new image cohort. Data access currently blocks a reproducible public setup.

## Relevant pretrained backbones / models

Release status here refers to **checkpoint/model availability**, not training-data release. “After cutoff” means after 2026-06-30; terms still need local compliance review.

| Backbone/model | Availability/status | Relevance and constraints |
|---|---|---|
| [DINOv3](https://github.com/facebookresearch/dinov3) / [DINOv2](https://github.com/facebookresearch/dinov2) | **Before cutoff** (DINOv3 public release 2025; DINOv2 2023). | Natural-image ViT baseline for S14/S16/S21; use as an ImageNet/natural-domain control. Not ultrasound or mammography-specific; weight license/model-card terms apply. |
| [USFM](https://github.com/openmedlab/USFM) | **Before cutoff** (2024 paper; public checkpoint link in official repo). | General ultrasound ViT pretrained with self-supervision on the authors’ claimed 2M-image multi-organ/multicenter pool; useful for S16 and FUSEP/PU2756. Repo code license is CC BY-NC 4.0; model-weight/data-use terms should be checked separately. |
| [USF-MAE](https://github.com/Yusufii9/USF-MAE) | **Before cutoff** (repo created 2025-10-22; latest inspected checkpoint links existed by 2026-04-25). | Ultrasound-only MAE, 370k 2D/3D images from 46 public datasets; explicitly evaluated on breast classification. Checkpoint links are Google Drive; constituent data retain their original terms and the model-weight license is not explicit in the README. |
| [BUVFM](https://github.com/SCU-MILAB/AIBUS-CODE) / [Hugging Face weights](https://huggingface.co/xenosscu/BUVFM) | **Before cutoff**: weight repository created 2026-05-11; repository explicitly lists HF release. | Breast-ultrasound video specialist (423k frames/84k sequences; BI-RADS risk stratification). Strong breast-US video starting point. Training data are not the same as an independently available public dataset; license for weights is not clearly stated in the inspected README/API. |
| [Mammo-FM](https://huggingface.co/batmanLab/Mammo-FM) | **Before cutoff**: HF model repo created 2026-04-10; 2025 arXiv paper. | Breast-specific mammography representation/VLM model. **Custom academic-only license**: non-commercial research only; no clinical deployment, commercial use, redistribution or hosted serving. Good S4/S21 baseline if the project is eligible under that license. |
| [EchoPrime](https://github.com/echonet/EchoPrime) | **Before cutoff**: inference release published 2024-10-15; downloadable model-data assets posted by 2025. | Echocardiography vision-language/video model, useful for EchoRisk tasks. Check upstream license and permitted use; only authorized challenge participants can currently access EchoRisk data. |
| [FADA-SKD-4B](https://huggingface.co/mshz88/FADA-SKD-4B) | **Before cutoff**: HF model page created 2026-05-10; revision June 29. | Fetal-ultrasound VLM adapter/checkpoint (Apache-2.0 card), built on Qwen3.5-VL-4B; need the base model and must respect its separate license. It is a specialized VLM, not a generic image encoder. |
| [SonoBase](https://huggingface.co/AlfredQin/sonobase) | **After cutoff**: HF checkpoint repo created 2026-08-21; weights tagged **CC BY-NC 4.0**. | General ultrasound interactive segmentation model. Relevant for FUSEP and US segmentation, including cross-device/domain shift. It was trained on SonoCorpus, which is itself an aggregation of older datasets; disclose checkpoint’s training provenance and check overlap. |
| [UltraSAM3](https://huggingface.co/zhuqh19/UltraSAM3) | **After cutoff**: weights created/released 2026-07-30; Apache-2.0 HF card. | Promptable ultrasound segmentation model; training table lists 37 existing ultrasound datasets, including BUSI/BUS-BRA-related cohorts. Good FUSEP segmentation baseline, but high risk of source-data overlap for any individual dataset among its training collections. |
| [BreastGPT](https://yangyy-liu.github.io/BreastGPT.io/) | **After cutoff or date uncertain**: model page says accepted EMNLP 2026 and links an 8B ModelScope checkpoint; exact first public checkpoint date/license not confirmed in this pass. | Breast workflow VLM with BUS and mammography tasks, trained on a 1.86M instruction-pair/17-source corpus. Treat as a post-cutoff model and inspect ModelScope terms plus training-set overlap before using it as a baseline. |

## Concrete experimental setups enabled by this shard

The F/G pair must start from identical weights. F is allowed strong standard training (LP-FT/LoRA, augmentation, domain adaptation, recalibration); G gets everything F gets **plus mandatory interpretability-derived direct weight edits**. Revert each edit after training, add random-edit controls, and report source retention, target results, calibration, churn, diff size and wall-clock as the common brief requires.

### A. FUSEP cross-hospital ultrasound adaptation — S7/S8/S16 (best runnable post-cutoff setup)

- **Backbone:** DINOv3 ViT-B or USFM; run separate F/G experiments per start checkpoint. Detection head: a small DETR/RetinaNet-style decoder at fixed resolution.
- **Source → target:** Shenzhen/Samsung → Sichuan/SonoScape or Yunnan/GE; (i) R1 unlabeled target, then (ii) k={5,10,25,50} target-labeled patients. Primary test is held-out hospital/device, with source site retained as guardrail.
- **F:** supervised source training then standard UDA/LP-FT/LoRA and strong geometric/intensity/speckle augmentation; same target pool and label budget.
- **G:** same F, plus probe/SAE directions for hospital/device prediction; edit/rescale a small set of encoder channels or insert a sparse adapter-like weight circuit aimed at target-box features. Log target tensors/operation/norm and run edit-reversion/random-direction controls.
- **Metric:** mAP@[.5:.95] and per-class AP; secondary source mAP, worst-site AP, ECE, prediction churn. Seal held-out hospital test labels.
- **Practitioner value:** asks if a small audited model patch can transport fetal anatomy detection across device/site without full retraining.
- **One 24-GB GPU:** **Yes, likely**, with ViT-B/ResNet detector, 640-ish inputs, AMP and small batches. First audit patient identifiers/duplicates; dataset has only 4,017 images and patient count is missing, so power may be insufficient for <0.01 AP effects.

### B. Natural-image → pulmonary ultrasound segmentation/classification — S16/S22 (strong borderline data)

- **Backbone:** DINOv3 (natural baseline) and USF-MAE/USFM as an ultrasound-domain upper bound; keep the F/G pair identical within each track. Dataset: PU2756 (June 15, 2026; borderline, Figshare CC BY 4.0).
- **Source → target:** ImageNet/natural-image pretraining → PU2756; label regimes k={5,10,25,50,200} patients, with five-fold patient-level evaluation. Compare a matched ultrasound-pretrained checkpoint separately.
- **F:** linear/LoRA/full fine-tuning as budget allows, class balance, and standard ultrasound augmentation.
- **G:** F plus saliency/probe-derived edits for lesion texture/border and speckle-sensitive channels; must be followed by edit-ablation and random-edit controls.
- **Metric:** patient-level benign/malignant AUROC/AUPRC and lesion Dice; report confidence intervals across folds and calibration.
- **Practitioner value:** a direct test of whether interpretable edits narrow the natural-to-ultrasound gap when biopsy labels are scarce.
- **One 24-GB GPU:** **Yes**, 2D crops and AMP; 2,756 patients allow patient-level folds. Do not make multicenter robustness claims without confirming source-site diversity.

### C. Mammography vendor shift — S4/S21 (exploratory only; LUMINA is small)

- **Backbone:** Mammo-FM (academic-only license) or DINOv3; optional RadDINO/CXR encoder control. Dataset: LUMINA (March 10, 2026, borderline), with 468 patients and six declared acquisition systems.
- **Source → target:** train on vendor/system A and use unlabeled or k-labeled patients from a held-out LUMINA vendor as target; optionally compare against an older publicly available mammography source set, with patient/image overlap audits.
- **F:** LP-FT/LoRA, vendor-aware/intensity augmentation, temperature scaling.
- **G:** same F plus vendor-probe-guided stem/normalization edits or a sparse edit to vendor-sensitive features; report contribution after edit reversion.
- **Metric:** patient/exam-level pathology AUROC and sensitivity at a fixed specificity; secondary worst-vendor AUROC, calibration, source retention and churn.
- **Practitioner value:** tests a common failure mode in screening deployment—processing style and scanner heterogeneity—without confusing label differences with vendor shift.
- **One 24-GB GPU:** **Yes** for patch-based/frozen-encoder experiments, but **not adequately powered for a definitive clinical ΔAUROC claim**: 468 patients and vendor-wise counts need review first. Use as pilot/negative-calibration setting, not primary evidence.

### D. Longitudinal cardio-oncology hotfix — S9/S8 (conditional on existing EchoRisk authorization)

- **Backbone:** EchoPrime or BUVFM, then fine-tune an identical starting model for F/G. Dataset: EchoRisk-MICCAI (released to registered teams April 17, 2026; access closed to new users).
- **Source → target:** baseline/earlier visits → later q3-month follow-up visits, using k={5,10,25,50} newly labeled patients; patient-level split and preserve full trajectory.
- **F:** temporal video LP-FT/LoRA, sampled-frame strategy, strong video augmentation and calibration.
- **G:** same F plus interpretable timepoint/view-direction edits to the output/temporal representation; quantify update benefit and churn on earlier visits.
- **Metric:** LVEF MAE or GLS-dysfunction AUROC; co-primary retention/churn on baseline and earlier follow-up exams. Use hidden challenge test only for an authorized team.
- **Practitioner value:** models how a deployed surveillance tool could be updated after new treatment protocols or a changed follow-up population without damaging baseline performance.
- **One 24-GB GPU:** **Likely yes** with frame sampling/frozen video encoder; cannot run without an authorized dataset copy. This is a conditional design, not a recommendation to bypass the challenge DUA.

## Contradictions, exclusions, and residual risks

- **OMAMA scope conflict:** the 2024 Dataverse record KXJCIU reports 165,368 2D images/157,810 patients (and current Version 3 metadata); the new HYFOWN record reports 4,138 studies/16,552 images. These are different record/version scopes. Keep them separate; the 2026 release is not automatically a novel-patient cohort.
- **BUS-Large date/access:** catalogue says July 15, but data access is restricted and first file availability is unverified. Do not treat a catalogue publication date as proof a research agent could download the data then.
- **Open-H-RF release is staged and heterogeneous:** September data-card date, September file additions and October v1 announcement refer to different milestones. Constituent subsets may have been public earlier.
- **DBT-2026 count discrepancy:** the medRxiv abstract says 558 exams; Results/Discussion reports 1,110 exams from 558 patients. Resolve against the authorized manifest before powering a study.
- **PU2756 is eligible only for the Jan–Jun borderline bucket:** its file record says June 15; the article’s July 4 date does not move it past cutoff.
- **FADA annotation data is not a freely downloadable new image set:** Zenodo metadata is public but the files are restricted/absent from the inspected records, and every source image is older public data.
- **SonoCorpus is a manifest, not new image data:** do not count the 456,963 source images as post-cutoff scans. Use source licenses and dedup lists.
- **Other leads not counted:** `Heartbeat` (2026 fetal-echo paper, 1,475 patients) had no verified public data files/first release in this pass; BUS-CoT’s Figshare record predates cutoff (2025-12-09) despite a 2026 paper; the Zenodo breast-US item `21315228` is a code/reproducibility package and does not redistribute original images; no verified post-cutoff data extension was found for TN-Mammo v1.0.1.
- **Power and contamination:** FUSEP and LUMINA are small; PU2756 is a single-region cohort; the raw-RF corpora lack diagnostic labels; large aggregates contain prior public sources. No dataset listed alone guarantees the brief’s 1,000–3,000-study target test size. Prioritize patient-level dedup, sealed test labels, exact subset provenance, and acquisition metadata checks before agent access.

## Source shortlist

- [FUSEP official repository](https://github.com/ahuteam/FUSEP) — data link, license caveats, sites/devices, labels and dated README history.
- [Open-H-RF HF collection](https://huggingface.co/datasets/nvidia/Open-H-RF) and [GitHub](https://github.com/open-h/Open-H-RF) — release metadata, constituent cards, license and files.
- [EPFL/Zenodo raw RF record](https://zenodo.org/records/22936172) — authoritative release/version date, data size, volunteer count, access and license.
- [BUS-Large KTH metadata](https://researchdata.se/en/catalogue/dataset/oai-datarepository-kth-se-frfd6-ymw69) — publication date, composition and access restriction.
- [OMAMA Dataverse new multiview record](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/HYFOWN) and [older 2D record](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/KXJCIU) — distinguish post-cutoff record from 2024 public dataset/version.
- [SonoCorpus Zenodo manifest](https://zenodo.org/records/22770825) — proves manifest-only status and source-license structure.
- [LUMINA Kaggle](https://www.kaggle.com/datasets/phy710/lumina-mammography-dataset) / [paper](https://arxiv.org/abs/2603.14644) — initial version/date, license, patient count, pathology/BI-RADS/density and vendors.
- [PU2756 Figshare API/record](https://api.figshare.com/v2/articles/32672274) / [paper](https://www.nature.com/articles/s41597-026-07715-0) — verified June 15 release, direct files/license and clinical label description.
- [DBT-2026 medRxiv](https://www.medrxiv.org/content/10.64898/2026.03.03.25337924v1.full) — preprint, cohort, access form, DUA and exam-count inconsistency.
- [EchoRisk official timeline](https://echorisk-miccai.github.io/timeline.html), [dataset](https://echorisk-miccai.github.io/dataset.html) and [rules](https://echorisk-miccai.github.io/rules.html) — data release, hidden test and current access restrictions.
