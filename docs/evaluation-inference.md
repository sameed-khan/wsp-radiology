# F/G locked inference

After freeze, pass the final snapshot's **workspace** directory (not the live
workspace) to the orchestrator-only command:

```sh
uv run wsp-eval infer --workspace runs/R/snapshots/S/workspace \
  --image wsp-agent:toolkit-step1 --run-id R \
  --out /home/skhanxx8/projects/wsp-radiology/data/locked/private/runs/fg/R
```

Defaults are the main checkout's private `test-png` and `test-manifest.json`,
and its `models` directory. `--images`, `--manifest`, and `--models` override
those paths for synthetic testing. The output must be under the private runs
tree and must not already contain `inference-output`. The predictor receives
only the read-only frozen workspace, test images and models, and a writable
private output directory; it cannot access labels or the host network. It must
write `image,prob` CSV rows and the frozen model must provide
`output/model/threshold.json` with numeric `threshold` in [0,1]. The command
then invokes locked scoring and writes `private-results.json` and the aggregate
`summary.json`. Missing predictions are flagged as evaluation failures.

The container uses GPU 0, a 3-hour timeout and a five-second host-side GPU
memory poll; exceeding 11 GiB terminates the entire container and fails the
evaluation. This is not a hardware partition: short-lived excess can go
unobserved. Docker, the NVIDIA runtime, and the image tag are trusted host
components. The command does not verify that the supplied workspace is a
final snapshot or verify its manifest; the orchestrator must do that before
scoring. If inference fails, remove or move the incomplete private output
before retrying. Independent code review was waived.

Run synthetic live acceptance (no real test images or labels):
`WSP_LIVE=1 uv run --extra test pytest -q tests/test_eval_inference_live.py`.
