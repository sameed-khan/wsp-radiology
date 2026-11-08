import hashlib
import json

import pytest


@pytest.fixture
def sae_fixture(tmp_path):
    package = tmp_path / 'data/agent-sae/current'
    package.mkdir(parents=True)
    (package / 'README.md').write_text('pool-only SAE fixture\n')
    digest = hashlib.sha256((package / 'README.md').read_bytes()).hexdigest()
    (package / 'manifest.json').write_text(json.dumps({'README.md': digest}))
    return package
