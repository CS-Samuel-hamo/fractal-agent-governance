#!/usr/bin/env python3
"""Unit tests for runtime_common.py — fast, no subprocess."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, safe_name, utc_now, write_json


class TestSafeName:
    def test_alphanumeric_passthrough(self) -> None:
        assert safe_name('hello123') == 'hello123'

    def test_spaces_to_hyphens(self) -> None:
        assert safe_name('hello world') == 'hello-world'

    def test_special_chars_replaced(self) -> None:
        assert safe_name('hello@world!') == 'hello-world'

    def test_leading_trailing_hyphens_stripped(self) -> None:
        assert safe_name('-hello-') == 'hello'

    def test_empty_fallsback(self) -> None:
        assert safe_name('') == 'item'

    def test_unicode_preserved(self) -> None:
        assert safe_name('中文测试') == '中文测试'


class TestUtcNow:
    def test_returns_string(self) -> None:
        result = utc_now()
        assert isinstance(result, str)

    def test_ends_with_z(self) -> None:
        assert utc_now().endswith('Z')

    def test_iso_format(self) -> None:
        # YYYY-MM-DDTHH:MM:SSZ
        result = utc_now()
        assert len(result) == 20, f'Expected 20 chars, got {len(result)}: {result}'
        assert result[4] == '-'
        assert result[7] == '-'
        assert result[10] == 'T'
        assert result[13] == ':'
        assert result[16] == ':'


class TestJsonIO:
    def test_load_json_missing_file(self) -> None:
        result = load_json(Path('/nonexistent/path.json'))
        assert result == {}

    def test_load_json_invalid_json(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('not json')
            path = Path(f.name)
        try:
            result = load_json(path)
            assert result == {}
        finally:
            path.unlink(missing_ok=True)

    def test_load_json_valid(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'key': 'value', 'num': 42}, f)
            path = Path(f.name)
        try:
            result = load_json(path)
            assert result == {'key': 'value', 'num': 42}
        finally:
            path.unlink(missing_ok=True)

    def test_load_json_non_dict(self) -> None:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([1, 2, 3], f)
            path = Path(f.name)
        try:
            result = load_json(path)
            assert result == {}
        finally:
            path.unlink(missing_ok=True)

    def test_write_json_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'nested' / 'subdir' / 'test.json'
            write_json(path, {'a': 1, 'b': {'c': [1, 2, 3]}})
            assert path.exists()
            result = json.loads(path.read_text(encoding='utf-8'))
            assert result == {'a': 1, 'b': {'c': [1, 2, 3]}}
            assert path.stat().st_size > 0

    def test_write_json_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            deep = Path(tmp) / 'a' / 'b' / 'c' / 'd' / 'file.json'
            write_json(deep, {'ok': True})
            assert deep.exists()
