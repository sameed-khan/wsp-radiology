# Common research brief for the dataset-search fleet

## Context
We are designing a study of whether "weight-space programming" (WSP) adds value over standard fine-tuning for radiology AI/ML practitioners. In WSP, an AI agent edits a neural network's weights directly, guided by interpretability. Examples:
- ablating or rescaling components;
- inserting hand-wired circuits built from SAE features or probes;
- rank-1 or knowledge edits;
- weight arithmetic and model merging.

## Background reading (do this first)
1. `01-brainstorm-opus.md` (settings S1–S44).
2. `02-orchestrator-supplement.md` (settings S45–S56).

Both are in the same directory as this brief. The investigator dislikes "spurious shortcut" settings, and likes distribution-shift and natural-image-backbone domain-gap settings.

## Tool rules
- Search with the `web_search` tool using provider="exa" (Exa backend), and use fetch/content tools to verify primary sources. Do not ask the supervisor about this; proceed.

## Today's date
2026-11-12.

## Release-date rule
We want publicly available datasets whose data were FIRST RELEASED publicly on or after 2026-07-01. The date must be when the data itself became available, not just when a paper appeared. This is the Opus 5.5 training cutoff (June 2026), and it matters because the study agents must not have memorized the data.

Keep a separate "borderline" list for datasets released Jan–Jun 2026. Include new versions or extensions of older datasets only if the new part was released after the cutoff.

## Sources to sweep
- arXiv and medRxiv dataset papers
- Scientific Data, Radiology: AI, Medical Image Analysis
- NeurIPS 2026 Datasets & Benchmarks
- MICCAI 2026 challenges and workshops
- RSNA 2026 and Kaggle competitions
- grand-challenge.org
- Zenodo, Figshare
- PhysioNet, TCIA, Synapse, OpenNeuro
- Hugging Face datasets
- institutional data portals and national programs

## Per-dataset fields to report
1. Name and link(s).
2. Release date, with evidence and how you verified it.
3. Modality and anatomy.
4. Task and label type: classification, segmentation, detection or report.
5. Size: number of patients and images.
6. Number of sites, scanners, vendors and countries, and whether there is per-image site, device or demographic metadata.
7. Temporal metadata.
8. Access (open, registration, DUA or credentialed) and license.
9. Test-set situation: hidden challenge test set, or released labels.
10. Known overlap with pre-cutoff datasets (contamination risk).
11. Which setups (S#) it supports, and HOW: the starting backbone(s) (for example DINOv3, a domain foundation model, or a generalist medical VLM), the source data, the target or shift, and the label budget.

## Then also provide
- 3–8 concrete experimental setups that your shard's datasets enable. For each give:
  - backbone;
  - source → target;
  - what arm F (no direct edits) and arm G (interpretability-derived direct edits required) do;
  - metric;
  - why it matters to practitioners;
  - whether it is feasible on one 24 GB GPU.
- Relevant pretrained backbones (any release date). Mark the ones released after the cutoff.

## Quality rules
- Be exhaustive.
- Mark uncertainty honestly.
- Never invent a dataset: every entry needs a verifiable link.

## Output format
Markdown.
