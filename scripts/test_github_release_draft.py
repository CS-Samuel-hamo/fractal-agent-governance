#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from github_release_draft_generator import generate  # noqa: E402
from public_docs_leakage_scanner import scan_texts  # noqa: E402
from public_release_packager import VERSION  # noqa: E402
from release_tag_preflight import preflight  # noqa: E402


def test_github_release_draft_generates() -> None:
    generate(ROOT)
    draft = ROOT / 'GITHUB_RELEASE_DRAFT.md'
    artifact = ROOT / '.zoo-agent' / 'public_release' / 'github_release_draft.md'
    assert draft.exists()
    assert artifact.exists()
    text = draft.read_text(encoding='utf-8')
    assert f'AI Project Operator v{VERSION}' in text
    assert f'v{VERSION}' in text
    assert 'Project Map-backed Autopilot' in text
    assert 'This release does not create remote GitHub PRs.' in text
    assert 'No cloud sync or telemetry.' in text


def test_github_release_draft_has_no_unsupported_claims() -> None:
    text = (ROOT / 'GITHUB_RELEASE_DRAFT.md').read_text(encoding='utf-8')
    report = scan_texts({'GITHUB_RELEASE_DRAFT.md': text})
    assert report['safe'] is True, report
    lowered = text.lower()
    assert 'fully autonomous' not in lowered
    assert 'creates remote github prs' not in lowered
    assert 'calls github api' not in lowered


def test_release_tag_preflight_does_not_create_tag_or_push() -> None:
    payload = preflight(ROOT)
    assert payload['tag'] == f'v{VERSION}'
    assert payload['auto_tag_created'] is False
    assert isinstance(payload['suggested_commands'], list)
    tag_check = subprocess.run(['git', 'rev-parse', '--verify', f'v{VERSION}'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if payload['tag_exists'] is False:
        assert tag_check.returncode != 0


def main() -> None:
    test_github_release_draft_generates()
    test_github_release_draft_has_no_unsupported_claims()
    test_release_tag_preflight_does_not_create_tag_or_push()
    print('github release draft tests passed')


if __name__ == '__main__':
    main()
