# Mech-interp toolbox for label-efficient weight-space programming in radiology

Compiled 2026-11-08.
Scope: tools a reasoning optimizer (Claude Opus 5.5) could use to
diagnose, hypothesize, edit and verify the weights of a radiology image model
while using as few task labels as possible.

## 1. Summary

The toolbox is large, but most of it falls into three groups
that differ in how much labeled data they consume.

1. Tools that need no task labels:
   feature visualization, neuron labeling (CLIP-Dissect, DnD, MAIA),
   sparse autoencoders (SAEs) trained on unlabeled images,
   synthetic probes (RadEdit, RoentGen), slice discovery,
   concept banks (CLEAR, SpLiCE), and unlabeled-image data selection.
2. Tools that need a handful of labels, used only for verification
   or for choosing among a few hypotheses:
   difference-of-means directions, linear probes, concept activation vectors,
   last-layer reweighting, activation patching on labeled pairs.
3. Tools that are gradient optimizers in disguise:
   SAE training, TRAK or influence functions, Santurkar-style edits,
   task arithmetic from fine-tuned models, "watch a small net train".
   These can be label-free or label-consuming,
   but they must be reported as conventional optimization.

The strongest direct evidence on the WSP side is cautionary.
The original report says editing removed an obstacle to an existing ability
but did not add one that the model lacked ([WSP post][wsp], Gemma 3 270M run).
A reproduction found that a difference-of-means script
recovered 93% of the gain of the released Qwen edit ([aiXiv][aixiv]).
A clinical audit found a simple per-flaw statistic found the same flaws
as Opus 5.5 ([arXiv 2611.05341][clin]).
For a label-efficiency study, the likely win is therefore
"expose and re-weight features the pretrained backbone already has,
using unlabeled data and priors",
not "write new visual features".
The tool choices below are ranked with that expectation in mind.

Label codes used throughout:

- **N**: no images of the target task are needed.
- **U**: unlabeled target-domain images only.
- **X**: labels from other datasets (including labels baked into
  pretrained or generative models).
- **T**: task labels from the target cohort.

Maturity is rated for vision models specifically:
high (widely replicated), medium, low, or unproven.

## 2. Verified WSP context (2026)

These items were fetched and read for this review.

- Takehi, Teoh, Zhang and Khattab, "Sparks of Weight-Space Programming",
  2 Nov 2026 ([post][wsp]).
  Experiments on real language models used Python and forward passes.
  The no-tool setting appears only on networks of 17K to 172K weights.
  On Gemma 3 270M, which rarely loops, Astra could not improve math.
- Nusrat, arXiv 2611.05341 ([clin][clin]):
  Opus 5.5 audited small radiotherapy screening networks (433 to 4,801
  parameters) with no tools or data.
  It named the broken rule in 16 of 18 flawed networks,
  but each flaw was "visible in single units"
  and "a simple statistic chosen for each flaw type found the same flaws".
  Black-box testing found confounds faster.
  It could not certify that a network was correct.
- arXiv 2611.08070 ([read][read]):
  Opus 5.5 reading about 125K-parameter CNNs zero-shot
  was better described as local arithmetic plus dataset priors than as
  weight-flow tracing.
  Label permutation broke its interpretations.
  Mostly single runs.
- aiXiv 261103.000004 ([aixiv][aixiv]):
  the released Qwen edit raised accuracy from 10.2% to 64.8% on 64 practice
  problems.
  A difference-of-means script reached 60.9% (93% of the gain)
  once it was given Astra's layers, column budget and scale.
  Blinded Opus 5.5 and Sonnet 5.5 runs found positive-gain edits
  but stopped after 18 to 23 forward-pass requests.
- arXiv 2611.07319 WeightLoop ([wloop][wloop]) is a 5-page paper
  where GPT-6 Astra writes an editing program once
  and the program then applies small edits (for example 16 weights)
  to a gene-ranking predictor as feedback arrives.
  Its offline replay used experimental assay feedback, not images.
- arXiv 2611.04268 ([wrest][wrest]) is explicitly conjectural
  (no experiments) for image-restoration diffusion models.
  It argues low-level layers are editable and semantic layers
  are "distributed and resistant to sparse modification".
- Secondary commentary ([critics][critics], [audit][audit]) reports
  that the Qwen edit reproduces at about 51% on MATH-500
  and that reading real-model weights helped little.
  These are blog posts, not peer-reviewed;
  treat their numbers as unverified.
- Program-as-Weights ([PAW][paw]) predates the post by four months
  and compiles functions into LoRA weights with a trained compiler.
  It is a trained generator of weights, not an LLM reading weights.

Implication for design:
the only vision-relevant WSP evidence is on toy CNNs (arXiv 2611.08070)
and conjecture (arXiv 2611.04268).
No published WSP result adapts a real radiology model.
The proposed study would therefore be the first test of this kind.

## 3. Toolbox by family

### 3.1 Feature discovery and labeling

**F1. Feature visualization and activation maximization.**

- What: optimize an input to maximize a unit's activation
  ([Olah et al. 2017][featvis]; [Zoom In][zoomin]).
- Reveals: what a channel or neuron responds to.
  Cammarata states that "fixed feature visualization" and attribution
  visualization improved the share of understandable neurons
  in InceptionV1 ([essay][clean]).
- Labels: N.
- Maturity: high on CNNs; medium on ViTs (patch-token neurons are harder);
  unproven on radiographs (images look like noise or textures).
- Cost: seconds to minutes per unit on one GPU.
- Code: Lucid, Lucent, Captum (open source; not re-checked here).
- WSP use: diagnose.
  The optimizer can render top units of a head-adjacent layer
  and flag units that encode non-anatomical texture or markers.
- Caveat: visualizations may not match natural-image statistics
  of radiographs. Pair with exemplar search (F4).

**F2. Network Dissection and Net2Vec.**

