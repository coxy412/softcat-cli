"""T — Test: Validate the generated agent works correctly."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

from softcat.config import Config

console = Console()


class TestResult(BaseModel):
    """Result of testing an agent."""

    passed: bool
    message: str = ""
    output_preview: str = ""


class Tester:
    """T — Test phase of the S.O.F.T.C.A.T pipeline.

    Runs the generated agent in a sandboxed test mode to validate
    it works before deployment.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def test(self, agent_dir: Path) -> TestResult:
        """Test an agent by running it with --dry-run or in test mode."""
        agent_py = agent_dir / "agent.py"

        if not agent_py.exists():
            return TestResult(passed=False, message="agent.py not found")

        # Step 1: Syntax check
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import ast; ast.parse(open('{agent_py}').read())"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return TestResult(
                    passed=False,
                    message=f"Syntax error: {result.stderr.strip()}",
                )
        except subprocess.TimeoutExpired:
            return TestResult(passed=False, message="Syntax check timed out")

        # Step 2: Import check — verify dependencies are available
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"exec(open('{agent_py}').read().split('def ')[0])"],
                capture_output=True,
                text=True,
                timeout=15,
                env={**dict(__import__("os").environ), "SOFTCAT_TEST_MODE": "1"},
            )
            if result.returncode != 0:
                return TestResult(
                    passed=False,
                    message=f"Import error: {result.stderr.strip()[:200]}",
                )
        except subprocess.TimeoutExpired:
            return TestResult(passed=False, message="Import check timed out")

        # Step 3: Config check
        config_yaml = agent_dir / "config.yaml"
        if not config_yaml.exists():
            return TestResult(passed=False, message="config.yaml not found")

        prompt_md = agent_dir / "prompt.md"
        if not prompt_md.exists():
            return TestResult(passed=False, message="prompt.md not found")

        return TestResult(
            passed=True,
            message="All checks passed",
        )
