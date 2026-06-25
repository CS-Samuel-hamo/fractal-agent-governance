#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from demo_fixture_packager import ensure_demo_fixture
from public_alpha_packager import write_manifest
from public_docs_leakage_scanner import scan_project, scan_texts


def test_public_docs_are_safe() -> None:
    ensure_demo_fixture(ROOT)
    write_manifest(ROOT)
    report = scan_project(ROOT)
    assert report['safe'] is True, report
    assert report['secret_leak_detected'] is False, report
    assert report['absolute_path_leak_detected'] is False, report
    assert report['unsupported_claim_detected'] is False, report


def test_scanner_detects_absolute_local_path() -> None:
    report = scan_texts({'README.md': 'Open C:\\Users\\person\\private\\project.txt'})
    assert report['absolute_path_leak_detected'] is True, report
    assert report['safe'] is False, report


def test_scanner_detects_secret_marker() -> None:
    fake_token = 'ghp_' + ('4' * 36)
    report = scan_texts({'README.md': f'token {fake_token}'})
    assert report['secret_leak_detected'] is True, report
    assert report['safe'] is False, report


def test_scanner_detects_unsupported_github_claim() -> None:
    report = scan_texts({'README.md': 'This tool creates remote PRs for you.'})
    assert report['unsupported_claim_detected'] is True, report
    assert report['safe'] is False, report


def test_demo_fixture_has_no_leaks() -> None:
    manifest = ensure_demo_fixture(ROOT)
    assert manifest['safe_to_use'] is True, manifest
    demo_root = ROOT / 'examples' / 'demo_project'
    assert not (demo_root / '.env').exists()
    texts = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding='utf-8-sig', errors='replace')
        for path in demo_root.rglob('*')
        if path.is_file()
    }
    report = scan_texts(texts)
    assert report['safe'] is True, report


def main() -> None:
    test_public_docs_are_safe()
    test_scanner_detects_absolute_local_path()
    test_scanner_detects_secret_marker()
    test_scanner_detects_unsupported_github_claim()
    test_demo_fixture_has_no_leaks()
    print('public docs safety tests OK')


if __name__ == '__main__':
    main()
