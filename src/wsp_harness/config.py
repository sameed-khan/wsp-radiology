"""Load and freeze the preregistered supervisor inputs.

This module does not launch sessions. In particular, loading configuration is
not evidence that the sandbox or recorder has been validated.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping

import yaml

TOOLS = frozenset({'read', 'write', 'edit', 'bash', 'web_search', 'subagent', 'subagent_result'})
FIELDS = frozenset({'arm', 'k', 'start_utc', 'deadline_utc', 'now_utc', 'remaining', 'n_pool', 'weight_sentence'})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(template: str, values: Mapping[str, object]) -> str:
    """Replace only documented tokens, preserving unrelated literal braces."""
    missing = {name for name in FIELDS if '{' + name + '}' in template and name not in values}
    if missing:
        raise ValueError(f'missing prompt values: {sorted(missing)}')
    return re.sub(r'\{(' + '|'.join(sorted(FIELDS)) + r')\}',
                  lambda m: str(values[m.group(1)]), template)


@dataclass(frozen=True)
class Inputs:
    model: str
    thinking: str
    tools: tuple[str, ...]
    system_prompt: str
    launch_template: str
    continuation_template: str
    weight_sentence: str
    hashes: dict[str, str]


def pi_argv(inputs: Inputs, repo: Path, recorder: Path) -> list[str]:
    """Construct the explicit host Pi argv, never a shell command."""
    extensions = repo.resolve() / 'harness' / 'pi-ext'
    return [
        'pi', '--mode', 'rpc', '--model', inputs.model, '--thinking', inputs.thinking,
        '--session-dir', str((recorder / 'sessions').resolve()), '--no-extensions',
        '-e', str(extensions / 'container-tools.ts'),
        '-e', str(extensions / 'subagents.ts'),
        '-e', str(extensions / 'web-search.ts'),
        '--no-skills', '--no-context-files', '--no-prompt-templates', '--no-themes',
        '--no-mcp', '--tools', ','.join(inputs.tools),
        '--append-system-prompt', inputs.system_prompt,
    ]


def load_inputs(root: Path, arm: str, *, allow_test_model: bool = False) -> Inputs:
    arm = arm.upper()
    if arm not in {'F', 'G'}:
        raise ValueError('arm must be F or G')
    paths = {
        'arm': root / '.pi' / 'agents' / f'wsp-arm-{arm.lower()}.md',
        'launch': root / '.pi' / 'prompts' / 'wsp-launch.md',
        'continue': root / '.pi' / 'prompts' / 'wsp-continue.md',
        'weights': root / '.pi' / 'prompts' / 'weight-sentences.json',
    }
    raw = {name: path.read_bytes() for name, path in paths.items()}
    definition = raw['arm'].decode('utf-8')
    match = re.fullmatch(r'---\s*\n(.*?)\n---\s*\n(.*)', definition, re.DOTALL)
    if not match:
        raise ValueError('arm definition must have YAML frontmatter')
    front = yaml.safe_load(match.group(1))
    if not isinstance(front, dict):
        raise ValueError('arm frontmatter must be a mapping')
    model, thinking, tools = (front.get(k) for k in ('model', 'thinking', 'tools'))
    allowed_models = {'anthropic/claude-opus-5-5'}
    if allow_test_model:
        allowed_models.add('anthropic/claude-haiku-5-5')
    if model not in allowed_models:
        raise ValueError('unsupported parent model')
    if thinking not in {'off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'}:
        raise ValueError('invalid thinking level')
    if isinstance(tools, str):
        tools = [part.strip() for part in tools.split(',')]
    if not isinstance(tools, list) or not tools or any(not isinstance(t, str) or t not in TOOLS for t in tools):
        raise ValueError('tools must be an explicit safe allowlist')
    if len(set(tools)) != len(tools):
        raise ValueError('duplicate tool in allowlist')
    weights = json.loads(raw['weights'])
    if not isinstance(weights, dict) or not isinstance(weights.get(arm), str) or not weights[arm].strip():
        raise ValueError('missing weight sentence')
    return Inputs(model, thinking, tuple(tools), match.group(2),
                  raw['launch'].decode('utf-8'), raw['continue'].decode('utf-8'),
                  weights[arm], {name: digest(data) for name, data in raw.items()})
