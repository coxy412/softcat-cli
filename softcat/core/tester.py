"""T — Test: Validate the generated agent works correctly."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, Field
from rich.console import Console

from softcat.config import Config

console = Console()


class TestResult(BaseModel):
    """Result of testing an agent."""

    passed: bool
    message: str = ""
    output_preview: str = ""
    checks: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class Tester:
    """T — Test phase of the S.O.F.T.C.A.T pipeline.

    Runs the generated agent in a sandboxed test mode to validate
    it works before deployment.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def test(self, agent_dir: Path) -> TestResult:
        """Pre-activation test: syntax + file presence. Quick and dependency-free."""
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

        # Step 2: Import check — skipped for now (deps not yet installed at test phase)
        console.print("[dim]   → import check skipped (deps installed during activation)[/dim]")

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

    def test_runtime(self, agent_dir: Path, timeout: int = 30) -> TestResult:
        """Post-activation test: import check, dry-run execution, output validation.

        This should be called AFTER deps are installed (post-activation).
        Sets SOFTCAT_DRY_RUN=1 so well-behaved agents use sample data.
        """
        from softcat.agents.runtime import build_env, resolve_python

        checks: dict[str, bool] = {}
        warnings: list[str] = []
        agent_py = agent_dir / "agent.py"
        python = resolve_python(agent_dir)
        env = build_env(agent_dir)

        # Step 1: Import check — load agent.py as a module (skips if __name__ == "__main__" block)
        import_script = (
            "import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('agent', '{agent_py}'); "
            "mod = importlib.util.module_from_spec(spec); "
            "spec.loader.exec_module(mod); "
            "print('imports OK')"
        )
        try:
            result = subprocess.run(
                [python, "-c", import_script],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(agent_dir),
                env=env,
            )
            checks["import"] = result.returncode == 0
            if not checks["import"]:
                warnings.append(f"Import failed: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            checks["import"] = False
            warnings.append("Import check timed out")

        # Step 2: Dry-run execution with SOFTCAT_DRY_RUN=1
        outputs_dir = agent_dir / "outputs"
        outputs_before: set[Path] = set()
        if outputs_dir.exists():
            outputs_before = set(outputs_dir.iterdir())

        dry_env = build_env(agent_dir, extra={"SOFTCAT_DRY_RUN": "1"})
        try:
            result = subprocess.run(
                [python, str(agent_py)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(agent_dir),
                env=dry_env,
            )
            checks["execution"] = result.returncode == 0
            if not checks["execution"]:
                warnings.append(
                    f"Dry-run failed (exit {result.returncode}): {result.stderr[:200]}"
                )
        except subprocess.TimeoutExpired:
            checks["execution"] = False
            warnings.append(f"Dry-run timed out after {timeout}s")

        # Step 3: Output check — did the agent produce output?
        if outputs_dir.exists():
            outputs_after = set(outputs_dir.iterdir())
            new_outputs = outputs_after - outputs_before
            checks["output_produced"] = len(new_outputs) > 0
            if not checks["output_produced"]:
                warnings.append("Agent did not produce any output files")
        else:
            checks["output_produced"] = False
            warnings.append("outputs/ directory does not exist")

        all_passed = all(checks.values())
        if all_passed:
            message = "All runtime checks passed"
        else:
            failed = [k for k, v in checks.items() if not v]
            message = f"Some checks failed: {', '.join(failed)}"

        return TestResult(
            passed=all_passed,
            message=message,
            checks=checks,
            warnings=warnings,
        )
