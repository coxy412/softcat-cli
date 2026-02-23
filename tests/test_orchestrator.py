"""Tests for the SOFT CAT Orchestrator."""

from softcat.config import Config
from softcat.core.orchestrator import Orchestrator
from softcat.core.scanner import DataSource, ScanResult


class TestOrchestrator:
    """Test the Orchestrator class."""

    def test_simple_digest_plan(self):
        config = Config(anthropic_api_key="test-key")
        orchestrator = Orchestrator(config)

        scan = ScanResult(
            suggested_name="test-digest",
            summary="A daily digest",
            intent="digest",
            complexity="simple",
            data_sources=[DataSource(type="rss", url_or_path="https://example.com/rss")],
            dependencies=["feedparser"],
        )

        plan = orchestrator.plan(scan)

        assert plan.template == "digest"
        assert "claude-haiku" in plan.model
        assert "feedparser" in plan.pip_dependencies
        assert "anthropic" in plan.pip_dependencies

    def test_complex_custom_plan(self):
        config = Config(anthropic_api_key="test-key")
        orchestrator = Orchestrator(config)

        scan = ScanResult(
            suggested_name="test-complex",
            summary="A complex agent",
            intent="custom",
            complexity="complex",
            data_sources=[
                DataSource(type="api", url_or_path="https://api.example.com"),
                DataSource(type="web", url_or_path="https://example.com"),
            ],
        )

        plan = orchestrator.plan(scan)

        assert plan.template == "base"
        assert "sonnet" in plan.model
        assert "httpx" in plan.pip_dependencies
        assert "beautifulsoup4" in plan.pip_dependencies

    def test_cost_estimation(self):
        config = Config(anthropic_api_key="test-key")
        orchestrator = Orchestrator(config)

        scan = ScanResult(
            suggested_name="test",
            summary="Test",
            estimated_tokens_per_run=2000,
            complexity="simple",
        )

        plan = orchestrator.plan(scan)
        assert plan.estimated_cost_per_run > 0
