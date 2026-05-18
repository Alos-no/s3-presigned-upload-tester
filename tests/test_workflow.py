"""Tests for GitHub Actions workflow invariants."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "test-providers.yml"


def test_workflow_restores_published_history_before_provider_tests():
    """CI must seed site/data/history.json before build_site appends the new run."""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    restore_step = "Restore published history"
    run_step = "Run provider tests"

    assert restore_step in workflow
    assert "https://s3.alos.no/data/history.json" in workflow
    assert workflow.index(restore_step) < workflow.index(run_step)
