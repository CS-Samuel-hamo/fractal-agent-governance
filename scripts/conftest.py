"""pytest configuration for the agent runtime test suite.

This conftest provides shared fixtures and pytest integration.
Test files can also be run directly with `python test_*.py`.
"""
from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from test_helpers import AGENT, ROOT, repo, run_agent


@pytest.fixture
def tmp_project() -> Path:
    """Create a temporary project directory that is cleaned up after the test."""
    project = repo('pytest-tmp')
    yield project
    import shutil

    shutil.rmtree(project, ignore_errors=True)


@pytest.fixture
def agent_cli(tmp_project: Path) -> Path:
    """Return the path to a fresh test project; `run_agent(project, ...)` for CLI calls."""
    return tmp_project


@pytest.fixture
def agent_result(agent_cli: Path, request: pytest.FixtureRequest) -> CompletedProcess[str]:
    """Run the agent CLI with the test function's docstring as the prompt."""
    prompt = getattr(request.function, '__doc__', '') or ''
    return run_agent(agent_cli, prompt.strip())
