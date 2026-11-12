from pathlib import Path

import pytest

from wsp_harness.config import load_inputs

ROOT = Path(__file__).resolve().parents[1]


def test_redteam_inputs_load_with_opus_and_no_weight_sentence():
    inputs = load_inputs(ROOT, 'R')
    assert inputs.model == 'anthropic/claude-opus-5-5'
    assert inputs.weight_sentence == ''
    assert 'MFXR' in inputs.launch_template
    assert set(inputs.tools) <= {'read', 'write', 'edit', 'bash', 'web_search', 'subagent', 'subagent_result'}


def test_redteam_test_model_is_haiku():
    assert load_inputs(ROOT, 'R', allow_test_model=True).model == 'anthropic/claude-haiku-5-5'


def test_unknown_arm_rejected():
    with pytest.raises(ValueError):
        load_inputs(ROOT, 'X')


def test_parent_model_override_allowlist():
    assert load_inputs(ROOT, 'F', model_override='anthropic/claude-fable-5-2').model == 'anthropic/claude-fable-5-2'
    assert load_inputs(ROOT, 'F').model == 'anthropic/claude-opus-5-5'
    with pytest.raises(ValueError):
        load_inputs(ROOT, 'F', model_override='anthropic/claude-haiku-5-5')
