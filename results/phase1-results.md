# Phase 1 pilot results (MFXR, locked test set) — 2026-11-11

Aggregate, disclosure-safe summary. Locked test set: 1,593 images / 491 patients (62.7 % positive images).
Image-level AUROC with 95 % CIs from 2,000 patient-cluster bootstrap replicates (nested over resamples
where applicable). Per-image results, run evidence and audits are private (`data/locked/private/`,
`runs/`, sealed `artifacts/runs/`). One resample per F/G/G2 cell, so intervals cover test-patient
variation only, not label-sampling or agent-run variation (plan §8.3).

## Agent arms (resample-1 labeled patients; Opus 5.5 medium; Haiku 5.5 subagents)

| Run | k | Test AUROC | Patient AUROC | Sens / Spec at own threshold | Brier | Own CV estimate | Direct edits kept |
|---|---|---|---|---|---|---|---|
| F | 10 | 0.599 [0.559, 0.639] | 0.534 | 0.65 / 0.48 | 0.266 | 0.92 (LOPO, 25 images) | none (prohibited) |
| G | 10 | 0.758 [0.730, 0.785] | 0.744 | 0.64 / 0.72 | 0.210 | 0.87 | **none** (permitted, unused) |
| G2 | 10 | 0.659 [0.620, 0.697] | 0.640 | 0.62 / 0.64 | 0.243 | 0.88 | attention-head ablation (block 12, head 13) + calibration bias |
| F | 50 | 0.868 [0.841, 0.892] | 0.891 | 0.80 / 0.77 | 0.159 | 0.98 | none (prohibited) |
| G | 50 | 0.892 [0.865, 0.916] | 0.889 | 0.87 / 0.73 | 0.147 | 0.99 | **none** (permitted, unused) |
| G2 | 50 | 0.866 [0.839, 0.890] | 0.893 | 0.81 / 0.78 | 0.157 | 0.99 | model soup + 2x consensus task-vector amplification |

G2 = arm G re-run with the ADR-006 mandate (direct edit required; weight-space-programming background
and link). G2 ran after F/G under different timing/rate-limit conditions (ADR-006 amendment).

### Paired differences (same test patients)

| Contrast | ΔAUROC [95 % CI] |
|---|---|
| G − F, k=10 | **+0.159 [0.121, 0.195]** |
| G − F, k=50 | **+0.024 [0.019, 0.030]** |
| G (no test-time crop-group smoothing) − F, k=50 | +0.009 [0.005, 0.014] |
| G2 − F, k=10 | +0.060 [0.013, 0.105] |
| G2 − F, k=50 | −0.002 [−0.015, 0.011] |
| G2 − G, k=10 | −0.099 [−0.132, −0.067] |
| G2 − G, k=50 | −0.026 [−0.040, −0.013] |

### Effect of the agents' own choices (ablations of frozen submissions)

| Ablation | ΔAUROC [95 % CI] |
|---|---|
| G k=50: with − without test-time crop-group smoothing | +0.015 [0.013, 0.018] |
| G2 k=10: with − without the head-ablation edit (same head) | −0.019 [−0.032, −0.006] |
| G2 k=50: amplified (λ=2) − plain soup (λ=1) | +0.018 [0.012, 0.024] |

Ablation threshold/calibration metrics are not meaningful (fitted to the edited model); AUROC only.

## Comparator arms (best per k; nested mean over 5 resamples, resample-1 value in parentheses)

| k | Best arms (test AUROC) |
|---|---|
| 0 | D-ft SKELEX 0.900; D-ft DINOv3 0.879; D-head 0.79; H 0.46–0.52 |
| 10 | **D-ft SKELEX 0.911** (r1 only); D-ft DINOv3 0.887; D-head 0.79–0.81; H SKELEX 0.729; B-lora 0.64–0.68; A 0.57–0.62 |
| 50 | **D-ft SKELEX 0.913**; D-ft DINOv3 0.892; H 0.85–0.87 (r1 0.85); B-lora 0.83–0.84; A 0.79–0.80 |
| 250 | H SKELEX 0.947; D-ft SKELEX 0.943; B-lora 0.91–0.92; A 0.86–0.88 |
| all | H DINOv3 0.977; D-ft 0.976; B-lora 0.966–0.974; B-full 0.89–0.93; A 0.89–0.93 |

Arm E (scripted SAE/difference-of-means) was weak at every k (≤ 0.71). D-ft has one resample (r1).
AUROC target (larger of B-full/B-lora mean at k=all, minus 0.02): 0.974 − 0.02 = **0.954**; reached by
H/D-ft/B-lora only at k=all. G vs D-ft SKELEX (same labeled patients): k=10 −0.153 [−0.176, −0.129];
k=50 −0.022 [−0.047, 0.002].

## Sensitivity and audits

