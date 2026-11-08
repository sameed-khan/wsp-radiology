import json
import shutil
from pathlib import Path

import pytest

from wsp_harness import prepare as mod


def fixture_data(tmp_path, monkeypatch):
    data = tmp_path / 'data-root'
    alloc = data / 'data/locked/private/allocations/k10/r1'
    alloc.mkdir(parents=True)
    (alloc / 'labels.csv').write_text('image,patient,label\na,p,0\n')
    (alloc / 'allocation.json').write_text('{}')
    (data / 'data/locked/private/hash-corpus.json').write_text('{}')
    pool = data / 'data/pool'
    pool.mkdir()
    (pool / 'a').touch()
    (data / 'models').mkdir()
    (data / 'data/external/extracted').mkdir(parents=True)
    root = tmp_path / 'repo'
    shutil.copytree(mod.REPO / '.pi', root / '.pi')
    monkeypatch.setattr(mod, 'EXPECTED_POOL', 1)
    def command(argv):
        if argv[0] == 'git':
            return '' if 'status' in argv else 'abc'
        if argv[:3] == ['docker', 'image', 'inspect']:
            return json.dumps({'Id': 'sha256:123', 'RepoDigests': []})
        if argv[:2] == ['docker', 'ps']:
            return ''
        if argv[0] == 'nvidia-smi':
            return '23000'
        if argv[0] == 'pi':
            return '{"status":"ready"}'
        raise AssertionError(argv)
    monkeypatch.setattr(mod, '_command', command)
    return root, data


def test_preparation_private_and_only_expected_prompt_diff(tmp_path, monkeypatch):
    root, data = fixture_data(tmp_path, monkeypatch)
    path, report, prompts = mod.prepare(root, 10, 1, 'agent', 'proxy', data)
    assert report['ready']
    assert json.loads(path.read_text()) == report
    labels = Path(report['checks']['labels']['path'])
    assert sorted(p.name for p in labels.iterdir()) == ['labels.csv']
    assert (labels / 'labels.csv').read_bytes() == (data / 'data/locked/private/allocations/k10/r1/labels.csv').read_bytes()
    assert labels.stat().st_mode & 0o777 == 0o700
    assert (labels / 'labels.csv').stat().st_mode & 0o777 == 0o600
    assert path.stat().st_mode & 0o777 == 0o600
    assert '2993' not in prompts['F']
    assert prompts['F'] != prompts['G']
    assert mod.prepare(root, 10, 1, 'agent', 'proxy', data)[0] != path


def test_failed_checks_and_invalid_arguments(tmp_path, monkeypatch):
    root, data = fixture_data(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, '_command', lambda argv: None)
    (data / 'data/pool/b').touch()
    path, report, _ = mod.prepare(root, 10, 1, 'agent', 'proxy', data)
    assert not report['ready']
    for name in ('git_clean', 'n_pool', 'agent_image', 'proxy_image', 'gpu_free', 'no_running_agents', 'anthropic_auth'):
        assert not report['checks'][name]['ok']
    with pytest.raises(ValueError):
        mod.prepare(root, 20, 1, 'agent', 'proxy', data)
    with pytest.raises(ValueError):
        mod.prepare(root, 10, 2, 'agent', 'proxy', data)


def test_unexpected_prompt_difference_is_detected(tmp_path, monkeypatch):
    root, data = fixture_data(tmp_path, monkeypatch)
    original = mod.load_inputs
    from dataclasses import replace
    def load(root, arm):
        obj = original(root, arm)
        return replace(obj, launch_template=obj.launch_template + ' extra') if arm == 'G' else obj
    monkeypatch.setattr(mod, 'load_inputs', load)
    _, report, _ = mod.prepare(root, 10, 1, 'agent', 'proxy', data)
    assert not report['checks']['prompt_diff']['ok']
