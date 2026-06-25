#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_privacy_filter import filter_artifact, write_privacy_report


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='agent-learning-privacy-') as tmp:
        workspace = Path(tmp)
        artifact = workspace / 'session_history.json'
        payload = {
            'token': 'token=FAKE_TOKEN_12345',
            'owner': 'person@example.com',
            'path': r'C:\Users\alice\private-project\file.py',
            'stdout_tail': 'raw backend log that should not be stored',
            'note': '```python\n' + ('print("raw code")\n' * 80) + '```',
        }
        report = filter_artifact(artifact, payload)
        assert_true(report.get('safe_to_store') is True, 'sanitized artifact should remain storable')
        assert_true(report.get('privacy_status') == 'sanitized', 'token/path/log content should be sanitized')
        sanitized_text = json.dumps(report.get('sanitized'), ensure_ascii=False)
        assert_true('FAKE_TOKEN_12345' not in sanitized_text, 'token value leaked')
        assert_true('person@example.com' not in sanitized_text, 'email leaked')
        assert_true('C:\\Users\\alice' not in sanitized_text, 'absolute path leaked')
        assert_true('raw backend log' not in sanitized_text, 'raw log leaked')
        assert_true('[REDACTED_LONG_CODE_BLOCK]' in sanitized_text, 'long code block not redacted')

        env_report = filter_artifact(workspace / '.env', {'content': 'SHOULD-NOT-BE-READ'})
        assert_true(env_report.get('safe_to_store') is False, '.env artifact should be rejected')
        assert_true(env_report.get('privacy_status') == 'rejected', '.env should be rejected')

        unsafe_report = filter_artifact(workspace / 'map_evidence.json', {'note': 'should-not-be-read'})
        assert_true(unsafe_report.get('safe_to_store') is False, 'unsafe marker should reject artifact')

        public_report = write_privacy_report(workspace, report)
        public_text = json.dumps(public_report, ensure_ascii=False)
        assert_true(public_report.get('privacy_status') == 'sanitized', 'public report should keep status fields')
        assert_true('FAKE_TOKEN_12345' not in public_text, 'privacy report leaked token value')

    print('cross project privacy filter tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