- Overlap sensitivity: excluding the 7 test images with an external-dataset pHash match ≤ 4 (all
  inspected pairs were adult MURA shoulder/forearm images, i.e. pHash false positives) changes no
  AUROC by more than 0.002.
- Other-fracture-control subgroup: not estimable (no subgroup annotations).
- F provenance audit (independent GPT-6.1-Sol, read-only): both F runs clean; no prohibited direct
  edit established. Notes: incomplete provenance entries (calibration config at k=10; teacher ancestry
  at k=50). F k=10's prior-matching intercept is numerically solved (statistical), not hand-set.
- No denylisted source use found; proxy blocked MFXR routes in validation; one real pre-launch leak
  (pool file-ordering side channel) was found by the validation agent and fixed before any F/G run.
- G k=50 used label-free transductive test-time smoothing (SIFT crop-group matching across test
  images); reported with and without.

## Resources (API-equivalent list prices; subscription OAuth, `totalFromProvider=false`)

| Run | Wall clock | Rate-limit outage credited | Opus $ | Haiku $ | Total $ | Haiku subagents | GPU busy h (est.) |
|---|---|---|---|---|---|---|---|
| F k10 | 3.8 h | 0 (stall before ADR-005, ~2.5 h) | 16.20 | 0.32 | 16.52 | 4 | 0.4 |
| G k10 | 4.4 h | 0 (stall before ADR-005, ~2.5 h) | 24.26 | 0.12 | 24.38 | 7 | 1.5 |
| F k50 | 11.9 h | 2.9 h | 14.68 | 14.28 | 28.96 | 53 | 4.1 |
| G k50 | 11.9 h | 2.9 h | 20.71 | 46.86 | 67.57 | 52 | 6.0 |
| G2 k10 | 1.5 h | 0.6 h | 28.35 | 1.07 | 29.42 | 11 | 0.1 |
| G2 k50 | 2.9 h | 0.6 h | 13.97 | 5.39 | 19.36 | 30 | 1.7 |

Every agent session ended voluntarily (FINAL) far before its 24-hour budget (≈1–9 working hours).
No orchestrator task advice was given; interventions were infrastructure notes only.

## Plan §2 outcome levels and §10 gate

- Level 1 / 2 (G at k ≤ 10 ≥ B with all labels): **not met** (0.758 vs 0.974).
- Level 3 (G reaches 0.954 at ≤ half the k of the best comparator): **not met** (G never reaches it).
- Level 4 (G better than best of A–F, H at the same k): **not met** (D-ft exceeds G at k=10 and k=50).
- §10 gate as literally preregistered (G > F in AUROC at ≥ 1 k; no denylist use by G): **formally met**
  (k=10 +0.159, k=50 +0.024). **However the original G made no direct weight edits**, so the G–F gap
  reflects run-to-run agent variation (and, at k=50, partly test-time smoothing), not weight-space
  programming. With direct edits mandated (G2), there is no robust gain over F (k=10 +0.060, wide CI,
  driven by F k=10's poor run; k=50 −0.002), and G2 underperforms the unconstrained G at both k.
  Of G2's kept edits, the interpretability-derived head ablation lowered test AUROC (−0.019) and the
  weight-averaging/task-vector amplification raised it (+0.018).
- Per plan §10, with one resample per k the recommended next step if the gate is in doubt is more
  resamples/budgets in Phase 1 before deciding on Phase 2.

## Fable-G2 (ADR-007 amendment; added 2026-11-12)

Arm G with the ADR-006 edit mandate, parent model Claude Fable 5.2 (medium), resample-1 labels.
Per the investigator, no per-edit reversion ablations were run (quick read only).

| Run | k | Test AUROC | Patient AUROC | Sens / Spec | Kept direct edits | Also in submission |
|---|---|---|---|---|---|---|
| Fable-G2 | 10 | **0.892 [0.863, 0.917]** | 0.871 | 0.80 / 0.82 | SAE-derived "mesh-cast" neuron inserted as extra logit branch; hand-set head rescale | own reads of ~2,100 pool images; LoRA ×3 encoders; crop-link logit averaging |
| Fable-G2 | 50 | 0.836 [0.804, 0.865] | 0.871 | 0.79 / 0.72 | SKELEX last-block attention-output ablation | frozen 3-encoder probes + co-training; crop-group averaging |

| Contrast (paired) | k=10 ΔAUROC | k=50 ΔAUROC |
|---|---|---|
| Fable-G2 − Opus G2 | **+0.232 [0.197, 0.270]** | −0.030 [−0.047, −0.015] |
| Fable-G2 − Opus F | +0.293 [0.251, 0.332] | −0.032 [−0.043, −0.022] |
| Fable-G2 − Opus G | +0.134 [0.112, 0.155] | −0.056 [−0.067, −0.046] |
| Fable-G2 − D-ft SKELEX (r1) | −0.019 [−0.040, 0.001] | −0.078 [−0.108, −0.050] |

Excluding the 7 overlap images changes no estimate by more than 0.002.
