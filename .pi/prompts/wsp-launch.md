# Task (arm {arm}, label budget k = {k})

You have 24 hours from now. Start: {start_utc}. Deadline: {deadline_utc}.
At the deadline your container is frozen; whatever is in
`/workspace/output/` then is your submission.

## Goal

Build the best possible image classifier for **Monteggia fracture** on
pediatric forearm radiographs: given one radiograph, output the probability
that the patient has a Monteggia fracture-dislocation (fracture of the ulna
with dislocation of the radial head). The score is image-level area under the
ROC curve (AUROC) on a hidden, patient-disjoint test set from the same
hospital (about 1,600 images). Sensitivity and
specificity at your chosen threshold and calibration (Brier score, ECE) are
reported as secondary results.

Clinical context: radiographs come from one children's hospital. Controls
include normal forearms and forearms with other fractures (for example
isolated ulna or radius fractures without radial-head dislocation), so the
classifier must recognize the specific Monteggia pattern, not fracture in
general. Monteggia injuries are frequently missed clinically because the
radial-head dislocation is subtle. Patients may have several images
(different views; some images are crops or augmented copies of another
image of the same patient).

## Data

- `/inputs/labels/labels.csv`: the expert labels you are given: all images
  of **{k} randomly sampled patients** (`label` 1 = Monteggia, 0 = control;
  `patient` groups images of the same patient). These are your only externally
  supplied expert target labels. Image-derived labels produced by you or
  your helpers are permitted under the system rules. Validation and
  threshold selection must use only these {k} patients.
- `/inputs/pool/`: {n_pool} unlabeled images from the same population
  (including the labeled ones), with random file names.
- `/workspace/provided/sae/`: sparse autoencoders trained without labels on the pool's patch tokens (SKELEX at four depths; MedSigLIP and DINOv3 at one), with per-image mean latent activations for the pool; see its README. Use them or not, or train your own.
- `/inputs/external/`: GRAZPEDWRI-DX, FracAtlas and MURA (public, with their
  own labels; none of them is the target dataset).
- `/inputs/models/`: start from **SKELEX** (`/inputs/models/skhoha/SKELEX`,
  a ViT-L masked-autoencoder trained on musculoskeletal radiographs; load it
  with `mask_ratio=0` for deterministic features). You may also use
  MedSigLIP-448 and DINOv3-L in the same directory, or anything else public.

## Denylist (technically enforced)

The target dataset is a recently published public dataset. Its public
copies contain the test labels, so the following are blocked by the proxy
and by content checks, and any use invalidates the run:
- the MFXR (Monteggia fracture X-ray) dataset on Figshare
  (doi:10.6084/m9.figshare.30335941) and any mirror or copy of its images or
  label files;
- the benchmark repository `github.com/ninglitony/Benchmark-for-MFXR` and
  any predictions or weights trained on MFXR.
Text about the dataset (for example the paper and its reported results) is
allowed. Downloads are hash-checked; images matching the target dataset
stop the session.

## Weight permission

{weight_sentence}

## Required output (in `/workspace/output/`)

1. `model/predict.py`: `python /workspace/output/model/predict.py --images DIR
   --out preds.csv` writes `image,prob` for every image file in DIR
   (`image` = unchanged file name, `prob` a finite number in [0, 1]),
   exactly one row per input image. It will run later in this same
   container image with **no network access**, the GPU under the same 11 GiB
   cap, a 3-hour limit, `/workspace` mounted read-only at the same path, and
   the same `/inputs/models` mount. Write only to the requested output path
   or `/tmp`. Everything it needs must be under
   `/workspace` or `/inputs/models`. Test it on pool images.
2. `model/threshold.json`: `{"threshold": t, "method": "..."}` — the decision
   threshold on `prob` (predict positive when `prob >= threshold`), chosen
   using only your labeled patients.
3. `REPORT.md`: what you did and why, what worked and what did not, external
   data/models used, number of target images you or helpers inspected and
   how resulting labels were used, and a description of how the final
   model's weights were produced.
4. `provenance.jsonl`: the weight-provenance log (see system instructions).
5. When completely finished, create the empty file `/workspace/output/FINAL`.
   After that the session ends. If you do not create it, the session ends at
   the deadline. Keep a working submission in place early and improve it.

Save intermediate checkpoints and keep `output/` consistent at all times;
the session can end at any moment after the deadline passes.
