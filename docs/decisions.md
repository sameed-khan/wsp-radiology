# Investigator decisions

These are accepted design decisions, not claims that the corresponding
controls have already been implemented. No experimental session has started.

## ADR-001: unrestricted F/G experimentation with protected audit records

**Status:** accepted by the investigator, 2026-11-08.

### Decision

Retain unrestricted experimentation within the study's label, leakage,
network, time, compute and arm-specific rules. Do not require final models
to be produced through a restricted fitting/editing service.

Arm F is prohibited from directly writing model weights; arm G is permitted
to do so. Both can write training code and use conventional fitting and
optimization. The manipulation concerns permission to edit weights directly,
not whether an LLM proposed a training algorithm.

Enforce the integrity of the evidence boundary instead: agents and their
subagents must have **no write access** to authoritative Pi session history,
audit records, trusted harness code/configuration, or the recorder. They
must not be able to delete, replace, truncate, redirect or disable those
records through their writable workspace. The preferred implementation is
a trusted supervisor/recorder outside the writable execution sandbox,
with agent commands executing in the sandbox. Merely setting a log-file
permission while leaving its parent directory or recorder writable is
insufficient. Do not mount host session/authentication directories or the
Docker socket into agent workspaces. Agent-local logs are supplementary,
not authoritative. The agent may modify experimental code, not the trusted
harness running or recording the experiment.

### Required evidence and audit

- Retain the complete persisted Pi event/session history, including tool
  arguments/results, all branches, interventions and compaction events;
  retain the underlying entries, not only a compacted summary or HTML view.
- Preserve experiment definitions, actual launch settings and model IDs,
  timing/resource accounting, proxy records and external-source inventory.
- Preserve executed experimental script versions where captured and
  start/checkpoint/end workspace snapshots or diffs. A command naming a
  script is not itself a copy of the script's contents at execution time.
- Record checkpoint hashes, parent/operation lineage and available
  tensor-level change information. Distinguish direct LLM-prescribed edits,
  closed-form fitting and gradient training; retain mixed ancestry rather
  than overwriting it with the final operation's tag. Mark unsupported or
  ambiguous attributions as unknown, not as proven.
- Instrument ordinary training/editing helpers, but do not treat their
  self-generated logs alone as authoritative under arbitrary shell access.
- Seal completed evidence with hashes in a host-owned receipt, archive
  reviewed evidence through DVC, and link it to the code/protocol revision.
  Hashes support integrity checking; they do not by themselves prevent
  someone who can rewrite both a log and its receipt from tampering.
- Audit arm F for prohibited edits and both arms for label/network/resource
  violations. An established prohibited direct edit invalidates an F run;
  insufficient evidence or unresolved provenance is reported explicitly and
  must not silently receive a clean audit verdict.

### Scope of the guarantee

Protected records support a trustworthy history of interactions handled by
the trusted Pi harness. They are not a complete operating-system execution
trace, a record of private model reasoning, or a mathematical proof of the
origin of every parameter. A shell call can run subprocesses, downloaded
code or many tensor operations without each becoming a separate Pi tool
call; tool output may also be truncated unless captured separately.
Final-weight provenance is therefore **audited**, not strictly enforced by
a restricted model-write API. The recorder's isolation and event completeness
must be tested before launch. Agent copies of a transcript are not enough.

### Implementation status

Not yet implemented as a complete agent-launch/audit system. Current Docker
code is an offline containment fixture only. This decision does not remove
the plan's required network controls, red team, label isolation or audit.

## Other accepted preparation decisions

- Use Docker instead of Podman, with a trusted host daemon and hardened
  nonroot experiment containers; do not claim rootless isolation if absent.
- Use the release's 1,484 patient identifiers (993 train, 491 test), retaining
  the official split and documenting the paper's 1,482-patient discrepancy.
- The investigator checked the source site and confirmed a posting date of
  2026-07-18. Record that attestation alongside the conflicting historical
  API metadata rather than silently removing the latter.
- At k=0, target-supervised methods that require labels are not applicable.
  Applicable zero-shot methods use no target-label tuning and a
  preregistered fixed threshold. Exact arm recipes still need definition.
- The investigator confirmed MURA use for this research. This does not by
  itself establish an additional third-party API permission or settle
  SKELEX derivative redistribution rights.
- The investigator rebooted successfully. Host and Docker GPU visibility
  were subsequently verified; ML training validation remains separate.

