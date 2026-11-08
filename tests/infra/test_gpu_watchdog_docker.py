"""Live GPU watchdog check; requires Docker, an NVIDIA GPU, gcc, and ubuntu:24.04."""
import json
import subprocess
import time
import uuid

import pytest

from infra import gpu_watchdog


@pytest.mark.docker
def test_gpu_watchdog_kills_cuda_allocator(tmp_path):
    source = tmp_path / "allocator.c"
    binary = tmp_path / "allocator"
    source.write_text('''
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>
int main(void) {
    void *h = dlopen("libcuda.so.1", RTLD_NOW);
    if (!h) return 1;
    int (*init)(unsigned) = dlsym(h, "cuInit");
    int (*device)(int *, int) = dlsym(h, "cuDeviceGet");
    int (*context)(void **, unsigned, int) = dlsym(h, "cuCtxCreate_v2");
    int (*alloc)(unsigned long long *, size_t) = dlsym(h, "cuMemAlloc_v2");
    int d; void *c; unsigned long long p;
    if (!init || !device || !context || !alloc || init(0) || device(&d, 0) ||
        context(&c, 0, d) || alloc(&p, 64 * 1024 * 1024)) return 2;
    puts("allocated"); fflush(stdout); sleep(120); return 0;
}
''')
    subprocess.run(["gcc", "-o", str(binary), str(source), "-ldl"], check=True)
    # Docker must be able to traverse pytest's host-side temporary directories.
    # Bind-mount the file directly, so container access does not depend on them.
    name = "wsp-gpu-test-" + uuid.uuid4().hex[:12]
    try:
        subprocess.run(["docker", "run", "-d", "--name", name, "--gpus", "device=0",
                        "--mount", f"type=bind,src={binary},dst=/allocator,readonly",
                        "ubuntu:24.04", "sh", "-c", "/allocator & wait"], check=True, capture_output=True)
        for _ in range(30):
            output = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
            if "allocated" in output.stdout:
                break
            time.sleep(1)
        else:
            pytest.fail("CUDA allocator did not start: " + output.stderr)
        container_id = gpu_watchdog._run("docker", "inspect", "--format", "{{.Id}}", name).strip()
        log = tmp_path / "events.jsonl"
        gpu_watchdog.poll({name: (container_id, 0.001)}, log, True)
        events = [json.loads(line) for line in log.read_text().splitlines()]
        assert any(e["event"] == "violation" and e["memory_mib"] >= 64 for e in events)
        for _ in range(30):
            state = gpu_watchdog._run("docker", "inspect", "--format", "{{.State.Running}}", name).strip()
            if state == "false":
                break
            time.sleep(1)
        else:
            pytest.fail("allocator container remained running after violation")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