- What: align units with labeled concept masks
  ([Bau et al. 2017][netdis]; Net2Vec, arXiv 1801.03454, not re-fetched).
- Reveals: which units match which labeled concepts (Broden).
- Labels: X (needs a segmentation dataset with concept masks).
- Maturity: high on CNNs; low on radiology (no Broden-like set).
- Cost: low to medium.
- Code: public (original repo; not re-checked here).
- WSP use: only if public anatomy masks exist
  (lungs, heart, ribs, devices).
  Anatomy masks from other datasets count as X, not T.

**F3. CLIP-Dissect, MILAN, FALCON, Describe-and-Dissect, LINE.**

- What: label neurons with text.
  [CLIP-Dissect][clipdissect] needs no labeled data or concept masks.
  [MILAN][milan] trains a captioner on human neuron descriptions.
  [FALCON][falcon] captions top-activating crops.
  [DnD][dnd] is training-free and concept-set-free.
  [LINE][line] (2026) is an iterative LLM-based labeler.
- Reveals: candidate natural-language meaning for each unit.
- Labels: N or U.
  MILAN needs X (human-annotated descriptions).
  The CLIP-type labelers use a general CLIP or captioner;
  a radiology encoder (CLEAR, BiomedCLIP) must replace it,
  otherwise the text will describe radiographs as "gray image".
- Maturity: high on ImageNet CNNs;
  low on radiology (not shown to be reliable there; unverified).
- Cost: low.
- Code: CLIP-Dissect and DnD have official repos.
- WSP use: hypothesize.
  Output a table of unit to concept hypotheses
  that the optimizer then tests with probes (S1 to S4).
- Caveat: CVPR 2026 work reports that top-activation-only evaluation
  is unreliable for such labelers ([Oikarinen et al.][evalcvpr]).

**F4. Exemplar search and crop-response mapping.**

- What: rank unlabeled images or crops by a unit's activation,
  and move or resize a window to see which region drives it.
  This is the user's "crop and observe" affordance.
- Reveals: spatial and content selectivity of a unit.
- Labels: U (unlabeled target images) or N (unrelated public images).
- Maturity: high; this is basic mechanistic practice.
- Cost: one forward pass over the pool, or many for sliding windows.
- Code: trivial in PyTorch hooks; [Prisma][prismacode] for ViTs.
- WSP use: diagnose and verify.
  The optimizer can test the claim "unit 312 fires on pacemaker leads"
  by cropping leads out and re-measuring.
- Caveat: attention mixes information across patches,
  so the highest-activating patch need not cause the feature.
  [CaFE][cafe] addresses this with effective receptive fields.

**F5. Automated interpretability agents.**

- What: an LLM or VLM designs and runs experiments on another model.
  [MAIA][maia] ([code][maiacode]) synthesizes and edits images,
  retrieves exemplars and summarizes, to label units and find failure modes.
  [OpenAI auto-interp][bills] describes and scores neurons.
  Anthropic's [auditing agents][auditagents] and
  [AuditBench][auditbench] test tool-using investigators on language models.
  [Natural Language Autoencoders][nla] verbalize activations (language
  models only).
- Reveals: faster hypothesis loops; failure modes such as
  spurious background cues (MAIA).
- Labels: N or U.
- Maturity: medium on ResNet-class vision (MAIA);
  unproven on medical imaging.
- Cost: LLM tokens plus forward passes.
- Code: MAIA is open source; Anthropic agent prompts are open.
- WSP use: the optimizer is itself an interpretability agent,
  so MAIA-style tools (image edit, exemplar retrieval, summarize)
  should be exposed as functions in the WSP harness.
- Caveat: a general VLM may misread radiographs.
  Validate its descriptions against a radiology encoder (CLEAR)
  and a small radiologist-written checklist.

### 3.2 Dictionary learning and concept models

**D1. SAEs on vision encoders (general).**