## ADR-002: Haiku-only subagents for F/G and orchestrator role

**Status:** accepted by the investigator, 2026-11-08.

- F and G agents may spawn an unlimited number of subagents, but subagents
  must be `anthropic/claude-haiku-5-5` only. The model is hard-coded in the
  trusted harness tool; agents cannot select another model. Subagents may
  not spawn further subagents (one level only). Concurrency is capped
  identically for F and G (8 concurrent children) to protect shared API
  limits; total count is unlimited.
- Subagents execute in the same session container, obey the same rules
  (F's prohibition of direct weight writes applies to F's subagents) and
  their complete histories are recorded host-side under ADR-001. Images
  read by subagents are logged as LLM-derived labels.
- The orchestrator (parent Pi session talking to the investigator) does not
  execute F/G work; it builds/freezes the harness, launches, monitors,
  resolves infrastructure blockers without task advice, freezes, evaluates
  and audits. Opus 5.5 agents perform the F/G work.
- Cost reporting: per-session token usage and API-equivalent cost from Pi
  session records (parent + subagents), reported as list-price estimates
  (`totalFromProvider: false`; access is subscription OAuth), with the price
  table archived.

## ADR-003: Anthropic implementation models after OpenAI usage limit

**Status:** accepted by the investigator, 2026-11-08.

- After the OpenAI subscription usage limit stopped GPT-6.1-Terra/Sol lanes,
  remaining implementation is done by Claude Sonnet 5.5 (medium effort)
  subagents; simple code, execution and long-running jobs by Claude Haiku 5.5
  (high effort). Independent code review is waived for the remaining work
  by investigator decision; this must be reported as a limitation. Code
  written before the switch keeps its recorded Sol review status (L1, L4e
  reviewed with fixes pending/applied; L2/L3 partial, unreviewed).
- The investigator accepts the risk that Anthropic subscription usage limits
  may interrupt F/G sessions; such stalls are logged as infrastructure
  interruptions and handled identically for F and G.
- Work proceeds up to launch readiness; F/G launch requires the
  investigator's explicit go-ahead.
- Amendment (same day): OpenAI models became available again; per the
  investigator, implementation resumes on OpenAI models (GPT-6.1-Terra),
  Opus 5.5 remains the F/G agent model, and all non-F/G arms are completed
  before F/G launch.

## ADR-004: Precomputed label-free SAEs provided to F and G

**Status:** accepted by the investigator, 2026-11-08.

To keep the 24-hour F/G windows focused on the manipulated variable rather than on
tooling setup, both arms receive the same precomputed sparse autoencoders, trained
without labels on pool patch tokens with the arm E recipe: SKELEX at layers 8/12/16/20
and MedSigLIP/DINOv3 at their 2/3-depth layer, with pool mean latent activations and
quality statistics. No test-set data are included. The launch prompt gains one
identical sentence; agents may ignore them or train their own. This slightly steers
both arms toward SAE-based workflows (plan §7.3 already lists SAE tooling).

## ADR-005: Deadline extensions for API rate-limit downtime (standing rule)

**Status:** accepted by the investigator, 2026-11-10.

Any F/G session time lost to provider rate limiting or usage-limit errors is added
back to that session's deadline. The supervisor measures each outage (from the first
rate-limit failure until the next successful model event), extends that session's
deadline by the measured duration, logs it as an automatic infrastructure event and
sends the agent a fixed, preregistered notice with the new deadline (no task advice).
The k=10 sessions launched 2026-11-10 lost about 2.5 h each (18:26 to ~20:55 UTC) and
are extended retroactively by their measured outages.

## ADR-006: Arm G mandates direct weight editing (future launches)

**Status:** accepted by the investigator, 2026-11-11.

After the k=10 pair, arm G had made no direct weight edits despite permission, so
the G-F contrast measured nothing about weight-space programming. The investigator
changed arm G's definition and weight sentence to REQUIRE at least one kept,
documented, interpretability-derived direct edit that improves the model on the
labeled patients. Arm F is unchanged (direct edits prohibited). This changes the
manipulation from "permission" to "requirement" and applies only to launches after
this decision: the completed k=10 pair and the in-progress k=50 pair (launched
2026-11-10T22:04Z under tag `phase1-launch-freeze-k50`) keep their original
prompts and are not re-run now; a re-run is a later investigator decision. Any
supervisor adoption/restart of the in-progress k=50 G run must use the tagged
input files (its launch hashes reference them).
