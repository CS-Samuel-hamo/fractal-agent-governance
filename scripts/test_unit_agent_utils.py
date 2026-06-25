#!/usr/bin/env python3
"""Unit tests for agent_utils.py — pure functions only, no subprocess."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from agent_utils import (
    clean_progress,
    parse_json_output,
    pipeline_failure_summary,
    user_task_result,
)


class TestCleanProgress:
    def test_int(self) -> None:
        assert clean_progress(75) == '75%'

    def test_float(self) -> None:
        assert clean_progress(33.3) == '33%'

    def test_int_clamped_low(self) -> None:
        assert clean_progress(-5) == '0%'

    def test_int_clamped_high(self) -> None:
        assert clean_progress(150) == '100%'

    def test_string_with_percent(self) -> None:
        assert clean_progress('50%') == '50%'

    def test_string_without_percent(self) -> None:
        assert clean_progress('done') == 'done'

    def test_empty_string(self) -> None:
        assert clean_progress('') == 'unknown'

    def test_none(self) -> None:
        assert clean_progress(None) == 'unknown'

    def test_zero(self) -> None:
        assert clean_progress(0) == '0%'

    def test_whitespace_string(self) -> None:
        assert clean_progress('  ') == 'unknown'


class TestParseJsonOutput:
    def test_empty_result(self) -> None:
        assert parse_json_output({}) == {}

    def test_stdout_empty(self) -> None:
        assert parse_json_output({'stdout': ''}) == {}

    def test_stdout_valid_json(self) -> None:
        result = parse_json_output({'stdout': '{"a": 1, "b": "hello"}'})
        assert result == {'a': 1, 'b': 'hello'}

    def test_stdout_non_dict_json(self) -> None:
        assert parse_json_output({'stdout': '"just a string"'}) == {}

    def test_stdout_invalid_json(self) -> None:
        assert parse_json_output({'stdout': 'not-json-at-all'}) == {}

    def test_stdout_starts_with_bracket(self) -> None:
        assert parse_json_output({'stdout': '["array"]'}) == {}

    def test_stdout_whitespace_before_json(self) -> None:
        result = parse_json_output({'stdout': '  {"key": "val"}'})
        assert result == {'key': 'val'}

    def test_stdout_nested(self) -> None:
        result = parse_json_output({'stdout': '{"outer": {"inner": [1,2,3]}}'})
        assert result == {'outer': {'inner': [1, 2, 3]}}


class TestUserTaskResult:
    def test_basic(self) -> None:
        result = user_task_result(task='fix bug', mode='preview', result='ready')
        assert result == {'task': 'fix bug', 'mode': 'preview', 'result': 'ready'}

    def test_empty_task(self) -> None:
        result = user_task_result(task='', mode='blocked', result='no input')
        assert result == {'task': '', 'mode': 'blocked', 'result': 'no input'}


class TestPipelineFailureSummary:
    def test_payload_verdict_and_reason(self) -> None:
        result = pipeline_failure_summary(
            {'final_verdict': 'BLOCKED', 'reason': 'timeout'},
            {},
        )
        assert result == 'BLOCKED: timeout'

    def test_payload_verdict_only(self) -> None:
        result = pipeline_failure_summary(
            {'final_verdict': 'FAILED', 'status': ''},
            {},
        )
        assert result == 'FAILED'

    def test_payload_reason_only(self) -> None:
        result = pipeline_failure_summary(
            {'status': 'error', 'result': 'worker crashed'},
            {},
        )
        assert result == 'error: worker crashed'

    def test_empty_payload_with_stderr(self) -> None:
        result = pipeline_failure_summary({}, {'stderr': 'Line1\nLine2\nLast line of error'})
        assert 'Last line of error' in result

    def test_empty_payload_with_stdout(self) -> None:
        result = pipeline_failure_summary({}, {'stdout': 'Only output here', 'stderr': ''})
        assert 'Only output here' in result

    def test_totally_empty(self) -> None:
        result = pipeline_failure_summary({}, {})
        assert 'could not complete' in result