- What: train a sparse autoencoder on activations, then read features.
  [Prisma][prisma] ([code][prismacode]) releases SAEs and a hooked ViT.
  [Steering CLIP's ViT with SAEs][clipsae] finds 10% to 15% of
  neurons and features steerable and many more steerable SAE features.
  [Interpretable and Testable Vision Features][itvf] pairs exemplars with
  decoder vectors.
  [Linear structure of VLM embedding spaces][vlmsae] releases SAEs for CLIP,
  SigLIP, SigLIP2 and AIMv2.
  [Archetypal SAE][archsae] addresses instability across training runs.
- Reveals: candidate monosemantic directions, plus an intervention handle.
- Labels: U (trained on unlabeled images; reconstruction loss only).
  Feature naming may use X (a captioner).
- Maturity: medium (many open SAEs, mixed evidence of usefulness).
  [Probing the Representational Power of SAEs][probe-sae] and
  [VS2][vs2] report a reconstruction-vs-task saliency gap:
  features salient for reconstruction need not be those useful for the task.
- Cost: hours to a day on one GPU per layer and encoder.
- WSP use: SAE decoder vectors give the optimizer a basis in which
  "edit" becomes "scale feature 1,204 by 0.3" instead of editing raw weights.
- Gradient note: SAE training is a gradient optimizer.
  It uses no task labels, but it is a conventional training run.

**D2. SAEs on medical and radiology encoders.**

- [SAE-Rad][saerad]: SAEs on a radiology ViT; features compiled into reports.
- [MedSAE][medsae] (ICIP 2026): SAEs on MedCLIP, evaluated on CheXpert.
  Code: github.com/EIDOSLAB/MedSAE.
- [Sparse Autoencoders for Interpretable Medical Image Representation
  Learning][sail] (MICCAI 2026): SAEs on BiomedParse and DINOv3
  embeddings of 909,873 CT and MRI slices.
  Reports recovering up to 87.8% of downstream performance
  with 10 features.
  Code: github.com/pwesp/sail.
- [SAE steering of radiology VLMs][saesteer] (May 2026):
  inference-time SAE steering raised a clinical composite metric by
  5.4% to 17.0% relative on RadVLM, LLaVA-Rad and CheXOne,
  and transferred zero-shot to IU-Xray.
  Feature dashboard released.
- [Matryoshka-SAE on a radiology MLLM][radsaemllm] (arXiv 2507.12950).
- Pathology: [PICASSO][picasso] (bioRxiv 2026) builds a concept atlas
  from 120M patches and manipulates concepts directly.
- Not found: SAEs trained on RAD-DINO or MedSigLIP specifically
  (searches returned none; they may exist unindexed).
- Labels: U for training.
  Evaluation in the cited papers uses reports or labels,
  which would be T in the proposed study if reused.
- WSP use: strongest candidate for the "feature menu" the optimizer reads.
  The 10-feature result suggests a head can sit on a very small
  dictionary subset, which is a small search space for label-sparse
  selection.
- Caveat: the 87.8% figure is relative to the original embedding probe
  and was obtained with labeled downstream training; it does not show
  zero-label performance.

**D3. Transcoders, crosscoders, attribution graphs.**

- What: replace MLPs with sparse approximations to trace computation
  ([transcoders][transcoder]; Anthropic's [circuit tracing][cltrace]).
- Labels: U (language-model training corpora).
- Maturity: high on language models; unproven on vision or radiology
  (no vision application found in this search).
- WSP use: low priority. Cost is high, and ViT-scale replacement models
  are not established.

**D4. Label-free concept bottlenecks and concept decompositions.**

- [Label-free CBM][lfcbm], [LaBo][labo] and [SpLiCE][splice]
  express a CLIP-type embedding as sparse concept scores.
- [CLEAR][clear] (Nature Biomedical Engineering, 2026) is an auditable
  chest X-ray foundation model that scores 368,294 text concepts
  per image and then predicts through them.
  Reported: zero-shot mean AUROC 78.2% on VinDr-CXR
  and 70.0% on PadChest; CheXpert linear-probe mean AUROC 87.0%
  (figures from a secondary summary, not re-verified against the paper).
  Code: github.com/peterhan91/CLEAR; weights on Hugging Face.
- Labels: N for the concept scoring (text only).
  The concept bank itself was built with report supervision (X).
- Maturity: medium on natural images, early on chest X-rays.
- WSP use: gives the optimizer a language-addressable weight surface.
  A head over CLEAR concepts can be written as
  "pneumothorax = pleural line + absent lung markings",
  which is a prior-based head with no target labels.
- Caveat: CLEAR trained on 0.87M image-report pairs from
  public sources; check overlap with the target evaluation set.

### 3.3 Causal and attribution methods

**C1. Ablation, activation patching, attribution patching, path patching.**

- What: replace or zero a unit's activation and measure the effect.
  [Attribution patching][eap] approximates it with gradients.
  [ACDC][acdc] automates edge selection.
  Vision work: [automatic visual circuits][vcirc],
  [edge-based ViT circuits][vitcirc] (2026),
  [patching for ViT attribution][actpatchvit] (2026).
- Reveals: which units are necessary or sufficient for a behavior.
- Labels: U or T.
  Needs a metric; a metric on class logits needs labels,
  but "change in logit under a counterfactual pair" needs only
  paired inputs, for example RadEdit before/after.
- Maturity: high on language models; low to medium on vision;
  unproven on radiology.
- Cost: low (a few forward passes per patch).
- WSP use: verify.
  After the optimizer edits a head,
  patching clean-vs-edited activations shows whether the edit
  changed the intended path.

**C2. Integrated gradients, saliency, TCAV, probes, steering vectors.**

- [TCAV][tcav] measures sensitivity to a concept direction.
  Linear probes and difference-of-means directions
  estimate concept or class directions.
- Labels: concept examples are X or T (the concept needs a few labeled
  positives and negatives), unless concept examples come from synthetic
  probes (S1 to S4), which then are N or X.
- Maturity: high for probes; medium for TCAV in chest X-ray work
  (bias studies; entangled concepts are a known limit).
- Caution: DeGrave et al. found saliency maps
  could fail to localize pathology in COVID-19 CXR models
  ([DeGrave 2021][degrave]), so saliency is weak evidence of mechanism.
- WSP use: a difference-of-means direction is the most direct bridge
  from "I found a concept" to "I wrote a weight".
  It is also the non-LLM baseline that recovered 93% of the Qwen edit
  ([aiXiv][aixiv]).

**C3. Causal scrubbing.**

- What: test a hypothesized circuit by resampling activations
  consistent with the hypothesis (Redwood Research, 2022;
  write-up on the Alignment Forum, not re-fetched).
- Labels: U.
- Maturity: language-model specific; unproven on vision.
- WSP use: low priority; useful only for rigorous claims in a paper.

### 3.4 Direct model and weight editing in vision

**E1. Rewriting prediction rules (Santurkar et al. 2021).**

- [Paper][santurkar] and [code][santurkar-code]:
  edit a layer by rank-one update so that features of one concept
  (for example, "snow") map to those of another ("road").
  Requires almost no new data.
- Labels: N or U (a few exemplar images per concept).
  Fitting the update is a constrained optimization step.
- Maturity: medium (ImageNet-scale ResNets, CLIP).
- WSP use: the closest published analogue of weight-space programming
  in vision. The optimizer can specify (concept A, concept B) pairs
  found by D1 or F3 and let the rank-one solve write the weights.
- Caveat: the closed-form solve is not "direct LLM weight writing".
  Report it as a conventional edit with an LLM-chosen target.

**E2. ViT and classifier editing, 2025 to 2026.**

- [Model editing for Vision Transformers][vitedit] (NeurIPS 2025):
  ViT predictions are influenced more by attention-adjacent modules than
  by MLPs alone, so edits that only target MLPs underperform.
- [Single-weight spurious-correlation neutralization][singleweight]
  (arXiv 2501.14182) and [class vectors][classvec] (arXiv 2510.11268)
  edit classifiers post hoc; the latter names medical imaging as motivation.
- Labels: mostly T or X for the edited examples.
- Maturity: low to medium; benchmarks are natural-image.

**E3. Task arithmetic, model merging, WiSE-FT, model patching.**

- [Task arithmetic][taskarith], [MedMerge][medmerge],
  [Med-LEGO][medlego], [T-cubed test-time merging][t3],
  [WiSE-FT][wiseft] (interpolating zero-shot and fine-tuned weights),
  [model patching][modelpatch].
- Labels: X or T (task vectors come from fine-tuned models).
  A task vector built by fine-tuning on another institution's labels
  is X; on the target site, T.
  T-cubed combines two models at test time without gradients.
- Maturity: high on CLIP; medium on medical imaging.
- WSP use: the optimizer can combine published task vectors
  (for example, a CXR classification model fine-tuned elsewhere) with
  the target backbone by reasoning about which layers to blend.
- Caveat: strong non-LLM baselines exist (uniform or tuned interpolation).

**E4. ROME / MEMIT analogues.**

- [ROME][rome] edits language-model MLP key-value memories.
  There is no accepted vision or radiology analogue found here;
  E1 and E2 are the nearest.
- Maturity: unproven on vision.

**E5. Pruning, neuron surgery, concept-neuron suppression.**

- [SAE feature suppression in CLIP][clipsae] improved performance on
  CelebA, Waterbirds and typographic attacks.
- [Label-free spurious mitigation with SAEs][labelfreesae] (ICLR 2026)
  and [SEM][sem] do SAE-based debiasing without extra labels.
- Labels: U or N (some variants need a text description of the spurious
  concept only).
- Maturity: medium on natural-image benchmarks; unproven in radiology.
- WSP use: if the optimizer finds a feature tied to site, device or
  laterality marker, zero its decoder direction in the head's input.

**E6. Compiling programs into weights (RASP, Tracr) and hand-designed
circuits.**

- [Tracr][tracr] compiles RASP programs into transformer weights.
  The WSP post cites it as one route to writing weights.
- Labels: N.
- Maturity: language-model toy tasks only; no vision compiler.
- WSP use: for radiology, "hand-designed circuit" means hand-set
  convolution filters or head weights from priors
  (for example, a lung-field template or a CLEAR-concept head).
  Existing WSP evidence for from-scratch writing is on games, not images.

**E7. Last-layer reweighting and retraining.**

- [Deep Feature Reweighting][dfr]: retrain only the last layer on a
  group-balanced held-out set; matches or beats complex debiasing.
- Labels: T plus group labels (small set).
- Maturity: high; widely replicated ([follow-up critique][dfr2]).
- Role: this is the conventional baseline to beat for any
  head-only edit, and it is exactly the shape of the pilot in the idea file.

### 3.5 Training dynamics, data attribution and label selection

**T1. Watching features form (Cammarata essay).**

- Nick Cammarata, "Neural Networks Are Already Clean", Goodfire
  ([essay][clean]).
  The date 15 Oct 2026 comes from a secondary summary
  ([bigchange.ai][bigchange]); the fetched page text did not show it.
  A technical paper on the language-model experiments is "still
  forthcoming" per that summary.
- Directly relevant statements in the fetched text:
  "At the time, I hadn't watched neurons grow over training.
  Now it's easier, and it holds up everywhere I've seen."
  and "it's easy to check if you have training checkpoints".
  The vision experiment reduced InceptionV1 layer 3b from 480 to 10
  channels and retrained; neurons "stay interpretable and generalized,
  but coarser".
  Architectural changes (not weight edits) changed the share of
  interpretable last-layer neurons from almost none to 99 to 100%.
- What it supports: observing feature formation across checkpoints
  is practical for small vision networks.
  What it does not show: that formation can be steered by weight edits
  to reduce label need. The steering shown is by architecture and
  regularization choices, then retraining.
- Contested: [bigchange.ai][bigchange] reports a superposition
  objection; the thesis is an informal working hypothesis.
- Labels: whatever the training run uses (X or T).
- WSP use: pipeline P4 below.

**T2. Developmental interpretability and the local learning coefficient.**

- [Hoogland et al. 2024][hoogland] link stagewise development in
  transformers to loss-landscape degeneracy (language and in-context tasks).
  [Timaeus][timaeus] extends this to "susceptibilities".
- Labels: training data labels (X or T).
- Maturity: language models and toy models; unproven on vision.
- WSP use: low for a first study. Could detect when a small head has
  finished forming; not a label saver by itself.

**T3. Data attribution (TRAK, EK-FAC, influence functions).**

- [TRAK][trak] attributes predictions to training examples;
  [Koh and Liang (2017)][koh] influence functions (not re-fetched);
  a 2026 evaluation finds gradient-based attribution degrades
  as the number of supporting documents grows ([EDS-LM][eds]).
- Labels: T (needs trained model and labeled training pool).
- Use for label saving: after a small seed set, rank unlabeled or
  candidate pool items by influence on validation errors.
  That is active learning with a gradient-heavy scorer.
- Maturity: medium on CNNs; costly on ViTs.

**T4. Concept-support data selection and low-budget active learning.**

- [Mind the Tail][tails] (arXiv 2610.21007, Oct 2026):
  SAE concept activations guide sample selection to cover
  under-supported concepts; improves over selection baselines on
  fine-grained, spurious-correlation and general classification.
- [TypiClust][typiclust]: at low budgets, label typical examples
  from clusters of self-supervised embeddings.
- Labels: U for selection; T only for the selected samples.
- Maturity: medium (natural images); unproven on radiology.
- Caveat: selection by prevalence enrichment changes real labeling cost
  (the idea file already flags this).
- WSP use: choose *which* k patients to label.
  Counts as zero labels until labels are requested.

**T5. Slice discovery and hidden stratification.**

- [Domino][domino] finds underperforming slices using cross-modal
  embeddings; [hidden stratification][hidstrat] shows clinically
  meaningful failures in medical imaging.
- Labels: T for errors (needs predictions plus labels).
  A label-free variant uses model uncertainty on U.
- WSP use: moderate; best at the verification stage.

### 3.6 Synthetic and procedural probe sources

Rule: a generative model that was trained with labels or reports
transfers those labels' information (X) into any probe set,
and may share training data with the backbone.

| Source | Modality | Weights | License note |
|---|---|---|---|
| RoentGen | CXR | gated | MIMIC access |
| RoentGen-v2 | CXR | gated | MIT, MIMIC |
| RadEdit | CXR | gated | MSRLA |
| Cheff | CXR | see repo | MIT code |
| CheXGenBench Sana | CXR | open HF | check card |
| MAISI / NV-Generate-CT | CT | open HF | NVIDIA |
| MedSyn / GenerateCT | CT | open | check card |

Details and sources:

- **RoentGen** ([paper][roentgen], [repo][roentgen-gh]):
  text-conditioned CXR latent diffusion.
  Weights are provided to researchers credentialed for MIMIC-CXR.
- **RoentGen-v2** ([card][roentgen2]; arXiv 2508.16783):
  MIT license on the card, with an access gate requiring MIMIC-CXR
  credentials; a 565k-image synthetic dataset is listed.
- **RadEdit** ([card][radedit]; arXiv 2312.12865):
  mask-constrained editing to add or remove findings.
  Weights under MSRLA (research use only);
  trained on MIMIC-CXR, NIH-CXR and CheXpert with labels as text.
  Most directly useful for counterfactual pairs.
- **Cheff** ([arXiv 2303.11224][cheff]): cascaded latent diffusion for
  1-megapixel CXR; repo licensed MIT. Checkpoint license not verified.
- **CheXGenBench** ([repo][chexgen]; arXiv 2505.10496; TMLR 2026):
  benchmark, leaderboard and a released Sana-0.6B CXR checkpoint
  ([card][sana]) plus SynthCheX-75K.
  The benchmark shows large differences in fidelity and privacy
  between generators; select by FID with a radiology encoder.
- **Counterfactual CXR editors**:
  [disease removal and generation][cfxray], [PRISM][prism],
  [XReal][xreal].
  Licenses and checkpoint availability were not verified.
- **CT**: [MAISI / NV-Generate-CT][maisi]
  (HF card points to an NVIDIA community license; a secondary source
  says NVIDIA Open Model License, so verify before use),
  [MedSyn][medsyn], [GenerateCT][gct], [Text2CT weights][t2ct],
  and [MedSegFactory][medsegfactory] (image-mask pairs).
- **Procedural probes**: crops, window and contrast changes,
  rotations, pasted markers, lesion inpainting, laterality flips.
  Labels: N. Trivial to generate. Realism is limited.
- **Unrelated public datasets** (other body parts, other modalities,
  natural images): N for the target task.
  Use to test whether a unit encodes modality or markers
  rather than pathology.

Label accounting for probes:
generating probes is N or X;
but any probe with a "disease present" tag is a synthetic label
that the study must disclose as a prior.
If the evaluation cohort is from MIMIC, CheXpert or NIH,
these generators and RAD-DINO (trained on MIMIC-CXR, CheXpert, NIH-CXR,
PadChest and BRAX per its [card][raddino]) have seen related data.

### 3.7 Agentic and LLM-driven optimization

- **LLM as optimizer.** [OPRO][opro] (prompts); [AIDE][aide]
  (tree search over ML code); [autoresearch][autoresearch]
  (agent edits training code and keeps or discards by validation loss).
  All of these use a validation score as feedback.
  Every validation query uses labels.
- **WSP family.** Post [wsp], audit [clin], reading [read],
  reproduction [aixiv], WeightLoop [wloop], restoration conjecture [wrest],
  commentary [critics] and [audit].
- **Interpretability agents.** MAIA (F5), Anthropic auditing agents,
  Goodfire-style agent teams (mentioned in a
  [MIT Technology Review][mittr] profile; details not verified).
- **AI Scientist (Lu et al. 2024, arXiv 2408.06292)**: not re-fetched here.
- Labels: validation feedback is T. This is the main hidden label channel.
- WSP use: the control loop itself.

### 3.8 Radiology-specific interpretability evidence

- [DeGrave et al. 2021][degrave]: COVID-19 CXR classifiers relied on
  confounders (for example, source-specific markers) rather than pathology.
  Used generative methods and saliency; saliency maps were unreliable.
- [Gichoya et al. 2022][gichoya]: models predict self-reported race from
  CXR even from degraded images.
  This shows backbones carry demographic features
  that a head can pick up.
- [Hidden stratification][hidstrat] and [slice discovery][domino].
- [RadEdit][radedit] explicitly reports use for acquisition,
  manifestation and population shift stress tests.
- [CLEAR][clear] reports concept-level auditing of failure mechanisms
  (for example, atelectasis confounding other findings).
- [SAE steering][saesteer] shows model-specific hallucination features
  in radiology VLMs.

## 4. Summary table

Abbreviations: Lbl = label class; Mat = maturity on vision;
Cost: L low, M medium, H high.

| Tool | Lbl | Mat | Cost |
|---|---|---|---|
| F1 Feature visualization | N | M | L |
| F2 Network Dissection | X | M | L |
| F3 CLIP-Dissect, DnD, LINE | N/U | M | L |
| F4 Exemplar and crop probes | U | H | L |
| F5 MAIA-style agent tools | N/U | M | M |
| D1 SAEs, general vision | U | M | M |
| D2 SAEs, medical | U | L | M |
| D3 Transcoders | U | L | H |
| D4 CBM, SpLiCE, CLEAR | N/X | M | L |
| C1 Patching, EAP, ACDC | U/T | L | L |
| C2 Probes, TCAV, diff-of-means | X/T | H | L |
| E1 Rank-one rule edit | U | M | L |
| E3 Task vectors, merging | X/T | H | L |
| E5 SAE feature suppression | U | M | L |
| E7 DFR last layer | T | H | L |
| T1 Watch features form | X/T | L | M |
| T3 TRAK, influence | T | M | H |
| T4 Concept-support selection | U | M | M |
| S Synthetic probes | N/X | M | M |

## 5. Four candidate WSP pipelines

Common protocol:
the optimizer may run any tool, including training,
but every labeled patient whose information touches editing,
selection or feedback is counted, including validation queries.
Validation on synthetic or proxy data is reported separately.

### P1. Unlabeled-first feature menu with a prior head

1. Diagnose (N, U): train an SAE on unlabeled target-site images
   from a frozen radiology encoder (RAD-DINO or MedSigLIP).
   Name features with exemplars (F4), a radiology VLM and CLEAR scores.
2. Hypothesize (N): from the task description and radiology knowledge,
   the optimizer writes a head over named features
   (for example, "consolidation = opacity + air bronchogram").
3. Edit: write the head weights directly (no fitting).
   Optionally apply label-free steering of the VS2 type.
4. Verify (N or X): test the head on RadEdit counterfactual pairs
   and procedural probes.
   Expected output change is specified before looking at the output.
5. Spend T labels (k = 8 to 128) only to choose between 2 to 5
   candidate heads and to set the decision threshold.
- Gradient note: SAE training is gradient-based
  and must be declared. The head is not.
- Baselines: zero-shot text prototype head, VS2, logistic regression
  on frozen features, SAE features plus logistic regression.
- Why promising: it uses only evidence that exists in the literature
  (medical SAEs, label-free steering, concept banks).
- Failure expectation: if the encoder does not separate the finding,
  no feature menu will help ([wsp][wsp], Gemma result).

### P2. Shortcut audit and surgical edit

1. Diagnose (U): slice discovery on unlabeled target images
   (Domino-style) and SAE features correlated with site, device,
   laterality markers, text burn-in and tubes.
2. Hypothesize: the optimizer lists suspected confounds and the
   expected effect of removing each.
3. Probe (N, X): RadEdit or procedural edits add or remove the confound
   while keeping anatomy fixed; patch activations (C1).
4. Edit: project the confound direction out of the head's input
   or suppress SAE features (E5); optionally rank-one edit (E1).
5. Verify with k labeled patients stratified by site and device;
   report worst-slice performance, not just mean AUROC.
- Motivation: [DeGrave 2021][degrave], [Gichoya 2022][gichoya],
  and the finding in [clin] that confound and shift flaws were visible
  in single units.
- Baselines: DFR (E7), group DRO, fine-tuning on the same k labels.
- Label savings are measured as labels saved to reach a worst-slice
  target, which is a more clinically defensible claim than mean AUROC.

### P3. Label allocation by concept coverage

1. Embed the unlabeled pool (U) with the backbone and an SAE.
2. Select k patients with concept-support selection (T4) plus
   TypiClust-style typical sampling at small k.
3. Label those k patients; fit or edit the head.
4. After a seed round, rank remaining candidates by influence on
   validation error (T3) or by model disagreement.
- This pipeline changes *which* labels are used, not the editor.
  It is the cleanest way to claim "fewer labels" because the
  active-learning baselines are well defined.
- Confound: selection by label prevalence must be priced.
  Report positive and negative counts.
- Risk: it tests the selector, not weight-space programming.
  Include it as a factorial arm, not the headline.

### P4. Watch a small network form, then transfer

1. Train a small network or head on a public proxy task
   (labels X, for example CheXpert findings), saving checkpoints.
2. Track feature formation (T1) with SAE or probe snapshots;
   the optimizer identifies which features form late, collapse,
   or encode shortcuts.
3. Steer the next run: change regularization, depth, curriculum
   or input crops, in the manner of the architecture and regularization
   changes in [clean]. Weight edits are not what is tested.
4. Transfer the resulting features to the target backbone or head with
   k target labels.
- Label class: X for the proxy run; T for the transfer.
- This is the user's "watch neurons grow" affordance.
  It is the least well supported by evidence and the most gradient-heavy.
  Treat it as exploratory.
- Detection and segmentation are easiest to approach here
  (anatomy priors compiled into filters or decoder bias),
  but no published WSP result covers them.

## 6. Risks and confounds

**Hidden gradient optimizers.**
SAE training, task-vector construction, rank-one solves,
TRAK, DFR, logistic regression and "train a small net" all use
gradient or closed-form fitting.
The user's framing allows these, which differs from the idea file's
requirement to define the boundary between direct editing and fitting.
The study should tag every produced weight by method
(hand-written, closed-form, gradient) and report each separately.

**Label leakage through side channels.**

- Validation feedback: each query to a labeled set leaks labels;
  repeated queries overfit even with fixed unique patients
  (the idea file already says this).
- Generative probes: RoentGen, RadEdit and CheXGenBench models
  were trained on labeled or report-paired public CXR data;
  probes carry that supervision (X).
- Pretraining overlap: RAD-DINO, CLEAR and the generators used
  MIMIC-CXR, CheXpert, NIH-CXR and others.
  Do not evaluate on those cohorts or on patients from them.
- LLM priors: [arXiv 2611.08070][read] found Opus 5.5 relies on
  remembered dataset and label order; the optimizer may know public
  CXR datasets and their label sets.
  Use a private or newly curated target set where possible.
- Concept names: a prompt that names the finding supplies prior
  medical knowledge. This is permitted, but it is not a "label",
  so report it as a prior.

**Weak evidence that LLM reasoning is the active ingredient.**

- Difference-of-means recovered 93% of the Qwen gain ([aixiv]).
- A simple statistic found the same flaws as Opus 5.5 ([clin]).
- Opus 5.5's CNN reading is mostly edge arithmetic and priors ([read]).
- Therefore, every WSP arm needs a non-LLM arm using the same tool:
  the same SAE and diff-of-means, with an automated search over layers,
  columns and scales.

**Editing cannot add missing features.**
The WSP post's own Gemma result says editing removed an obstacle
but could not add an ability.
If the backbone does not linearly expose the finding, a head edit
cannot reach good AUROC. A backbone fine-tune would then be required,
which is a different, label-hungry procedure.

**Interpretation tools are unreliable in places.**

- SAE instability across seeds ([Archetypal SAE][archsae]);
- a reconstruction-versus-task gap ([VS2][vs2]);
- top-activation-only neuron descriptions ([evalcvpr]);
- saliency maps that fail to localize pathology ([DeGrave 2021][degrave]);
- a live dispute about whether polysemanticity reflects superposition
  ([essay][clean], [bigchange.ai][bigchange]).
Treat each tool's output as a hypothesis and verify it with a patch
or a counterfactual.

**Statistical issues.**
Small k means high variance. Use repeated label subsets
and patient-level resampling.
The WSP reports are mostly single runs ([read]); do not copy that.
Undisclosed earlier trial runs are a possible selection effect in the
original report according to a secondary audit ([audit]; unverified).

**Synthetic probe realism.**
Diffusion CXRs can contain artifacts and may encode dataset shortcuts;
RadEdit's own card lists unwanted visual changes under editing.
A unit that reacts to a generative artifact is not necessarily using it
on real images.

**Compute.**
SAE training and exemplar retrieval are cheap compared with the
LLM context cost of reading weights. Dense weight reading
does not scale to a ViT; use summaries (singular vectors, SAE features),
as the WSP post's tool-using experiments do.

## 7. Unverified items

- No source found that applies WSP to a real vision model.
- No SAE on RAD-DINO or MedSigLIP found; none on CheXzero found.
- No evidence found on CLIP-Dissect, DnD or MAIA on radiographs.
- CLEAR performance numbers are from a secondary summary.
- Licenses for Cheff, the counterfactual CXR editors, MedSyn and MAISI
  were not read in full.
- Net2Vec, causal scrubbing, Koh and Liang, and the AI Scientist paper
  are cited from memory; IDs are standard but not fetched here.
- Exact date of the Cammarata essay is from a secondary source.
- The secondary blog critiques of WSP were not independently checked.

## 8. Ten most promising tools for label savings

1. **SAEs on a frozen radiology encoder (D1, D2).**
   Trained on U; give a small named basis; steering and suppression
   handles exist; medical SAE code is open.
2. **Concept-bank heads (CLEAR, SpLiCE, label-free CBM).**
   A text-defined head needs no T labels and is auditable.
3. **Difference-of-means and linear directions (C2).**
   Needs very few labels and is the baseline that recovered most of
   the published WSP gain; ideal for k = 8 to 32.
4. **Counterfactual probes (RadEdit, procedural edits).**
   Provide label-free verification of an edit; RadEdit was designed
   for acquisition and manifestation shift tests.
5. **Label-free SAE steering (VS2, SEM, label-free spurious mitigation).**
   Direct competitors that need no labels; they are the right
   non-LLM baselines.
6. **Rank-one rule editing (Santurkar) and SAE feature suppression (E1, E5).**
   The best-defined edit operators in vision; the LLM chooses targets.
7. **Concept-support data selection and TypiClust (T4).**
   Uses U only; saves T labels by choosing them; well-defined baselines.
8. **Exemplar and crop probing with a radiology VLM labeler (F3, F4, F5).**
   Cheap, label-free hypothesis generation; matches the user's listed
   affordances.
9. **Last-layer reweighting (DFR) and slice discovery (E7, T5).**
   Not LLM-based, but the mandatory conventional comparator and a
   small-label shortcut fix.
10. **Task vectors and weight interpolation (E3).**
    Use labels from other sites (X); a strong, cheap competitor for
    site-adaptation tasks; the LLM chooses which layers to blend.

Lower priority for a first study: transcoders, causal scrubbing,
developmental interpretability, TRAK on ViTs, and "watch a small
network form" (T1), because evidence on vision or radiology is weak or
absent, or because the compute and gradient burden is high.

## References

[wsp]: https://rikiyat.github.io/blog/weight-space-programming/
[clin]: https://arxiv.org/abs/2611.05341
[read]: https://arxiv.org/abs/2611.08070
[wloop]: https://arxiv.org/abs/2611.07319
[wrest]: https://arxiv.org/abs/2611.04268
[aixiv]: https://aixiv.science/abs/aixiv.261103.000004
[clean]: https://already-clean.goodfire.com/
[bigchange]: https://bigchange.ai/blog/goodfire-neuron-interpretability-superposition
[mittr]: https://www.technologyreview.com/2026/10/19/1147149/we-were-looking-at-it-wrong-the-explosive-claim-thats-upended-the-ai-world/
[critics]: https://shubham-tripathi.com/blog/weight-space-programming-ii-critics-replications/
[audit]: https://achintyakj.tech/blog/weight-space-audit
[paw]: https://programasweights.com/research/weight-space-programming/
[featvis]: https://distill.pub/2017/feature-visualization/
[zoomin]: https://distill.pub/2020/circuits/zoom-in/
[netdis]: https://arxiv.org/abs/1704.05796
[milan]: https://arxiv.org/abs/2201.11114
[clipdissect]: https://arxiv.org/abs/2204.10965
[falcon]: https://proceedings.mlr.press/v202/kalibhat23a.html
[dnd]: https://lilywenglab.github.io/Describe-and-Dissect/
[line]: https://arxiv.org/abs/2604.08039
[maia]: https://arxiv.org/abs/2404.14394
[maiacode]: https://github.com/multimodal-interpretability/maia/
[bills]: https://openaipublic.blob.core.windows.net/neuron-explainer/paper/index.html
[evalcvpr]: https://github.com/Trustworthy-ML-Lab/Efficient-Interpretability-Eval
[auditagents]: https://alignment.anthropic.com/2025/automated-auditing/
[auditbench]: https://alignment.anthropic.com/2026/auditbench/
[nla]: https://transformer-circuits.pub/2026/nla/
[cafe]: https://arxiv.org/abs/2509.00749
[prisma]: https://arxiv.org/abs/2504.19475
[prismacode]: https://github.com/Prisma-Multimodal/ViT-Prisma
[clipsae]: https://arxiv.org/abs/2504.08729
[itvf]: https://arxiv.org/abs/2502.06755
[vlmsae]: https://arxiv.org/abs/2504.11695
[archsae]: https://proceedings.mlr.press/v267/fel25a.html
[probe-sae]: https://arxiv.org/abs/2508.11277
[vs2]: https://arxiv.org/abs/2506.01247
[saerad]: https://arxiv.org/abs/2410.03334
[medsae]: https://arxiv.org/abs/2510.26411
[sail]: https://arxiv.org/abs/2603.23794
[saesteer]: https://arxiv.org/abs/2605.24977
[radsaemllm]: https://arxiv.org/abs/2507.12950
[picasso]: https://doi.org/10.64898/2026.06.12.731496
[transcoder]: https://arxiv.org/abs/2406.11944
[cltrace]: https://transformer-circuits.pub/2025/attribution-graphs/methods.html
[lfcbm]: https://arxiv.org/abs/2304.06129
[labo]: https://arxiv.org/abs/2211.11158
[splice]: https://github.com/ai4life-group/SpLiCE
[clear]: https://www.nature.com/articles/s41551-026-01741-4
[tcav]: https://arxiv.org/abs/1711.11279
[acdc]: https://arxiv.org/abs/2304.14997
[eap]: https://aclanthology.org/2024.blackboxnlp-1.25/
[vcirc]: https://arxiv.org/abs/2404.14349
[vitcirc]: https://arxiv.org/abs/2604.14477
[actpatchvit]: https://arxiv.org/abs/2603.13652
[santurkar]: https://arxiv.org/abs/2112.01008
[santurkar-code]: https://github.com/madrylab/EditingClassifiers
[vitedit]: https://proceedings.neurips.cc/paper_files/paper/2025/file/6155cfb4e650d41167848fe2ead30ab8-Paper-Conference.pdf
[singleweight]: https://arxiv.org/abs/2501.14182
[classvec]: https://arxiv.org/abs/2510.11268
[labelfreesae]: https://proceedings.iclr.cc/paper_files/paper/2026/hash/359242d225d2fba218a85e147803f8b7-Abstract-Conference.html
[sem]: https://sparse-embedding-modulation.github.io/
[taskarith]: https://arxiv.org/abs/2212.04089
[medmerge]: https://arxiv.org/abs/2403.11646
[medlego]: https://arxiv.org/abs/2503.01164
[t3]: https://arxiv.org/abs/2510.27265
[wiseft]: https://arxiv.org/abs/2109.01903
[modelpatch]: https://arxiv.org/abs/2008.06775
[rome]: https://arxiv.org/abs/2202.05262
[tracr]: https://arxiv.org/abs/2301.05062
[dfr]: https://arxiv.org/abs/2204.02937
[dfr2]: https://arxiv.org/abs/2308.00473
[hoogland]: https://arxiv.org/abs/2402.02364
[timaeus]: https://timaeus.co/research/2026-04-24-patterning-tms
[trak]: https://arxiv.org/abs/2303.14186
[koh]: https://arxiv.org/abs/1703.04730
[eds]: https://arxiv.org/abs/2610.40655
[tails]: https://arxiv.org/abs/2610.21007
[typiclust]: https://arxiv.org/abs/2202.02794
[domino]: https://arxiv.org/abs/2203.14960
[hidstrat]: https://arxiv.org/abs/1909.12475
[roentgen]: https://www.nature.com/articles/s41551-024-01246-y
[roentgen-gh]: https://github.com/StanfordMIMI/RoentGen
[roentgen2]: https://huggingface.co/stanfordmimi/RoentGen-v2
[radedit]: https://huggingface.co/microsoft/radedit
[cheff]: https://arxiv.org/abs/2303.11224
[chexgen]: https://github.com/Raman1121/CheXGenBench
[sana]: https://huggingface.co/raman07/CheXGenBench-Models-Sana-e20
[cfxray]: https://github.com/berkegokmen1/counterfactual-chexray-disease-editing
[prism]: https://github.com/Amarkr1/PRISM
[xreal]: https://github.com/BioMedIA-MBZUAI/XReal
[maisi]: https://huggingface.co/nvidia/NV-Generate-CT
[medsyn]: https://github.com/batmanlab/medsyn
[gct]: https://huggingface.co/generatect/GenerateCT
[t2ct]: https://huggingface.co/dmolino/text2ct-weights
[medsegfactory]: https://github.com/jwmao1/MedSegFactory
[raddino]: https://huggingface.co/microsoft/rad-dino
[opro]: https://arxiv.org/abs/2309.03409
[aide]: https://arxiv.org/abs/2502.13138
[autoresearch]: https://github.com/karpathy/autoresearch
[degrave]: https://www.nature.com/articles/s42256-021-00338-7
[gichoya]: https://www.thelancet.com/journals/landig/article/PIIS2589-7500%2822%2900063-2/fulltext
