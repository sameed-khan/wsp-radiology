import hashlib
import shutil
from pathlib import Path

import pytest

from wsp_harness.config import load_inputs, pi_argv, render

FIXTURE = Path(__file__).parent / 'fixtures' / 'harness'


def test_load_test_only_inputs_and_hashes():
    cfg = load_inputs(FIXTURE, 'f', allow_test_model=True)
    assert cfg.model == 'anthropic/claude-haiku-5-5'
    assert 'subagent' in cfg.tools
    assert cfg.hashes['arm'] == hashlib.sha256((FIXTURE / '.pi/agents/wsp-arm-f.md').read_bytes()).hexdigest()
    assert cfg.weight_sentence == 'Do not directly write weights.'
    with pytest.raises(ValueError, match='model'):
        load_inputs(FIXTURE, 'F')


def test_pi_argv_is_explicit_and_keeps_system_prompt_as_one_argument(tmp_path):
    cfg = load_inputs(FIXTURE, 'F', allow_test_model=True)
    argv = pi_argv(cfg, tmp_path, tmp_path / 'recorder')
    assert argv[:3] == ['pi', '--mode', 'rpc']
    assert argv.count('-e') == 3
    assert '--no-mcp' in argv and '--no-extensions' in argv
    assert argv[argv.index('--append-system-prompt') + 1] == cfg.system_prompt
    assert argv[argv.index('--tools') + 1] == ','.join(cfg.tools)


def test_render_only_documented_tokens():
    assert render('literal {"key": 1}; {arm} {k}', {'arm': 'F', 'k': 10}) == 'literal {"key": 1}; F 10'
    with pytest.raises(ValueError, match='missing prompt values'):
        render('{remaining}', {})


def test_reject_unsafe_tool(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / 'inputs')
    path = tmp_path / 'inputs/.pi/agents/wsp-arm-f.md'
    path.write_text(path.read_text().replace('subagent_result', 'codemode'))
    with pytest.raises(ValueError, match='allowlist'):
        load_inputs(tmp_path / 'inputs', 'F', allow_test_model=True)
