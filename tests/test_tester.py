"""Tests for the Tester — syntax check, import check, dry-run."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from softcat.config import Config
from softcat.core.tester import TestResult, Tester


class TestTesterBasic:
    """Test pre-activation checks (syntax + file presence)."""

    def test_syntax_check_passes(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("print('hello')\n")
        (agent_dir / "config.yaml").write_text("name: test\n")
        (agent_dir / "prompt.md").write_text("# Test\n")

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test(agent_dir)
        assert result.passed

    def test_syntax_check_fails(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("def broken(\n")
        (agent_dir / "config.yaml").write_text("name: test\n")
        (agent_dir / "prompt.md").write_text("# Test\n")

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test(agent_dir)
        assert not result.passed
        assert "Syntax error" in result.message

    def test_missing_agent_py(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test(agent_dir)
        assert not result.passed
        assert "agent.py not found" in result.message

    def test_missing_config_yaml(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("print('hello')\n")
        (agent_dir / "prompt.md").write_text("# Test\n")

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test(agent_dir)
        assert not result.passed
        assert "config.yaml" in result.message


class TestTesterRuntime:
    """Test post-activation runtime checks."""

    def test_runtime_import_check(self, tmp_path: Path):
        """Import check should pass for a simple valid agent."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "outputs").mkdir()
        (agent_dir / "agent.py").write_text(
            "import os\n\ndef main():\n    pass\n\nif __name__ == '__main__':\n    main()\n"
        )

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test_runtime(agent_dir, timeout=10)

        assert result.checks.get("import") is True

    def test_runtime_execution_with_output(self, tmp_path: Path):
        """Agent that writes to outputs/ should pass all checks."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        outputs_dir = agent_dir / "outputs"
        outputs_dir.mkdir()

        agent_code = (
            "import os\n"
            "from pathlib import Path\n"
            "def main():\n"
            "    out = Path(__file__).parent / 'outputs' / 'test.txt'\n"
            "    out.write_text('hello')\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        (agent_dir / "agent.py").write_text(agent_code)

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test_runtime(agent_dir, timeout=10)

        assert result.checks.get("import") is True
        assert result.checks.get("execution") is True
        assert result.checks.get("output_produced") is True
        assert result.passed

    def test_runtime_no_output_warns(self, tmp_path: Path):
        """Agent that doesn't produce output should flag it."""
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "outputs").mkdir()

        agent_code = (
            "def main():\n"
            "    pass\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        (agent_dir / "agent.py").write_text(agent_code)

        config = Config(anthropic_api_key="test-key")
        tester = Tester(config)
        result = tester.test_runtime(agent_dir, timeout=10)

        assert result.checks.get("output_produced") is False
        assert any("output" in w.lower() for w in result.warnings)


class TestTestResult:
    """Test the TestResult model."""

    def test_checks_and_warnings(self):
        result = TestResult(
            passed=False,
            message="Import failed",
            checks={"import": False, "execution": True},
            warnings=["Could not import agent"],
        )
        assert not result.passed
        assert result.checks["import"] is False
        assert len(result.warnings) == 1

    def test_backward_compat(self):
        """Old-style TestResult (no checks/warnings) should still work."""
        result = TestResult(passed=True, message="OK")
        assert result.checks == {}
        assert result.warnings == []
